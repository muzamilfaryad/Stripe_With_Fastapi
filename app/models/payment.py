from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    stripe_payment_intent_id = Column(String, unique=True, index=True, nullable=True)
    stripe_checkout_session_id = Column(String, unique=True, index=True, nullable=True)
    
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="usd")
    status = Column(String, default="pending")  # pending, succeeded, failed, refunded, partially_refunded, canceled
    
    # Idempotency key for preventing duplicate payment creation
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    order = relationship("Order", back_populates="payment")
