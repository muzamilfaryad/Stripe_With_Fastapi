from pydantic import BaseModel, Field, computed_field
from typing import Optional
from datetime import datetime


class PayoutCreate(BaseModel):
    """
    Schema for creating a manual payout.
    
    Expert pattern: Manual payouts are used when you want control over when 
    funds are transferred from your Stripe balance to your bank account.
    
    Reference: https://docs.stripe.com/api/payouts/create
    """
    stripe_account_id: str = Field(description="Stripe connected account ID (acct_xxx) to make payout from")
    amount: int = Field(
        gt=0, 
        ge=100,  # Minimum $1.00 (100 cents) for USD
        description="Payout amount in cents (e.g. 100 for $1.00). Minimum: 100 cents ($1.00) for USD"
    )
    currency: str = Field(default="usd", description="3-letter ISO currency code (lowercase)")
    method: str = Field(
        default="standard", 
        description="Payout speed: 'standard' (5-7 days, free) or 'instant' (30 min, 1% fee)"
    )
    destination: Optional[str] = Field(
        default=None,
        description="Bank account ID (ba_xxx) or card ID (card_xxx). If omitted, uses default. Must be a valid Stripe external account ID."
    )
    statement_descriptor: Optional[str] = Field(
        None,
        max_length=22,
        description="Text appearing on bank statement (max 22 chars)"
    )
    description: Optional[str] = Field(
        None,
        description="Internal description for your records"
    )


class PayoutResponse(BaseModel):
    """
    Schema for payout response following Stripe's payout object structure.
    
    Status transitions:
    - pending → in_transit → paid (success path)
    - pending → failed (error path)
    - pending → canceled (canceled before processing)
    """
    id: int
    stripe_payout_id: Optional[str] = None
    stripe_account_id: Optional[str] = None  # Stripe account ID (acct_xxx)
    
    amount_cents: int  # Stored in DB as cents
    currency: str
    method: str
    type: str
    status: str
    
    destination_id: Optional[str] = None
    arrival_date: Optional[datetime] = None
    automatic: bool
    
    description: Optional[str] = None
    statement_descriptor: Optional[str] = None
    
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    
    balance_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    @property
    def amount(self) -> float:
        """Convert cents to dollars for API response"""
        return round(self.amount_cents / 100, 2)

    class Config:
        from_attributes = True


class PayoutListResponse(BaseModel):
    """
    Paginated list response for payouts.
    Follows REST API best practices with metadata.
    """
    data: list[PayoutResponse]
    total: int
    skip: int
    limit: int
