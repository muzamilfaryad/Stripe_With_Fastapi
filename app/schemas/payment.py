from pydantic import BaseModel, Field
from typing import Optional, Literal

class PaymentCreateRequest(BaseModel):
    customer_id: int = Field(gt=0, description="Customer ID")
    product_id: int = Field(gt=0, description="Product ID")

class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_id: int

class RefundRequest(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Optional partial refund amount in dollars. If not provided, refunds full amount")
    reason: Optional[Literal["duplicate", "fraudulent", "requested_by_customer"]] = Field(None, description="Reason for the refund")

class RefundResponse(BaseModel):
    refund_id: str
    payment_id: int
    amount: float
    status: str
    message: str
