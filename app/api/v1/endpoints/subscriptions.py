from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import stripe
import logging
from datetime import datetime, timezone
from app.core.database import get_db
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionIntentResponse
from app.services.subscription_service import SubscriptionService
from app.models.subscription import Subscription

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=SubscriptionIntentResponse)
def create_new_subscription(sub_data: SubscriptionCreate, db: Session = Depends(get_db)):
    try:
        service = SubscriptionService(db)
        return service.create_subscription_intent(sub_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[SubscriptionResponse])
def get_all_subscriptions(db: Session = Depends(get_db)):
    """
    Get all subscriptions in the system.
    Useful for testing and admin purposes.
    """
    subscriptions = db.query(Subscription).all()
    return subscriptions

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(subscription_id: str, db: Session = Depends(get_db)):
    """
    Get a specific subscription by ID.
    """
    if subscription_id.isdigit():
        subscription = db.query(Subscription).filter(Subscription.id == int(subscription_id)).first()
    else:
        subscription = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
        
    if not subscription:
        raise HTTPException(status_code=404, detail=f"Subscription {subscription_id} not found")
    return subscription

@router.get("/customer/{customer_id}", response_model=List[SubscriptionResponse])
def get_customer_subscriptions(customer_id: int, db: Session = Depends(get_db)):
    """
    Get all subscriptions for a customer.
    Automatically syncs from Stripe to ensure data is up-to-date.
    """
    # Get local subscriptions
    service = SubscriptionService(db)
    subscriptions = service.get_subscriptions_for_customer(customer_id)
    
    # Sync each subscription from Stripe to get latest status
    for db_sub in subscriptions:
        if db_sub.stripe_subscription_id:
            try:
                # Fetch latest data from Stripe
                stripe_sub = stripe.Subscription.retrieve(db_sub.stripe_subscription_id)
                
                # Update local subscription with Stripe data
                db_sub.status = stripe_sub.status
                db_sub.cancel_at_period_end = stripe_sub.cancel_at_period_end
                
                # Update period dates
                if hasattr(stripe_sub, 'current_period_start') and stripe_sub.current_period_start:
                    db_sub.current_period_start = datetime.fromtimestamp(
                        stripe_sub.current_period_start, tz=timezone.utc
                    )
                
                if hasattr(stripe_sub, 'current_period_end') and stripe_sub.current_period_end:
                    db_sub.current_period_end = datetime.fromtimestamp(
                        stripe_sub.current_period_end, tz=timezone.utc
                    )
                
                # Update trial dates if present
                if hasattr(stripe_sub, 'trial_start') and stripe_sub.trial_start:
                    db_sub.trial_start = datetime.fromtimestamp(
                        stripe_sub.trial_start, tz=timezone.utc
                    )
                
                if hasattr(stripe_sub, 'trial_end') and stripe_sub.trial_end:
                    db_sub.trial_end = datetime.fromtimestamp(
                        stripe_sub.trial_end, tz=timezone.utc
                    )
                
                logger.info(f"✅ Synced subscription {db_sub.id} from Stripe. Status: {stripe_sub.status}")
                
            except stripe.error.StripeError as e:
                # Log error but don't fail the entire request
                logger.warning(f"⚠️ Could not sync subscription {db_sub.id} from Stripe: {str(e)}")
                # Return local data even if Stripe sync fails
                continue
            except Exception as e:
                logger.warning(f"⚠️ Unexpected error syncing subscription {db_sub.id}: {str(e)}")
                continue
    
    # Commit all updates at once
    try:
        db.commit()
        # Refresh all subscriptions to get updated data
        for sub in subscriptions:
            db.refresh(sub)
    except Exception as e:
        logger.error(f"Error committing subscription updates: {str(e)}")
        db.rollback()
    
    return subscriptions

@router.delete("/{subscription_id}", response_model=SubscriptionResponse)
def cancel_subscription(
    subscription_id: str,
    cancel_immediately: bool = False,
    db: Session = Depends(get_db)
):
    """
    Cancel a subscription.
    
    Args:
        subscription_id: Local subscription ID to cancel
        cancel_immediately: If True, cancels immediately. If False (default), cancels at period end.
    
    Returns:
        Updated subscription with cancellation status
    """
    try:
        service = SubscriptionService(db)
        updated_subscription = service.cancel_subscription(subscription_id, cancel_immediately)
        return updated_subscription
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error canceling subscription {subscription_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
