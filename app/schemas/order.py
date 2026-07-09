from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    stripe_checkout_session_id: Optional[str]
    stripe_payment_intent_id: Optional[str]
    amount: int
    currency: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
