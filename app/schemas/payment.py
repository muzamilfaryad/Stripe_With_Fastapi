from pydantic import BaseModel
from typing import Optional

class PaymentCreateRequest(BaseModel):
    customer_id: int
    product_id: int # We lookup the price of this product backend

class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_id: int
