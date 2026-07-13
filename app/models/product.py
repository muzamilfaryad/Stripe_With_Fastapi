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
    orders = relationship("Order", back_populates="product")

class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    stripe_price_id = Column(String, unique=True, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    currency = Column(String, default="usd")
    unit_amount_cents = Column(Integer, nullable=False)  # Always in cents for precision
    recurring_interval = Column(String, nullable=True) # e.g., 'month', 'year'. If null, it's one-time
    active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="prices")
    
    @property
    def unit_amount(self) -> float:
        """Get price in dollars"""
        return round(self.unit_amount_cents / 100, 2)
    
    @unit_amount.setter
    def unit_amount(self, dollars: float):
        """Set price from dollars (converts to cents)"""
        self.unit_amount_cents = int(dollars * 100)
