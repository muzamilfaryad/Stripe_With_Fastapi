import stripe
from sqlalchemy.orm import Session
from app.models.idempotency import IdempotencyKey
from app.repositories.payment_repository import payment as payment_repo
from app.repositories.order_repository import order as order_repo
from app.models.subscription import Subscription
import logging

logger = logging.getLogger(__name__)

def handle_payment_intent_succeeded(db: Session, event: stripe.Event):
    intent = event.data.object
    payment_intent_id = intent.id
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    if db_payment:
        payment_repo.update(db, db_obj=db_payment, obj_in={"status": "succeeded"})
        # Update related order
        db_order = order_repo.get(db, db_payment.order_id)
        if db_order:
            order_repo.update(db, db_obj=db_order, obj_in={"status": "paid"})
        logger.info(f"Payment {db_payment.id} marked as succeeded.")
    else:
        logger.warning(f"PaymentIntent {payment_intent_id} succeeded but no local Payment found.")

def handle_payment_intent_failed(db: Session, event: stripe.Event):
    intent = event.data.object
    payment_intent_id = intent.id
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    if db_payment:
        payment_repo.update(db, db_obj=db_payment, obj_in={"status": "failed"})
        db_order = order_repo.get(db, db_payment.order_id)
        if db_order:
            order_repo.update(db, db_obj=db_order, obj_in={"status": "failed"})
        logger.info(f"Payment {db_payment.id} marked as failed.")

from datetime import datetime, timezone

def handle_subscription_updated(db: Session, event: stripe.Event):
    subscription = event.data.object
    # Fallback to direct query for subscription since we didn't make a repo for it yet
    db_sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription.id).first()
    if db_sub:
        db_sub.status = subscription.status
        if getattr(subscription, 'current_period_end', None):
            db_sub.current_period_end = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
        db.commit()
        logger.info(f"Subscription {db_sub.id} updated to {subscription.status}.")

def handle_subscription_deleted(db: Session, event: stripe.Event):
    subscription = event.data.object
    db_sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription.id).first()
    if db_sub:
        db_sub.status = 'canceled'
        db.commit()
        logger.info(f"Subscription {db_sub.id} canceled.")

# Event Dispatcher Dictionary
EVENT_HANDLERS = {
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
}

def process_webhook_event(db: Session, event: stripe.Event):
    event_id = event.id
    
    # Idempotency Check
    existing_key = db.query(IdempotencyKey).filter(IdempotencyKey.key == event_id).first()
    if existing_key:
        logger.info(f"Event {event_id} already processed. Skipping.")
        return
        
    handler = EVENT_HANDLERS.get(event.type)
    if handler:
        logger.info(f"Dispatching event {event.type}")
        try:
            handler(db, event)
            # Record idempotency key after successful processing
            idempotency_key = IdempotencyKey(key=event_id)
            db.add(idempotency_key)
            db.commit()
        except Exception as e:
            logger.error(f"Error processing event {event.type}: {str(e)}")
            db.rollback()
            raise
    else:
        logger.debug(f"Unhandled event type: {event.type}")
