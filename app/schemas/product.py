from pydantic import BaseModel, computed_field
from typing import Optional, List

class PriceBase(BaseModel):
    currency: str = "usd"
    unit_amount: float
    recurring_interval: Optional[str] = None # 'month', 'year' or None

class PriceCreate(PriceBase):
    pass

class PriceResponse(PriceBase):
    id: int
    stripe_price_id: str
    active: bool
    
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProductCreate(ProductBase):
    prices: List[PriceCreate] = []

class ProductResponse(ProductBase):
    id: int
    stripe_product_id: str
    active: bool
    prices: List[PriceResponse] = []
    
    class Config:
        from_attributes = True
