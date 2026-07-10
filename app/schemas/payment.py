from pydantic import BaseModel, Field
from typing import Optional

class PaymentCreateRequest(BaseModel):
    customer_id: int = Field(gt=0, description="Customer ID")
    product_id: int = Field(gt=0, description="Product ID")

class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_id: int
