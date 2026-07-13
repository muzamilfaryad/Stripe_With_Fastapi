from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.transfer import TransferCreate, TransferResponse, TransferReverseRequest
from app.repositories.transfer_repository import transfer as transfer_repo
from app.services.transfer_service import create_transfer, reverse_transfer

router = APIRouter()


@router.post(
    "",
    response_model=TransferResponse,
    status_code=201,
    summary="Create a transfer",
    description=(
        "Transfer funds from your platform Stripe balance to a connected account. "
        "Uses the **Separate Charges + Transfers** pattern. "
        "Provide `stripe_charge_id` (source_transaction) to tie the transfer to an existing charge — "
        "this prevents balance insufficiency errors. "
        "Idempotent: duplicate requests with the same account + group + amount return the existing transfer."
    ),
)
def create_transfer_endpoint(data: TransferCreate, db: Session = Depends(get_db)):
    return create_transfer(db, data)


@router.get(
    "",
    response_model=List[TransferResponse],
    summary="List transfers",
    description="List all transfers. Filter by connected account or transfer group.",
)
def list_transfers(
    connected_account_id: Optional[int] = Query(None, description="Filter by connected account ID"),
    transfer_group: Optional[str] = Query(None, description="Filter by transfer group (e.g. ORDER_123)"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    if connected_account_id:
        return transfer_repo.get_by_connected_account(db, connected_account_id, skip=skip, limit=limit)
    if transfer_group:
        return transfer_repo.get_by_transfer_group(db, transfer_group)
    return transfer_repo.get_multi(db, skip=skip, limit=limit)


@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
    summary="Get transfer by ID",
)
def get_transfer(transfer_id: int, db: Session = Depends(get_db)):
    db_transfer = transfer_repo.get(db, transfer_id)
    if not db_transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return db_transfer


@router.post(
    "/{transfer_id}/reverse",
    response_model=TransferResponse,
    summary="Reverse a transfer",
    description=(
        "Reverse a transfer — fully or partially. "
        "Funds are returned from the connected account back to your platform balance. "
        "Omit `amount` to reverse the full transfer."
    ),
)
def reverse_transfer_endpoint(
    transfer_id: int,
    data: TransferReverseRequest,
    db: Session = Depends(get_db),
):
    return reverse_transfer(db, transfer_id, data)
