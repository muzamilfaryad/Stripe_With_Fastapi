import stripe
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate
import logging

logger = logging.getLogger(__name__)

def create_customer(db: Session, customer_data: CustomerCreate) -> Customer:
    """
    Create a customer with duplicate prevention and atomic transaction handling.
    
    Strategy:
    1. Check if customer already exists locally
    2. Check if customer exists in Stripe
    3. Create in Stripe if needed
    4. Save to database
    """
    
    # 1. Check if customer already exists in our database
    existing_customer = db.query(Customer).filter(Customer.email == customer_data.email).first()
    if existing_customer:
        logger.info(f"Customer with email {customer_data.email} already exists (ID: {existing_customer.id})")
        return existing_customer
    
    try:
        # 2. Check if customer exists in Stripe by email
        stripe_customers = stripe.Customer.list(email=customer_data.email, limit=1)
        
        if stripe_customers.data:
            # Customer exists in Stripe, use that
            stripe_customer = stripe_customers.data[0]
            logger.info(f"Found existing Stripe customer {stripe_customer.id} for email {customer_data.email}")
        else:
            # 3. Create new customer in Stripe
            stripe_customer = stripe.Customer.create(
                email=customer_data.email,
                name=customer_data.name
            )
            logger.info(f"Created new Stripe customer {stripe_customer.id} for email {customer_data.email}")
        
        # 4. Save to our database
        db_customer = Customer(
            email=customer_data.email,
            name=customer_data.name,
            stripe_customer_id=stripe_customer.id
        )
        db.add(db_customer)
        db.commit()
        db.refresh(db_customer)
        
        logger.info(f"Successfully created local customer {db_customer.id} linked to Stripe customer {stripe_customer.id}")
        
        return db_customer
        
    except stripe.error.InvalidRequestError as e:
        db.rollback()
        logger.error(f"Stripe invalid request when creating customer: {str(e)}")
        raise ValueError(f"Invalid customer data: {str(e)}")
        
    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Stripe error when creating customer: {str(e)}")
        raise ValueError(f"Payment system error: {str(e)}")
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error when creating customer: {str(e)}")
        raise ValueError("Database error occurred")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error when creating customer: {str(e)}", exc_info=True)
        raise

def get_customer_by_id(db: Session, customer_id: int) -> Customer:
    """Get customer by internal database ID."""
    return db.query(Customer).filter(Customer.id == customer_id).first()

def get_customer_by_email(db: Session, email: str) -> Customer:
    """Get customer by email address."""
    return db.query(Customer).filter(Customer.email == email).first()

def get_customer_by_stripe_id(db: Session, stripe_customer_id: str) -> Customer:
    """Get customer by Stripe customer ID."""
    return db.query(Customer).filter(Customer.stripe_customer_id == stripe_customer_id).first()
