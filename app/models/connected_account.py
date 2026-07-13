from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, index=True)

    # Stripe identifiers
    stripe_account_id = Column(String, unique=True, index=True, nullable=False)  # acct_xxx

    # Account info
    email = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    account_type = Column(String, default="express")  # express | custom | standard

    # Onboarding / capability flags (synced from Stripe via webhook)
    charges_enabled = Column(Boolean, default=False)
    payouts_enabled = Column(Boolean, default=False)
    details_submitted = Column(Boolean, default=False)

    # Status: pending (not onboarded), active, restricted, disabled
    status = Column(String, default="pending")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship — one account can receive many transfers
    transfers = relationship("Transfer", back_populates="connected_account")
