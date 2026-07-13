from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
import stripe
import logging
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.schemas.payment import PaymentCreateRequest, PaymentIntentResponse, RefundRequest, RefundResponse
from app.repositories.product_repository import product as product_repo
from app.repositories.order_repository import order as order_repo, OrderCreate
from app.repositories.payment_repository import payment as payment_repo, PaymentCreate
from app.services.stripe_service import stripe_service
from app.models.customer import Customer

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post(
    "/",
    response_model=PaymentIntentResponse,
    summary="Create a payment intent",
    description="""
    Create a Stripe Payment Intent for one-time payment processing.
    
    **Features:**
    - Idempotent requests using `Idempotency-Key` header
    - Atomic transaction handling (DB + Stripe)
    - Automatic retry logic for network failures
    - Rate limited to 10 requests per minute per IP
    
    **Flow:**
    1. Validates customer and product
    2. Creates database order
    3. Creates Stripe PaymentIntent
    4. Returns client_secret for frontend
    
    **Idempotency:**
    Send an `Idempotency-Key` header to prevent duplicate payments from double-clicks or retries.
    """,
    responses={
        200: {
            "description": "Payment intent created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "client_secret": "pi_3abc123_secret_xyz789",
                        "payment_id": 42
                    }
                }
            }
        },
        400: {"description": "Invalid request or payment processing error"},
        404: {"description": "Customer or product not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60))]
)
def create_payment(
    request: PaymentCreateRequest = Body(
        ...,
        examples={
            "one_time_payment": {
                "summary": "One-time payment example",
                "description": "Create a payment for an existing product",
                "value": {
                    "customer_id": 1,
                    "product_id": 1
                }
            }
        }
    ),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", description="Unique key to prevent duplicate payments")
):
    """
    Create a payment intent with atomic transaction handling and idempotency support.
    
    Send an 'Idempotency-Key' header to prevent duplicate payments from double-clicks.
    """
    
    # Check for idempotency - prevent duplicate payment creation
    if idempotency_key:
        existing_payment = db.query(payment_repo.model).filter(
            payment_repo.model.idempotency_key == idempotency_key
        ).first()
        
        if existing_payment:
            logger.info(f"Idempotent request detected: {idempotency_key}, returning existing payment {existing_payment.id}")
            # Retrieve the payment intent to get fresh client_secret
            try:
                intent = stripe_service.get_payment_intent(existing_payment.stripe_payment_intent_id)
                return PaymentIntentResponse(
                    client_secret=intent.client_secret,
                    payment_id=existing_payment.id
                )
            except stripe.error.StripeError:
                # If Stripe lookup fails, return what we have
                logger.warning(f"Could not retrieve Stripe intent for idempotent request")
                raise HTTPException(
                    status_code=400, 
                    detail="Payment already exists but could not retrieve details"
                )
    
    # 0. Validate Customer
    db_customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 1. Validate Product & Price
    db_product = product_repo.get(db, request.product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # Find the active price for this product
    active_price = next((p for p in db_product.prices if p.active), None)
    if not active_price:
        raise HTTPException(status_code=400, detail="Product has no active price")
        
    amount = active_price.unit_amount  # Amount in dollars
    currency = active_price.currency

    try:
        # 2. Create Order but don't commit yet
        db_order = order_repo.model(
            customer_id=request.customer_id,
            product_id=request.product_id,
            status="pending"
        )
        db.add(db_order)
        db.flush()  # Get order.id without committing
        
        logger.info(f"Created pending order {db_order.id} for customer {request.customer_id}")
        
        # 3. Create PaymentIntent in Stripe (amount will be converted to cents in stripe_service)
        intent = stripe_service.create_payment_intent(
            amount=amount,
            currency=currency,
            metadata={
                "order_id": str(db_order.id),
                "customer_id": str(request.customer_id),
                "product_id": str(request.product_id)
            }
        )
        
        logger.info(f"Created Stripe PaymentIntent {intent.id} for order {db_order.id}")
        
        # 4. Create Payment Record with the intent ID
        db_payment = payment_repo.model(
            order_id=db_order.id,
            currency=currency,
            status="pending",
            stripe_payment_intent_id=intent.id,
            idempotency_key=idempotency_key  # Store for future idempotent requests
        )
        db_payment.amount = amount  # Use property setter (converts to cents)
        db.add(db_payment)
        
        # 5. Commit everything atomically
        db.commit()
        db.refresh(db_payment)
        db.refresh(db_order)
        
        logger.info(f"Successfully created payment {db_payment.id} with intent {intent.id}")

        return PaymentIntentResponse(
            client_secret=intent.client_secret,
            payment_id=db_payment.id
        )
        
    except stripe.error.CardError as e:
        db.rollback()
        logger.error(f"Stripe card error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Card declined: {e.user_message}")
        
    except stripe.error.RateLimitError as e:
        db.rollback()
        logger.error(f"Stripe rate limit: {str(e)}")
        raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")
        
    except stripe.error.InvalidRequestError as e:
        db.rollback()
        logger.error(f"Stripe invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid payment request: {str(e)}")
        
    except stripe.error.AuthenticationError as e:
        db.rollback()
        logger.error(f"Stripe authentication error: {str(e)}")
        raise HTTPException(status_code=500, detail="Payment system authentication failed")
        
    except stripe.error.APIConnectionError as e:
        db.rollback()
        logger.error(f"Stripe network error: {str(e)}")
        raise HTTPException(status_code=503, detail="Payment service unavailable. Please try again.")
        
    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Payment processing error: {str(e)}")
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in create_payment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post(
    "/{payment_intent_id}/refund",
    response_model=RefundResponse,
    summary="Refund a payment",
    description="""
    Create a refund for a payment based on Stripe Payment Intent ID.
    
    **Features:**
    - Full or partial refunds
    - Automatic status update in database
    - Optional refund reason tracking
    - Rate limited to 10 requests per minute per IP
    
    **Flow:**
    - Validates payment exists and is eligible for refund
    - Creates Stripe refund
    - Updates payment status in database
    - Returns refund details
    
    **Refund Eligibility:**
    - Payment must have status 'succeeded'
    - Payment must have a valid Stripe payment intent ID
    """,
    responses={
        200: {
            "description": "Refund processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "refund_id": "re_3abc123xyz789",
                        "payment_id": 42,
                        "amount": 10.00,
                        "status": "succeeded",
                        "message": "Refund processed successfully"
                    }
                }
            }
        },
        400: {"description": "Invalid request or payment not eligible for refund"},
        404: {"description": "Payment not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60))]
)
def refund_payment(
    payment_intent_id: str,
    request: RefundRequest = Body(
        ...,
        examples={
            "full_refund": {
                "summary": "Full refund",
                "description": "Refund the entire payment amount",
                "value": {
                    "reason": "requested_by_customer"
                }
            },
            "partial_refund": {
                "summary": "Partial refund",
                "description": "Refund a specific amount",
                "value": {
                    "amount": 5.00,
                    "reason": "requested_by_customer"
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    """
    Refund a payment by Stripe Payment Intent ID. Supports both full and partial refunds.
    """
    
    try:
        # 1. Get the payment from database
        db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
        if not db_payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # 2. Validate payment is eligible for refund
        if not db_payment.stripe_payment_intent_id:
            raise HTTPException(
                status_code=400, 
                detail="Payment has no associated Stripe payment intent"
            )
        
        if db_payment.status != "succeeded":
            raise HTTPException(
                status_code=400, 
                detail=f"Payment cannot be refunded. Current status: {db_payment.status}"
            )
        
        # 3. Validate refund amount if partial refund
        refund_amount = request.amount  # Amount in dollars
        if refund_amount is not None:
            if refund_amount > db_payment.amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Refund amount (${refund_amount}) cannot exceed payment amount (${db_payment.amount})"
                )
        else:
            refund_amount = db_payment.amount
        
        logger.info(f"Processing refund for payment intent {payment_intent_id}, amount: ${refund_amount}")
        
        # 4. Create refund in Stripe (amount will be converted to cents in stripe_service)
        refund = stripe_service.create_refund(
            payment_intent_id=payment_intent_id,
            amount=request.amount,  # None for full refund
            reason=request.reason
        )
        
        logger.info(f"Created Stripe refund {refund.id} for payment intent {payment_intent_id}")
        
        # 5. Update payment status in database
        if refund_amount == db_payment.amount:
            # Full refund
            db_payment.status = "refunded"
        else:
            # Partial refund - you might want to track this differently
            db_payment.status = "partially_refunded"
        
        db.commit()
        db.refresh(db_payment)
        
        logger.info(f"Updated payment intent {payment_intent_id} status to {db_payment.status}")
        
        return RefundResponse(
            refund_id=refund.id,
            payment_id=db_payment.id,
            amount=refund_amount,
            status=refund.status,
            message="Refund processed successfully"
        )
        
    except stripe.error.InvalidRequestError as e:
        db.rollback()
        logger.error(f"Stripe invalid request for refund: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid refund request: {str(e)}")
        
    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Stripe error during refund: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Refund processing error: {str(e)}")
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during refund: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in refund_payment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
