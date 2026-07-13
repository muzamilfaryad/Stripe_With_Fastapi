from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.schemas.connected_account import (
    ConnectedAccountCreate,
    ConnectedAccountResponse,
    OnboardingLinkResponse,
)
from app.repositories.connected_account_repository import connected_account as ca_repo
from app.services.transfer_service import (
    create_connected_account,
    create_onboarding_link,
    sync_account_status,
)

router = APIRouter()


@router.post(
    "",
    response_model=ConnectedAccountResponse,
    status_code=201,
    summary="Create a connected account",
    description=(
        "Creates a Stripe Express connected account for a vendor/seller "
        "and persists it locally. After creation, call the onboarding-link "
        "endpoint to get the URL for the vendor to complete onboarding."
    ),
)
def create_account(data: ConnectedAccountCreate, db: Session = Depends(get_db)):
    return create_connected_account(db, data)


@router.post(
    "/{account_id}/onboarding-link",
    response_model=OnboardingLinkResponse,
    summary="Generate Express onboarding link",
    description=(
        "Returns a Stripe-hosted onboarding URL. Redirect the vendor to this "
        "URL so they can submit their business details. Once they complete it, "
        "Stripe fires `account.updated` and your webhook will sync the status."
    ),
)
def get_onboarding_link(
    account_id: int,
    db: Session = Depends(get_db),
    refresh_url: str = Query(
        default=f"{settings.CANCEL_URL}",
        description="URL to redirect to if onboarding link expires",
    ),
    return_url: str = Query(
        default=f"{settings.SUCCESS_URL}",
        description="URL to redirect to after onboarding completes",
    ),
):
    result = create_onboarding_link(db, account_id, refresh_url, return_url)
    return OnboardingLinkResponse(**result)


@router.get(
    "/{account_id}",
    response_model=ConnectedAccountResponse,
    summary="Get connected account (syncs status from Stripe)",
    description="Fetches the account from DB and syncs the latest onboarding status from Stripe.",
)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return sync_account_status(db, account_id)


@router.get(
    "",
    response_model=List[ConnectedAccountResponse],
    summary="List all connected accounts",
)
def list_accounts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    return ca_repo.get_multi(db, skip=skip, limit=limit)
