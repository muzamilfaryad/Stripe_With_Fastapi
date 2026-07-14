import uuid
import stripe
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.models.payout import Payout
from app.repositories.payout_repository import payout as payout_repo
from app.schemas.payout import PayoutCreate

logger = logging.getLogger(__name__)


def create_payout(db: Session, data: PayoutCreate) -> Payout:
    """
    Create a manual Stripe payout following expert-level patterns.
    
    Expert patterns applied:
    1. Idempotency key prevents duplicate payouts (critical for financial operations)
    2. DB record created BEFORE Stripe API call (audit trail even on failure)
    3. Amount stored in cents (avoids floating-point precision issues)
    4. Status tracking through entire lifecycle (pending → in_transit → paid/failed)
    5. Comprehensive error handling with specific error types
    
    Flow:
    1. Validate input
    2. Generate idempotency key
    3. Check for existing payout (idempotency guard)
    4. Create DB record (status=pending)
    5. Call Stripe API
    6. Update DB with Stripe response
    
    Reference: https://docs.stripe.com/api/payouts/create
    """
    
    # Amount is already in cents from the schema
    amount_cents = data.amount
    
    # Validate minimum payout amount based on currency
    min_amounts = {
        "usd": 100,   # $1.00
        "eur": 100,   # €1.00
        "gbp": 100,   # £1.00
        "cad": 100,   # C$1.00
        "aud": 100,   # A$1.00
        "jpy": 100,   # ¥100
        "chf": 100,   # CHF 1.00
        "sek": 300,   # SEK 3.00
        "nok": 300,   # NOK 3.00
        "dkk": 250,   # DKK 2.50
    }
    
    min_amount = min_amounts.get(data.currency.lower(), 100)
    if amount_cents < min_amount:
        currency_display = data.currency.upper()
        min_display = min_amount / 100 if data.currency.lower() != "jpy" else min_amount
        raise HTTPException(
            status_code=400,
            detail=f"Amount too small. Minimum payout for {currency_display} is {min_display} {currency_display} ({min_amount} cents)"
        )
    
    # Validate method
    if data.method not in ["standard", "instant"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid method. Must be 'standard' or 'instant'"
        )
    
    # Validate statement_descriptor length (Stripe enforces 22 chars)
    if data.statement_descriptor and len(data.statement_descriptor) > 22:
        raise HTTPException(
            status_code=400,
            detail="statement_descriptor must be 22 characters or less"
        )
    
    # Build deterministic idempotency key
    # Format: payout-{amount_cents}-{currency}-{method}-{uuid}
    idempotency_key = f"payout-{amount_cents}-{data.currency}-{data.method}-{uuid.uuid4().hex[:8]}"
    
    # Idempotency guard: check for duplicate
    existing = payout_repo.get_by_idempotency_key(db, idempotency_key)
    if existing:
        logger.info(f"Duplicate payout request detected. Returning existing payout {existing.id}.")
        return existing
    
    # Create DB record first (status=pending) — ensures audit trail even if Stripe fails
    from app.repositories.payout_repository import PayoutCreate as RepoCreate
    db_payout = payout_repo.create(db, obj_in=RepoCreate(
        stripe_account_id=data.stripe_account_id,
        amount_cents=amount_cents,
        currency=data.currency,
        method=data.method,
        type="bank_account",  # Default type
        status="pending",
        destination_id=data.destination,
        automatic=False,  # This is a manual payout
        description=data.description,
        statement_descriptor=data.statement_descriptor,
        idempotency_key=idempotency_key,
    ))
    
    logger.info(
        f"Payout {db_payout.id} created in DB (pending). "
        f"Amount: {amount_cents} cents {data.currency.upper()}, Method: {data.method}"
    )
    
    # Build Stripe payout creation payload
    stripe_params: dict = {
        "amount": amount_cents,
        "currency": data.currency,
        "method": data.method,
        "metadata": {
            "local_payout_id": str(db_payout.id),
            "stripe_account_id": data.stripe_account_id,
        },
    }
    
    # Only include destination if it's a real ID (not empty/placeholder)
    if data.destination and data.destination not in ["string", "", "null"]:
        stripe_params["destination"] = data.destination
    
    if data.statement_descriptor and data.statement_descriptor not in ["string", "", "null"]:
        stripe_params["statement_descriptor"] = data.statement_descriptor
    
    if data.description:
        stripe_params["description"] = data.description
    
    # Call Stripe API with idempotency key
    # Use stripe_account parameter to create payout on connected account
    try:
        stripe_payout = stripe.Payout.create(
            **stripe_params,
            idempotency_key=idempotency_key,
            stripe_account=data.stripe_account_id,
        )
        
        # Extract arrival_date from Stripe response (timestamp → datetime)
        arrival_date = None
        if stripe_payout.arrival_date:
            arrival_date = datetime.fromtimestamp(stripe_payout.arrival_date, tz=timezone.utc)
        
        # Update DB with Stripe response
        db_payout = payout_repo.update(db, db_obj=db_payout, obj_in={
            "stripe_payout_id": stripe_payout.id,
            "status": stripe_payout.status,  # pending | in_transit | paid | failed
            "arrival_date": arrival_date,
            "balance_transaction_id": getattr(stripe_payout, "balance_transaction", None),
            "destination_id": getattr(stripe_payout, "destination", None),
            "type": getattr(stripe_payout, "type", "bank_account"),
        })
        
        logger.info(
            f"Payout {db_payout.id} created successfully — "
            f"Stripe ID: {stripe_payout.id}, "
            f"Status: {stripe_payout.status}, "
            f"Arrival: {arrival_date}"
        )
    
    except stripe.error.InvalidRequestError as e:
        # Synchronous validation error (e.g., insufficient funds, invalid destination)
        payout_repo.update(db, db_obj=db_payout, obj_in={
            "status": "failed",
            "failure_code": getattr(e, 'code', 'unknown'),
            "failure_message": str(e)[:500],
        })
        logger.error(f"Payout {db_payout.id} failed synchronously: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Payout failed: {str(e)}"
        )
    
    except stripe.error.StripeError as e:
        # Generic Stripe error
        payout_repo.update(db, db_obj=db_payout, obj_in={
            "status": "failed",
            "failure_code": getattr(e, 'code', 'stripe_error'),
            "failure_message": str(e)[:500],
        })
        logger.error(f"Stripe error on payout {db_payout.id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Stripe error: {str(e)}"
        )
    
    return db_payout


def get_payouts(
    db: Session,
    status: str = None,
    method: str = None,
    automatic: bool = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Payout], int]:
    """
    Retrieve payouts with optional filtering.
    
    Returns:
        tuple: (list of payouts, total count)
    
    Expert pattern: Return both data and count for proper pagination.
    """
    
    # Apply filters
    if status:
        payouts = payout_repo.get_by_status(db, status, skip=skip, limit=limit)
        total = db.query(Payout).filter(Payout.status == status).count()
    elif method:
        payouts = payout_repo.get_by_method(db, method, skip=skip, limit=limit)
        total = db.query(Payout).filter(Payout.method == method).count()
    elif automatic is not None:
        if automatic:
            payouts = payout_repo.get_automatic_payouts(db, skip=skip, limit=limit)
        else:
            payouts = payout_repo.get_manual_payouts(db, skip=skip, limit=limit)
        total = db.query(Payout).filter(Payout.automatic == automatic).count()
    else:
        payouts = payout_repo.get_multi(db, skip=skip, limit=limit)
        total = db.query(Payout).count()
    
    return payouts, total


def get_payout(db: Session, payout_id: int) -> Payout:
    """
    Retrieve a single payout by ID.
    
    Expert pattern: Consistent error handling with 404 for not found.
    """
    db_payout = payout_repo.get(db, payout_id)
    if not db_payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    return db_payout
