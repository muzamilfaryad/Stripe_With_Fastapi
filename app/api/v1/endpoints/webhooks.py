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
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe signature")
        
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    try:
        process_webhook_event(db, event)
    except Exception as e:
        logger.error(f"Unhandled error processing event {event.id} ({event.type}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing webhook event: {str(e)}")
    
    return {"status": "success"}
