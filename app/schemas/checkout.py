from pydantic import BaseModel
from typing import Optional

class CheckoutRequest(BaseModel):
    customer_id: int
    amount: float  # Amount in dollars
    product_name: str
    currency: str = "usd"

class CheckoutResponse(BaseModel):
    session_id: str
    url: str
