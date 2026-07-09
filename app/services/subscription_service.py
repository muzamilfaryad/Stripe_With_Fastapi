import stripe
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.subscription import Subscription
from app.models.customer import Customer
from app.models.product import Price
from app.schemas.subscription import SubscriptionCreate, SubscriptionIntentResponse
from app.core.config import settings
from app.services.stripe_service import stripe_service

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def create_checkout_session(self, sub_data: SubscriptionCreate):
        customer = self.db.query(Customer).filter(Customer.id == sub_data.customer_id).first()
        price = self.db.query(Price).filter(Price.id == sub_data.price_id).first()
        
        if not customer or not price:
            raise ValueError("Customer or Price not found")
            
        db_sub = Subscription(
            customer_id=customer.id,
            price_id=price.id,
            status="pending",
        )
        self.db.add(db_sub)
        self.db.commit()
        self.db.refresh(db_sub)
            
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
        
        return session

    def create_subscription_intent(self, sub_data: SubscriptionCreate) -> SubscriptionIntentResponse:
        customer = self.db.query(Customer).filter(Customer.id == sub_data.customer_id).first()
        price = self.db.query(Price).filter(Price.id == sub_data.price_id).first()
        
        if not customer or not price:
            raise ValueError("Customer or Price not found")
            
        db_sub = Subscription(
            customer_id=customer.id,
            price_id=price.id,
            stripe_customer_id=customer.stripe_customer_id,
            stripe_price_id=price.stripe_price_id,
            status="pending",
        )
        self.db.add(db_sub)
        self.db.commit()
        self.db.refresh(db_sub)
        
        try:
            stripe_sub = stripe_service.create_subscription(
                customer_id=customer.stripe_customer_id,
                price_id=price.stripe_price_id,
                metadata={"client_reference_id": str(db_sub.id)}
            )
            
            db_sub.stripe_subscription_id = stripe_sub.id
            db_sub.status = stripe_sub.status
            
            # Safely access period fields (may not exist in newer API versions)
            period_start = getattr(stripe_sub, 'current_period_start', None)
            period_end = getattr(stripe_sub, 'current_period_end', None)
            db_sub.current_period_start = datetime.fromtimestamp(period_start) if period_start else None
            db_sub.current_period_end = datetime.fromtimestamp(period_end) if period_end else None
            self.db.commit()
            # In API versions >= 2025-03-31, payment_intent was replaced by confirmation_secret.
            confirmation_secret = getattr(stripe_sub.latest_invoice, 'confirmation_secret', None)
            client_secret = confirmation_secret.client_secret if confirmation_secret else ""

            return SubscriptionIntentResponse(
                client_secret=client_secret,
                subscription_id=db_sub.id
            )
        except Exception as e:
            raise e

    def get_subscriptions_for_customer(self, customer_id: int):
        return self.db.query(Subscription).filter(Subscription.customer_id == customer_id).all()
