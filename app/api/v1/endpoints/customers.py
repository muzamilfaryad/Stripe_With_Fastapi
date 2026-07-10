from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.services.customer_service import create_customer, get_customer_by_id

router = APIRouter()

@router.post(
    "/",
    response_model=CustomerResponse,
    summary="Create a new customer",
    description="""
    Create a customer in both local database and Stripe.
    
    **Features:**
    - Duplicate prevention (checks email)
    - Automatic Stripe customer creation
    - Links local customer to Stripe customer ID
    """,
    responses={
        200: {
            "description": "Customer created or already exists",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "customer@example.com",
                        "name": "John Doe",
                        "stripe_customer_id": "cus_ABC123xyz"
                    }
                }
            }
        },
        400: {"description": "Invalid request"}
    }
)
def create_new_customer(
    customer_in: CustomerCreate = Body(
        ...,
        examples={
            "with_name": {
                "summary": "Customer with name",
                "value": {
                    "email": "john.doe@example.com",
                    "name": "John Doe"
                }
            },
            "email_only": {
                "summary": "Email only",
                "value": {
                    "email": "jane@example.com"
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    try:
        customer = create_customer(db=db, customer_data=customer_in)
        return customer
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
    description="Retrieve a customer by their internal database ID",
    responses={
        200: {"description": "Customer found"},
        404: {"description": "Customer not found"}
    }
)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
