import stripe
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from app.models.subscription import Subscription
from app.models.customer import Customer
from app.models.product import Price
from app.schemas.subscription import SubscriptionCreate, SubscriptionIntentResponse
from app.core.config import settings
from app.services.stripe_service import stripe_service
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def create_checkout_session(self, sub_data: SubscriptionCreate):
        """
        Create a checkout session for subscription with atomic transaction handling.
        """
        customer = self.db.query(Customer).filter(Customer.id == sub_data.customer_id).first()
        if not customer:
            raise ValueError(f"Customer with ID {sub_data.customer_id} not found")
        
        price = self.db.query(Price).filter(Price.id == sub_data.price_id).first()
        if not price:
            raise ValueError(f"Price with ID {sub_data.price_id} not found")
        
        if not customer.stripe_customer_id:
            raise ValueError(f"Customer {customer.id} ({customer.email}) does not have a Stripe customer ID. Create customer in Stripe first.")
        
        try:
            # Create local subscription record but don't commit yet
            db_sub = Subscription(
                customer_id=customer.id,
                price_id=price.id,
                stripe_customer_id=customer.stripe_customer_id,
                stripe_price_id=price.stripe_price_id,
                status="pending",
            )
            self.db.add(db_sub)
            self.db.flush()  # Get subscription.id without committing
            
            logger.info(f"Created pending subscription {db_sub.id} for customer {customer.id}")
            
            # Create Stripe checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                customer=customer.stripe_customer_id,
                client_reference_id=str(db_sub.id),
                line_items=[{
                    'price': price.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=settings.SUCCESS_URL + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=settings.CANCEL_URL,
            )
            
            logger.info(f"Created Stripe checkout session {session.id} for subscription {db_sub.id}")
            
            # Commit everything together
            self.db.commit()
            self.db.refresh(db_sub)
            
            return session
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error during subscription checkout: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during subscription checkout: {str(e)}")
            raise ValueError("Database error occurred")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during subscription checkout: {str(e)}", exc_info=True)
            raise

    def create_subscription_intent(self, sub_data: SubscriptionCreate) -> SubscriptionIntentResponse:
        """
        Create a subscription with Payment Intent flow and atomic transaction handling.
        """
        customer = self.db.query(Customer).filter(Customer.id == sub_data.customer_id).first()
        if not customer:
            raise ValueError(f"Customer with ID {sub_data.customer_id} not found")
        
        price = self.db.query(Price).filter(Price.id == sub_data.price_id).first()
        if not price:
            raise ValueError(f"Price with ID {sub_data.price_id} not found")
        
        if not customer.stripe_customer_id:
            raise ValueError(f"Customer {customer.id} ({customer.email}) does not have a Stripe customer ID. Create customer in Stripe first.")
        
        try:
            # Create local subscription record but don't commit yet
            db_sub = Subscription(
                customer_id=customer.id,
                price_id=price.id,
                stripe_customer_id=customer.stripe_customer_id,
                stripe_price_id=price.stripe_price_id,
                status="pending",
            )
            self.db.add(db_sub)
            self.db.flush()  # Get subscription.id without committing
            
            logger.info(f"Created pending subscription {db_sub.id} for customer {customer.id}")
            
            # Create subscription in Stripe
            stripe_sub = stripe_service.create_subscription(
                customer_id=customer.stripe_customer_id,
                price_id=price.stripe_price_id,
                metadata={"client_reference_id": str(db_sub.id)}
            )
            
            logger.info(f"Created Stripe subscription {stripe_sub.id} for local subscription {db_sub.id}")
            
            # Update local subscription with Stripe data
            db_sub.stripe_subscription_id = stripe_sub.id
            db_sub.status = stripe_sub.status
            
            # Safely access period fields (may not exist in newer API versions)
            period_start = getattr(stripe_sub, 'current_period_start', None)
            period_end = getattr(stripe_sub, 'current_period_end', None)
            db_sub.current_period_start = datetime.fromtimestamp(period_start) if period_start else None
            db_sub.current_period_end = datetime.fromtimestamp(period_end) if period_end else None
            
            # Commit everything together
            self.db.commit()
            self.db.refresh(db_sub)
            
            logger.info(f"Successfully committed subscription {db_sub.id} with Stripe ID {stripe_sub.id}")
            
            # In API versions >= 2025-03-31, payment_intent was replaced by confirmation_secret.
            confirmation_secret = getattr(stripe_sub.latest_invoice, 'confirmation_secret', None)
            client_secret = confirmation_secret.client_secret if confirmation_secret else ""

            return SubscriptionIntentResponse(
                client_secret=client_secret,
                subscription_id=db_sub.id
            )
            
        except stripe.error.CardError as e:
            self.db.rollback()
            logger.error(f"Stripe card error: {str(e)}")
            raise ValueError(f"Card declined: {e.user_message}")
            
        except stripe.error.InvalidRequestError as e:
            self.db.rollback()
            logger.error(f"Stripe invalid request: {str(e)}")
            raise ValueError(f"Invalid subscription request: {str(e)}")
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error during subscription creation: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during subscription creation: {str(e)}")
            raise ValueError("Database error occurred")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during subscription creation: {str(e)}", exc_info=True)
            raise

    def get_subscriptions_for_customer(self, customer_id: int):
        """Get all subscriptions for a customer."""
        return self.db.query(Subscription).filter(Subscription.customer_id == customer_id).all()

    def cancel_subscription(self, subscription_id: str, cancel_immediately: bool = False):
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Local subscription ID or Stripe Subscription ID
            cancel_immediately: If True, cancels immediately. If False, cancels at period end.
        
        Returns:
            Updated subscription object
        """
        if isinstance(subscription_id, int) or (isinstance(subscription_id, str) and subscription_id.isdigit()):
            db_sub = self.db.query(Subscription).filter(Subscription.id == int(subscription_id)).first()
        else:
            db_sub = self.db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
            
        if not db_sub:
            raise ValueError(f"Subscription with ID {subscription_id} not found")
        
        if not db_sub.stripe_subscription_id:
            raise ValueError(f"Subscription {subscription_id} has no Stripe subscription ID")
        
        try:
            if cancel_immediately:
                # Cancel immediately
                stripe_sub = stripe.Subscription.cancel(db_sub.stripe_subscription_id)
                logger.info(f"Immediately canceled Stripe subscription {db_sub.stripe_subscription_id}")
            else:
                # Cancel at period end
                stripe_sub = stripe.Subscription.modify(
                    db_sub.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                logger.info(f"Scheduled cancellation for Stripe subscription {db_sub.stripe_subscription_id} at period end")
            
            # Update local subscription
            db_sub.status = stripe_sub.status
            db_sub.cancel_at_period_end = stripe_sub.cancel_at_period_end
            
            self.db.commit()
            self.db.refresh(db_sub)
            
            logger.info(f"Successfully updated local subscription {db_sub.id} with cancellation status")
            
            return db_sub
            
        except stripe.error.InvalidRequestError as e:
            self.db.rollback()
            logger.error(f"Stripe invalid request during cancellation: {str(e)}")
            raise ValueError(f"Cannot cancel subscription: {str(e)}")
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error during cancellation: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during subscription cancellation: {str(e)}", exc_info=True)
            raise
