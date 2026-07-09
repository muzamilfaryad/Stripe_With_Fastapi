from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    price_id = Column(Integer, ForeignKey("prices.id"), nullable=False)
    
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    
    status = Column(String, default="active") # active, past_due, canceled, etc.
    cancel_at_period_end = Column(Boolean, default=False)
    
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Optional relationships if you want to navigate
    # customer = relationship("Customer")
    # price = relationship("Price")
