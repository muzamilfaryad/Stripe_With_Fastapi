from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional, List

class PriceBase(BaseModel):
    currency: str = Field(default="usd", pattern="^[a-z]{3}$", description="ISO 4217 currency code")
    unit_amount: float = Field(gt=0, le=999999.99, description="Price in dollars (e.g., 10.99)")
    recurring_interval: Optional[str] = Field(None, pattern="^(month|year)$", description="Billing interval: 'month' or 'year'")
    
    @field_validator('unit_amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

class PriceCreate(PriceBase):
    pass

class PriceResponse(BaseModel):
    id: int
    stripe_price_id: str
    currency: str
    unit_amount_cents: int  # Stored in DB as cents
    recurring_interval: Optional[str] = None
    active: bool
    
    @computed_field
    @property
    def unit_amount(self) -> float:
        """Convert cents to dollars for API response"""
        return round(self.unit_amount_cents / 100, 2)
    
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Product name")
    description: Optional[str] = Field(None, max_length=1000, description="Product description")

class ProductCreate(ProductBase):
    prices: List[PriceCreate] = []

class ProductResponse(ProductBase):
    id: int
    stripe_product_id: str
    active: bool
    prices: List[PriceResponse] = []
    
    class Config:
        from_attributes = True
