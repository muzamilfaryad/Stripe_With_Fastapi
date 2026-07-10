from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    status = Column(String, default="pending")  # pending, paid, failed, canceled, refunded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    payment = relationship("Payment", back_populates="order", uselist=False)
