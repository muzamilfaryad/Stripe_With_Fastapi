from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    stripe_product_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    
    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")

class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    stripe_price_id = Column(String, unique=True, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    currency = Column(String, default="usd")
    unit_amount = Column(Integer, nullable=False) # strictly integer cents
    recurring_interval = Column(String, nullable=True) # e.g., 'month', 'year'. If null, it's one-time
    active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="prices")
