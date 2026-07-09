from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionIntentResponse
from app.services.subscription_service import SubscriptionService

router = APIRouter()

@router.post("/", response_model=SubscriptionIntentResponse)
def create_new_subscription(sub_data: SubscriptionCreate, db: Session = Depends(get_db)):
    try:
        service = SubscriptionService(db)
        return service.create_subscription_intent(sub_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/customer/{customer_id}", response_model=List[SubscriptionResponse])
def get_customer_subscriptions(customer_id: int, db: Session = Depends(get_db)):
    service = SubscriptionService(db)
    return service.get_subscriptions_for_customer(customer_id)
