from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
import stripe
import logging
from app.core.database import get_db
from app.core.config import settings
from app.services.webhook_service import process_webhook_event

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: Session = Depends(get_db)):
    logger.info("=" * 80)
    logger.info("🎯 WEBHOOK REQUEST RECEIVED")
    logger.info(f"Stripe-Signature Header: {stripe_signature}")
    
    if not stripe_signature:
        logger.error("❌ Missing stripe signature")
        raise HTTPException(status_code=400, detail="Missing stripe signature")
        
    payload = await request.body()
    logger.info(f"📦 Payload length: {len(payload)} bytes")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"✅ Event verified: {event.type} (ID: {event.id})")
    except ValueError as e:
        # Invalid payload
        logger.error(f"❌ Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"❌ Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    try:
        logger.info(f"⚙️ Processing event: {event.type}")
        process_webhook_event(db, event)
        logger.info(f"✅ Successfully processed event: {event.type}")
    except Exception as e:
        logger.error(f"Unhandled error processing event {event.id} ({event.type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing webhook event: {str(e)}")
    
    logger.info("=" * 80)
    return {"status": "success"}
