from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.schemas.payout import PayoutCreate, PayoutResponse, PayoutListResponse
from app.services.payout_service import create_payout, get_payouts, get_payout

router = APIRouter()


@router.post(
    "",
    response_model=PayoutResponse,
    status_code=201,
    summary="Create a manual payout",
    description=(
        "Create a manual payout to transfer funds from your Stripe balance to your bank account. "
        "\n\n**Key features:**\n"
        "- **Idempotent**: Duplicate requests return the same payout\n"
        "- **Method options**: `standard` (5-7 days, free) or `instant` (30 min, 1% fee)\n"
        "- **Status tracking**: pending → in_transit → paid/failed\n"
        "- **Audit trail**: DB record created before Stripe call\n"
        "\n\n**Expert pattern**: This follows Stripe's recommended approach for manual payouts, "
        "storing amounts in cents to avoid floating-point precision issues, and using idempotency "
        "keys to prevent duplicate transfers.\n"
        "\n\n**Reference**: https://docs.stripe.com/api/payouts/create"
    ),
)
def create_payout_endpoint(
    data: PayoutCreate, 
    db: Session = Depends(get_db)
) -> PayoutResponse:
    """
    Create a manual payout.
    
    **Request body:**
    - `stripe_account_id`: Stripe connected account ID (acct_xxx) to make payout from
    - `amount`: Payout amount in cents (e.g., 100 for $1.00)
    - `currency`: 3-letter ISO code (default: "usd")
    - `method`: "standard" (free, 5-7 days) or "instant" (1% fee, 30 min)
    - `destination`: Optional bank account ID (ba_xxx) or card ID (card_xxx)
    - `statement_descriptor`: Optional text for bank statement (max 22 chars)
    - `description`: Optional internal description
    
    **Response:**
    Returns the created payout with:
    - `stripe_payout_id`: Stripe's payout ID (po_xxx)
    - `status`: pending, in_transit, paid, failed, or canceled
    - `arrival_date`: Expected arrival timestamp
    - Full payout details
    """
    return create_payout(db, data)


@router.get(
    "",
    response_model=PayoutListResponse,
    summary="List all payouts",
    description=(
        "Retrieve a paginated list of payouts with optional filtering. "
        "\n\n**Filters:**\n"
        "- `status`: Filter by status (pending, in_transit, paid, failed, canceled)\n"
        "- `method`: Filter by method (standard, instant)\n"
        "- `automatic`: Filter by automatic (true) or manual (false) payouts\n"
        "\n\n**Pagination:**\n"
        "- `skip`: Number of records to skip (default: 0)\n"
        "- `limit`: Max records to return (default: 100, max: 500)\n"
        "\n\n**Expert pattern**: Returns both data and total count for proper pagination UI."
    ),
)
def list_payouts_endpoint(
    status: Optional[str] = Query(
        None, 
        description="Filter by status: pending, in_transit, paid, failed, canceled"
    ),
    method: Optional[str] = Query(
        None,
        description="Filter by method: standard or instant"
    ),
    automatic: Optional[bool] = Query(
        None,
        description="Filter by automatic (true) or manual (false) payouts"
    ),
    skip: int = Query(
        default=0, 
        ge=0,
        description="Number of records to skip for pagination"
    ),
    limit: int = Query(
        default=100, 
        ge=1,
        le=500,
        description="Maximum number of records to return (max 500)"
    ),
    db: Session = Depends(get_db),
) -> PayoutListResponse:
    """
    List payouts with optional filtering and pagination.
    
    **Query parameters:**
    - `status`: Filter by payout status
    - `method`: Filter by payout method (standard/instant)
    - `automatic`: Filter by automatic vs manual payouts
    - `skip`: Pagination offset
    - `limit`: Page size (max 500)
    
    **Response:**
    Returns:
    - `data`: Array of payout objects
    - `total`: Total count (useful for pagination UI)
    - `skip`: Current offset
    - `limit`: Current page size
    
    **Examples:**
    - Get all payouts: `GET /api/v1/payouts`
    - Get pending payouts: `GET /api/v1/payouts?status=pending`
    - Get instant payouts: `GET /api/v1/payouts?method=instant`
    - Get page 2 (50 per page): `GET /api/v1/payouts?skip=50&limit=50`
    """
    payouts, total = get_payouts(
        db=db,
        status=status,
        method=method,
        automatic=automatic,
        skip=skip,
        limit=limit,
    )
    
    return PayoutListResponse(
        data=payouts,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{payout_id}",
    response_model=PayoutResponse,
    summary="Get a specific payout",
    description=(
        "Retrieve details of a specific payout by its local database ID. "
        "\n\n**Expert pattern**: Use this to check payout status, arrival date, "
        "and any failure information."
    ),
)
def get_payout_endpoint(
    payout_id: int,
    db: Session = Depends(get_db)
) -> PayoutResponse:
    """
    Get a specific payout by ID.
    
    **Path parameters:**
    - `payout_id`: Local database ID of the payout
    
    **Response:**
    Returns full payout details including:
    - Stripe payout ID (po_xxx)
    - Current status
    - Arrival date
    - Failure information (if applicable)
    - All metadata
    
    **Error responses:**
    - 404: Payout not found
    """
    return get_payout(db, payout_id)
