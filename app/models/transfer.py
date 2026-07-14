from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)

    # Stripe identifier
    stripe_transfer_id = Column(String, unique=True, index=True, nullable=True)  # tr_xxx (null until Stripe confirms)

    # FK to our connected account record (deprecated - kept for backward compatibility)
    connected_account_id = Column(Integer, ForeignKey("connected_accounts.id"), nullable=True)

    # Stripe account ID (new field - replaces connected_account_id FK)
    stripe_account_id = Column(String, index=True, nullable=True)  # acct_xxx

    # Source transaction — ties transfer to original charge (CRITICAL for Separate Charges+Transfers)
    stripe_charge_id = Column(String, index=True, nullable=True)   # ch_xxx or py_xxx

    # Grouping — links charge + all related transfers (e.g. ORDER_123 or SUB_456)
    transfer_group = Column(String, index=True, nullable=True)

    # Amount always stored in dollars natively
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="usd", nullable=False)

    # Status lifecycle: pending → paid → reversed | failed
    status = Column(String, default="pending", nullable=False)

    description = Column(String, nullable=True)

    # Error info (populated if transfer fails at API call time)
    failure_message = Column(Text, nullable=True)

    # Reversal tracking
    reversed_at = Column(DateTime(timezone=True), nullable=True)
    amount_reversed = Column(Numeric(10, 2), default=0)

    # Idempotency — prevents double-transfers (same key = same transfer)
    idempotency_key = Column(String, unique=True, index=True, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    connected_account = relationship("ConnectedAccount", back_populates="transfers")
