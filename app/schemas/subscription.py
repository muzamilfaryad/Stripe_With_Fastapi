from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SubscriptionCreate(BaseModel):
    customer_id: int
    price_id: int

class SubscriptionResponse(BaseModel):
    id: int
    customer_id: int
    price_id: int
    
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    
    status: str
    cancel_at_period_end: Optional[bool] = False
    
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class SubscriptionIntentResponse(BaseModel):
    client_secret: str
    subscription_id: int
