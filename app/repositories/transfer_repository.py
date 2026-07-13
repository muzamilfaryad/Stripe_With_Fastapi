from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.repositories.base import CRUDBase
from app.models.transfer import Transfer


class TransferCreate(BaseModel):
    connected_account_id: int
    amount_cents: int
    currency: str = "usd"
    stripe_charge_id: Optional[str] = None
    transfer_group: Optional[str] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = None
    status: str = "pending"


class TransferUpdate(BaseModel):
    stripe_transfer_id: Optional[str] = None
    status: Optional[str] = None
    failure_message: Optional[str] = None
    reversed_at: Optional[str] = None
    amount_reversed_cents: Optional[int] = None


class CRUDTransfer(CRUDBase[Transfer, TransferCreate, TransferUpdate]):

    def get_by_stripe_transfer_id(self, db: Session, stripe_transfer_id: str) -> Optional[Transfer]:
        return db.query(self.model).filter(
            Transfer.stripe_transfer_id == stripe_transfer_id
        ).first()

    def get_by_idempotency_key(self, db: Session, key: str) -> Optional[Transfer]:
        return db.query(self.model).filter(
            Transfer.idempotency_key == key
        ).first()

    def get_by_transfer_group(self, db: Session, transfer_group: str) -> List[Transfer]:
        return db.query(self.model).filter(
            Transfer.transfer_group == transfer_group
        ).all()

    def get_by_connected_account(
        self, db: Session, connected_account_id: int, skip: int = 0, limit: int = 100
    ) -> List[Transfer]:
        return db.query(self.model).filter(
            Transfer.connected_account_id == connected_account_id
        ).offset(skip).limit(limit).all()


transfer = CRUDTransfer(Transfer)
