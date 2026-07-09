from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.services.customer_service import create_customer, get_customer_by_id

router = APIRouter()

@router.post("/", response_model=CustomerResponse)
def create_new_customer(customer_in: CustomerCreate, db: Session = Depends(get_db)):
    try:
        customer = create_customer(db=db, customer_data=customer_in)
        return customer
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
