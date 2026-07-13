from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    stripe_payment_intent_id = Column(String, unique=True, index=True, nullable=True)
    stripe_checkout_session_id = Column(String, unique=True, index=True, nullable=True)
    
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="usd")
    status = Column(String, default="pending")  # pending, succeeded, failed, refunded, partially_refunded, canceled
    
    # Idempotency key for preventing duplicate payment creation
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    order = relationship("Order", back_populates="payment")
    
    @property
    def amount(self) -> float:
        """Get amount in dollars"""
        return round(self.amount_cents / 100, 2)
    
    @amount.setter
    def amount(self, dollars: float):
        """Set amount from dollars (converts to cents)"""
        self.amount_cents = int(dollars * 100)
