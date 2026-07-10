from pydantic import BaseModel, Field
from typing import Optional

class CheckoutRequest(BaseModel):
    customer_id: int = Field(gt=0, description="Customer ID")
    amount: float = Field(gt=0, le=999999.99, description="Amount in dollars (e.g., 10.99)")
    product_name: str = Field(min_length=1, max_length=200, description="Product name for checkout")
    currency: str = Field(default="usd", pattern="^[a-z]{3}$", description="ISO 4217 currency code")

class CheckoutResponse(BaseModel):
    session_id: str
    url: str
