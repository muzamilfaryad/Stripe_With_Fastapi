import stripe
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment
from app.models.customer import Customer
from app.schemas.checkout import CheckoutRequest
import logging

logger = logging.getLogger(__name__)

def create_checkout_session(db: Session, checkout_req: CheckoutRequest):
    """
    Create a checkout session with atomic transaction handling.
    
    Strategy: Create Order and Payment records first with db.flush() (get IDs without committing),
    then create Stripe session, then commit everything together.
    If Stripe fails, rollback all database changes.
    
    Architecture:
    - Order: tracks the customer order with status
    - Payment: tracks the actual payment transaction with amount, currency, and Stripe IDs
    """
    # Get the customer
    customer = db.query(Customer).filter(Customer.id == checkout_req.customer_id).first()
    if not customer:
        raise ValueError("Customer not found")
    
    if not customer.stripe_customer_id:
        raise ValueError("Customer does not have a Stripe customer ID")
    
    try:
        # 1. Create Order in database but DON'T commit yet
        db_order = Order(
            customer_id=customer.id,
            product_id=None,  # Can be set if you have product tracking
            status='pending'
        )
        db.add(db_order)
        db.flush()  # Get the order.id without committing the transaction
        
        logger.info(f"Created pending order {db_order.id} for customer {customer.id}")
        
        # 2. Create Payment record linked to the order
        db_payment = Payment(
            order_id=db_order.id,
            currency=checkout_req.currency,
            status='pending'
        )
        db_payment.amount = checkout_req.amount  # Use property setter (converts to cents)
        db.add(db_payment)
        db.flush()  # Get the payment.id without committing
        
        logger.info(f"Created pending payment {db_payment.id} for order {db_order.id}")
        
        # 3. Create Stripe Checkout Session with order reference
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer=customer.stripe_customer_id,
            client_reference_id=str(db_order.id),
            line_items=[{
                'price_data': {
                    'currency': checkout_req.currency,
                    'unit_amount': int(checkout_req.amount * 100),  # Convert dollars to cents
                    'product_data': {
                        'name': checkout_req.product_name,
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=settings.SUCCESS_URL + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=settings.CANCEL_URL,
        )
        
        logger.info(f"Created Stripe checkout session {session.id} for order {db_order.id}")
        
        # 4. Update Payment with the Stripe session ID
        db_payment.stripe_checkout_session_id = session.id
        
        # 5. Commit everything together - atomic operation
        db.commit()
        db.refresh(db_order)
        db.refresh(db_payment)
        
        logger.info(f"Successfully committed order {db_order.id} with payment {db_payment.id} and session {session.id}")
        
        return session
        
    except stripe.error.CardError as e:
        # Card was declined
        db.rollback()
        logger.error(f"Stripe card error during checkout: {str(e)}")
        raise ValueError(f"Card declined: {e.user_message}")
        
    except stripe.error.RateLimitError as e:
        # Too many requests to Stripe API
        db.rollback()
        logger.error(f"Stripe rate limit error: {str(e)}")
        raise ValueError("Too many requests. Please try again shortly.")
        
    except stripe.error.InvalidRequestError as e:
        # Invalid parameters
        db.rollback()
        logger.error(f"Stripe invalid request: {str(e)}")
        raise ValueError(f"Invalid request: {str(e)}")
        
    except stripe.error.AuthenticationError as e:
        # Authentication with Stripe failed
        db.rollback()
        logger.error(f"Stripe authentication error: {str(e)}")
        raise ValueError("Payment system authentication failed. Please contact support.")
        
    except stripe.error.APIConnectionError as e:
        # Network communication failed
        db.rollback()
        logger.error(f"Stripe network error: {str(e)}")
        raise ValueError("Network error. Please try again.")
        
    except stripe.error.StripeError as e:
        # Generic Stripe error
        db.rollback()
        logger.error(f"Stripe error during checkout: {str(e)}")
        raise ValueError(f"Payment processing error: {str(e)}")
        
    except SQLAlchemyError as e:
        # Database error
        db.rollback()
        logger.error(f"Database error during checkout: {str(e)}")
        raise ValueError("Database error. Please try again.")
        
    except Exception as e:
        # Unexpected error - rollback to be safe
        db.rollback()
        logger.error(f"Unexpected error during checkout: {str(e)}", exc_info=True)
        raise ValueError(f"An unexpected error occurred: {str(e)}")
