from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import CRUDBase
from app.models.payment import Payment
from pydantic import BaseModel

class PaymentCreate(BaseModel):
    order_id: int
    amount_cents: int
    currency: str = "usd"
    status: str = "pending"
    
class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None

class CRUDPayment(CRUDBase[Payment, PaymentCreate, PaymentUpdate]):
    def get_by_payment_intent(self, db: Session, payment_intent_id: str) -> Optional[Payment]:
        return db.query(self.model).filter(Payment.stripe_payment_intent_id == payment_intent_id).first()
    
    def get_by_checkout_session(self, db: Session, checkout_session_id: str) -> Optional[Payment]:
        return db.query(self.model).filter(Payment.stripe_checkout_session_id == checkout_session_id).first()
        
    def get_by_order(self, db: Session, order_id: int) -> Optional[Payment]:
        return db.query(self.model).filter(Payment.order_id == order_id).first()

payment = CRUDPayment(Payment)
