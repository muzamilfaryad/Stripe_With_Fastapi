import stripe
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate

def create_customer(db: Session, customer_data: CustomerCreate) -> Customer:
    # 1. Create in Stripe
    stripe_customer = stripe.Customer.create(
        email=customer_data.email,
        name=customer_data.name
    )
    
    # 2. Save to our database
    db_customer = Customer(
        email=customer_data.email,
        name=customer_data.name,
        stripe_customer_id=stripe_customer.id
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    
    return db_customer

def get_customer_by_id(db: Session, customer_id: int) -> Customer:
    return db.query(Customer).filter(Customer.id == customer_id).first()
