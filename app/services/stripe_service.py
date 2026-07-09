import stripe
from typing import Optional, Dict, Any
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, str] = None) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata or {},
            # For modern Stripe integrations, we enable automatic_payment_methods
            automatic_payment_methods={"enabled": True},
        )
        
    @staticmethod
    def get_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    @staticmethod
    def create_customer(email: str, name: str) -> stripe.Customer:
        return stripe.Customer.create(email=email, name=name)

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    @staticmethod
    def create_subscription(customer_id: str, price_id: str, metadata: Dict[str, str] = None) -> stripe.Subscription:
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            expand=["latest_invoice.confirmation_secret"],
            metadata=metadata or {},
        )

stripe_service = StripeService()
