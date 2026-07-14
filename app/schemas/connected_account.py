from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class ConnectedAccountCreate(BaseModel):
    email: Optional[str] = Field(None, description="Vendor/seller email address")
    display_name: Optional[str] = Field(None, description="Business or person display name")
    account_type: str = Field(default="express", description="Stripe account type: express | custom | standard")


class ConnectedAccountResponse(BaseModel):
    id: int
    stripe_account_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    account_type: str

    # Onboarding status
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool
    status: str

    # Balance tracking
    balance_cents: int = Field(default=0, description="Total amount transferred to this account (in cents)")
    balance: Optional[float] = Field(None, description="Total amount transferred to this account (in dollars)")

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OnboardingLinkResponse(BaseModel):
    account_id: int
    stripe_account_id: str
    onboarding_url: str
    message: str
