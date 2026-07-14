from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric
from sqlalchemy.sql import func
from app.core.database import Base


class Payout(Base):
    """
    Stripe Payout model - represents funds transferred from Stripe balance to bank account.
    
    Key differences from Transfer:
    - Payouts move money from YOUR Stripe balance to YOUR bank account
    - Transfers move money from YOUR balance to a CONNECTED ACCOUNT
    
    Reference: https://docs.stripe.com/api/payouts
    """
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)

    # Stripe identifier (po_xxx) - null until Stripe confirms
    stripe_payout_id = Column(String, unique=True, index=True, nullable=True)

    # Stripe connected account ID (acct_xxx) - for payouts on connected accounts
    stripe_account_id = Column(String, index=True, nullable=True)

    # Amount stored in dollars (e.g. 10.00 for $10.00)
    amount = Column(Numeric(precision=12, scale=2), nullable=False)
    currency = Column(String, default="usd", nullable=False)

    # Payout method: standard (5-7 business days) or instant (30 minutes)
    method = Column(String, default="standard", nullable=False)  # standard | instant

    # Type of payout: bank_account | card
    type = Column(String, default="bank_account", nullable=False)

    # Status lifecycle: pending → paid | in_transit | failed | canceled
    # pending: Created but not yet submitted to bank
    # in_transit: Submitted to bank, funds in transit
    # paid: Successfully paid out
    # failed: Payout failed (insufficient funds, invalid account, etc.)
    # canceled: Payout was canceled before completion
    status = Column(String, default="pending", nullable=False)

    # Destination bank account or card ID (ba_xxx or card_xxx)
    destination_id = Column(String, nullable=True)

    # Expected arrival date (timestamp)
    arrival_date = Column(DateTime(timezone=True), nullable=True)

    # Automatic vs manual payout
    automatic = Column(Boolean, default=False, nullable=False)

    # Description (internal use)
    description = Column(String, nullable=True)

    # Statement descriptor (appears on bank statement, max 22 chars)
    statement_descriptor = Column(String, nullable=True)

    # Error info (populated if payout fails)
    failure_code = Column(String, nullable=True)
    failure_message = Column(Text, nullable=True)

    # Balance transaction ID from Stripe (txn_xxx)
    balance_transaction_id = Column(String, nullable=True)

    # Idempotency key - prevents duplicate payouts
    idempotency_key = Column(String, unique=True, index=True, nullable=True)


    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


