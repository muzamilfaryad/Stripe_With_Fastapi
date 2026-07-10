from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
import stripe
import logging
from app.core.database import get_db
from app.schemas.payment import PaymentCreateRequest, PaymentIntentResponse
from app.repositories.product_repository import product as product_repo
from app.repositories.order_repository import order as order_repo, OrderCreate
from app.repositories.payment_repository import payment as payment_repo, PaymentCreate
from app.services.stripe_service import stripe_service
from app.models.customer import Customer

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=PaymentIntentResponse)
def create_payment(
    request: PaymentCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
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
        
    amount_cents = active_price.unit_amount
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
        
        # 3. Create PaymentIntent in Stripe
        intent = stripe_service.create_payment_intent(
            amount_cents=amount_cents,
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
            amount_cents=amount_cents,
            currency=currency,
            status="pending",
            stripe_payment_intent_id=intent.id,
            idempotency_key=idempotency_key  # Store for future idempotent requests
        )
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
