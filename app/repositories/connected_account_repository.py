from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.repositories.base import CRUDBase
from app.models.connected_account import ConnectedAccount


class ConnectedAccountCreate(BaseModel):
    stripe_account_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    account_type: str = "express"


class ConnectedAccountUpdate(BaseModel):
    charges_enabled: Optional[bool] = None
    payouts_enabled: Optional[bool] = None
    details_submitted: Optional[bool] = None
    status: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None


class CRUDConnectedAccount(CRUDBase[ConnectedAccount, ConnectedAccountCreate, ConnectedAccountUpdate]):

    def get_by_stripe_account_id(self, db: Session, stripe_account_id: str) -> Optional[ConnectedAccount]:
        return db.query(self.model).filter(
            ConnectedAccount.stripe_account_id == stripe_account_id
        ).first()

    def get_active_accounts(self, db: Session) -> List[ConnectedAccount]:
        return db.query(self.model).filter(
            ConnectedAccount.status == "active"
        ).all()

    def get_onboarded_accounts(self, db: Session) -> List[ConnectedAccount]:
        """Return accounts where onboarding is fully complete."""
        return db.query(self.model).filter(
            ConnectedAccount.charges_enabled == True,
            ConnectedAccount.payouts_enabled == True,
        ).all()


connected_account = CRUDConnectedAccount(ConnectedAccount)
