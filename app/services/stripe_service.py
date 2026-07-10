import stripe
from typing import Optional, Dict, Any
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.max_network_retries = 2  # Built-in retry for network failures

class StripeService:
    """
    Wrapper service for Stripe API calls with retry logic and error handling.
    """
    
    @staticmethod
    def _retry_with_backoff(func, max_attempts=3, initial_delay=1.0):
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay in seconds (doubles each retry)
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return func()
            except stripe.error.RateLimitError as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    logger.warning(f"Rate limited by Stripe. Retrying in {delay}s... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Rate limit exceeded after {max_attempts} attempts")
                    raise
            except stripe.error.APIConnectionError as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    logger.warning(f"Stripe API connection error. Retrying in {delay}s... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Stripe API connection failed after {max_attempts} attempts")
                    raise
            except (stripe.error.CardError, 
                    stripe.error.InvalidRequestError, 
                    stripe.error.AuthenticationError) as e:
                # Don't retry these - they won't succeed on retry
                logger.error(f"Stripe error that won't benefit from retry: {type(e).__name__}")
                raise
        
        # If we get here, all retries failed
        raise last_exception
    
    @staticmethod
    def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, str] = None) -> stripe.PaymentIntent:
        """
        Create a payment intent with retry logic.
        """
        def _create():
            return stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
        
        return StripeService._retry_with_backoff(_create)
        
    @staticmethod
    def get_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
        """
        Retrieve a payment intent with retry logic.
        """
        def _get():
            return stripe.PaymentIntent.retrieve(payment_intent_id)
        
        return StripeService._retry_with_backoff(_get)

    @staticmethod
    def create_customer(email: str, name: str) -> stripe.Customer:
        """
        Create a Stripe customer with retry logic.
        """
        def _create():
            return stripe.Customer.create(email=email, name=name)
        
        return StripeService._retry_with_backoff(_create)

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        """
        Construct and verify a webhook event.
        
        Note: No retry logic here - webhook signature verification
        should either succeed or fail immediately.
        """
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    @staticmethod
    def create_subscription(customer_id: str, price_id: str, metadata: Dict[str, str] = None) -> stripe.Subscription:
        """
        Create a subscription with retry logic.
        """
        def _create():
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.confirmation_secret"],
                metadata=metadata or {},
            )
        
        return StripeService._retry_with_backoff(_create)
    
    @staticmethod
    def cancel_subscription(subscription_id: str) -> stripe.Subscription:
        """
        Cancel a subscription immediately with retry logic.
        """
        def _cancel():
            return stripe.Subscription.delete(subscription_id)
        
        return StripeService._retry_with_backoff(_cancel)
    
    @staticmethod
    def update_subscription(subscription_id: str, **kwargs) -> stripe.Subscription:
        """
        Update a subscription with retry logic.
        """
        def _update():
            return stripe.Subscription.modify(subscription_id, **kwargs)
        
        return StripeService._retry_with_backoff(_update)

stripe_service = StripeService()
