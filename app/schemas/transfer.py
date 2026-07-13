from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TransferCreate(BaseModel):
    connected_account_id: int = Field(gt=0, description="Local DB ID of the connected account")
    amount: float = Field(gt=0, description="Transfer amount in dollars (e.g. 85.00)")
    currency: str = Field(default="usd", description="3-letter ISO currency code")
    stripe_charge_id: Optional[str] = Field(
        None,
        description="Original Stripe charge ID (ch_xxx or py_xxx). Strongly recommended — ties transfer to source charge."
    )
    transfer_group: Optional[str] = Field(
        None,
        description="Group identifier to link charge + transfers (e.g. ORDER_123 or SUB_456)"
    )
    description: Optional[str] = Field(None, description="Internal description for this transfer")


class TransferResponse(BaseModel):
    id: int
    stripe_transfer_id: Optional[str] = None
    connected_account_id: int
    stripe_charge_id: Optional[str] = None
    transfer_group: Optional[str] = None

    amount: float           # in dollars (property from model)
    amount_reversed: float  # in dollars
    currency: str
    status: str

    description: Optional[str] = None
    failure_message: Optional[str] = None
    reversed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransferReverseRequest(BaseModel):
    amount: Optional[float] = Field(
        None,
        gt=0,
        description="Amount to reverse in dollars. If omitted, reverses the full transfer."
    )
    description: Optional[str] = Field(None, description="Reason for the reversal")
