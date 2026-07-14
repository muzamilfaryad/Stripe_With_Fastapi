import uuid
import stripe
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.models.connected_account import ConnectedAccount
from app.models.transfer import Transfer
from app.repositories.connected_account_repository import connected_account as connected_account_repo
from app.repositories.transfer_repository import transfer as transfer_repo
from app.schemas.connected_account import ConnectedAccountCreate
from app.schemas.transfer import TransferCreate

logger = logging.getLogger(__name__)


# ============================================================================
# CONNECTED ACCOUNT SERVICE
# ============================================================================

def create_connected_account(db: Session, data: ConnectedAccountCreate) -> ConnectedAccount:
    """
    Create a Stripe Express connected account and persist it locally.
    Expert pattern: always store locally AFTER Stripe confirms creation.
    """
    try:
        # Build Stripe account creation payload
        create_params: dict = {
            "type": data.account_type,
            "capabilities": {
                "transfers": {"requested": True},
            },
        }
        if data.email:
            create_params["email"] = data.email
        if data.display_name:
            create_params["business_profile"] = {"name": data.display_name}

        stripe_account = stripe.Account.create(**create_params)

        logger.info(f"Stripe connected account created: {stripe_account.id}")

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating connected account: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

    # Persist to DB
    from app.repositories.connected_account_repository import ConnectedAccountCreate as RepoCreate
    db_account = connected_account_repo.create(db, obj_in=RepoCreate(
        stripe_account_id=stripe_account.id,
        email=data.email,
        display_name=data.display_name,
        account_type=data.account_type,
    ))

    logger.info(f"ConnectedAccount {db_account.id} created for Stripe account {stripe_account.id}")
    return db_account


def create_onboarding_link(
    db: Session,
    account_id: int,
    refresh_url: str,
    return_url: str,
) -> dict:
    """
    Generate a Stripe Express onboarding URL for the connected account.
    The vendor visits this URL to submit their business details.
    """
    db_account = connected_account_repo.get(db, account_id)
    if not db_account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    try:
        link = stripe.AccountLink.create(
            account=db_account.stripe_account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        logger.info(f"Onboarding link created for account {db_account.stripe_account_id}")
        return {
            "account_id": db_account.id,
            "stripe_account_id": db_account.stripe_account_id,
            "onboarding_url": link.url,
            "message": "Redirect the vendor to onboarding_url to complete onboarding.",
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating onboarding link: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


def sync_account_status(db: Session, account_id: int) -> ConnectedAccount:
    """
    Fetch the latest account status from Stripe and sync to DB.
    Call this after the vendor returns from the onboarding URL.
    """
    db_account = connected_account_repo.get(db, account_id)
    if not db_account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    try:
        stripe_account = stripe.Account.retrieve(db_account.stripe_account_id)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

    charges_enabled = stripe_account.charges_enabled
    payouts_enabled = stripe_account.payouts_enabled
    details_submitted = stripe_account.details_submitted

    new_status = "active" if (charges_enabled and payouts_enabled) else "pending"

    updated = connected_account_repo.update(db, db_obj=db_account, obj_in={
        "charges_enabled": charges_enabled,
        "payouts_enabled": payouts_enabled,
        "details_submitted": details_submitted,
        "status": new_status,
    })

    logger.info(
        f"Account {db_account.stripe_account_id} synced — "
        f"charges_enabled={charges_enabled}, payouts_enabled={payouts_enabled}"
    )
    return updated


# ============================================================================
# TRANSFER SERVICE
# ============================================================================

def create_transfer(db: Session, data: TransferCreate) -> Transfer:
    """
    Create a Stripe Transfer using the Separate Charges + Transfers pattern.

    Expert rules applied:
    1. Idempotency key prevents double-transfers.
    2. source_transaction ties transfer to original charge (no balance needed).
    3. transfer_group links charge + transfers for Stripe Dashboard grouping.
    4. DB record is created BEFORE Stripe API call (with status=pending),
       then updated with stripe_transfer_id on success.
    """
    
    # Convert dollars → cents (same pattern as Payment model)
    amount_cents = int(round(data.amount * 100))

    # Build a deterministic idempotency key
    idempotency_key = (
        f"transfer-{data.stripe_account_id}-"
        f"{data.transfer_group or uuid.uuid4().hex}-"
        f"{amount_cents}"
    )

    # Check for duplicate (idempotency guard)
    existing = transfer_repo.get_by_idempotency_key(db, idempotency_key)
    if existing:
        logger.info(f"Duplicate transfer request detected. Returning existing transfer {existing.id}.")
        return existing

    # Create DB record first (status=pending) — audit trail even if Stripe call fails
    from app.repositories.transfer_repository import TransferCreate as RepoCreate
    db_transfer = transfer_repo.create(db, obj_in=RepoCreate(
        connected_account_id=None,  # No longer using FK to local connected account
        stripe_account_id=data.stripe_account_id,  # Store Stripe account ID directly
        amount_cents=amount_cents,
        currency=data.currency,
        stripe_charge_id=data.stripe_charge_id,
        transfer_group=data.transfer_group,
        description=data.description,
        idempotency_key=idempotency_key,
        status="pending",
    ))

    # Build Stripe Transfer payload
    stripe_params: dict = {
        "amount": amount_cents,
        "currency": data.currency,
        "destination": data.stripe_account_id,
        "metadata": {
            "local_transfer_id": str(db_transfer.id),
            "stripe_account_id": data.stripe_account_id,
        },
    }
    if data.stripe_charge_id and data.stripe_charge_id.lower() not in ["null", "none", ""]:
        # CRITICAL: source_transaction prevents "Insufficient funds" errors
        stripe_params["source_transaction"] = data.stripe_charge_id
    if data.transfer_group:
        stripe_params["transfer_group"] = data.transfer_group
    if data.description:
        stripe_params["description"] = data.description

    try:
        stripe_transfer = stripe.Transfer.create(
            **stripe_params,
            idempotency_key=idempotency_key,
        )

        # Update DB with Stripe transfer ID
        db_transfer = transfer_repo.update(db, db_obj=db_transfer, obj_in={
            "stripe_transfer_id": stripe_transfer.id,
            "status": "pending",  # transfer.created webhook will confirm
        })

        logger.info(
            f"Transfer {db_transfer.id} created — Stripe ID: {stripe_transfer.id}, "
            f"Amount: {data.amount} {data.currency.upper()}, "
            f"Destination: {data.stripe_account_id}"
        )

    except stripe.error.InvalidRequestError as e:
        # Synchronous failure — mark immediately in DB
        transfer_repo.update(db, db_obj=db_transfer, obj_in={
            "status": "failed",
            "failure_message": str(e)[:500],
        })
        logger.error(f"Transfer {db_transfer.id} failed synchronously: {e}")
        raise HTTPException(status_code=400, detail=f"Transfer failed: {str(e)}")

    except stripe.error.StripeError as e:
        transfer_repo.update(db, db_obj=db_transfer, obj_in={
            "status": "failed",
            "failure_message": str(e)[:500],
        })
        logger.error(f"Stripe error on transfer {db_transfer.id}: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return db_transfer
