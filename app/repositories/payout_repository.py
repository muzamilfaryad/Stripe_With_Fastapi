from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.repositories.base import CRUDBase
from app.models.payout import Payout


class PayoutCreate(BaseModel):
    stripe_account_id: Optional[str] = None  # Stripe account ID (acct_xxx)
    amount_cents: int
    currency: str = "usd"
    method: str = "standard"
    type: str = "bank_account"
    status: str = "pending"
    destination_id: Optional[str] = None
    automatic: bool = False
    description: Optional[str] = None
    statement_descriptor: Optional[str] = None
    idempotency_key: Optional[str] = None

class PayoutUpdate(BaseModel):
    stripe_payout_id: Optional[str] = None
    status: Optional[str] = None
    arrival_date: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    balance_transaction_id: Optional[str] = None


class CRUDPayout(CRUDBase[Payout, PayoutCreate, PayoutUpdate]):
    """
    Repository for Payout operations following the same pattern as TransferRepository.
    Provides database access methods with proper indexing and query optimization.
    """

    def get_by_stripe_payout_id(self, db: Session, stripe_payout_id: str) -> Optional[Payout]:
        """Retrieve payout by Stripe payout ID (po_xxx)"""
        return db.query(self.model).filter(
            Payout.stripe_payout_id == stripe_payout_id
        ).first()

    def get_by_idempotency_key(self, db: Session, key: str) -> Optional[Payout]:
        """Retrieve payout by idempotency key (prevents duplicates)"""
        return db.query(self.model).filter(
            Payout.idempotency_key == key
        ).first()

    def get_by_status(
        self, 
        db: Session, 
        status: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Payout]:
        """Get all payouts with a specific status (pending, paid, failed, etc.)"""
        return db.query(self.model).filter(
            Payout.status == status
        ).offset(skip).limit(limit).all()

    def get_by_method(
        self, 
        db: Session, 
        method: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Payout]:
        """Get payouts by method (standard or instant)"""
        return db.query(self.model).filter(
            Payout.method == method
        ).offset(skip).limit(limit).all()

    def get_automatic_payouts(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Payout]:
        """Get all automatic payouts"""
        return db.query(self.model).filter(
            Payout.automatic == True
        ).offset(skip).limit(limit).all()

    def get_manual_payouts(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Payout]:
        """Get all manual payouts"""
        return db.query(self.model).filter(
            Payout.automatic == False
        ).offset(skip).limit(limit).all()


# Singleton instance
payout = CRUDPayout(Payout)
