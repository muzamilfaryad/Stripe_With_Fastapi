import stripe
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.order import Order
from app.models.customer import Customer
from app.schemas.checkout import CheckoutRequest

def create_checkout_session(db: Session, checkout_req: CheckoutRequest):
    # Get the customer
    customer = db.query(Customer).filter(Customer.id == checkout_req.customer_id).first()
    if not customer:
        raise ValueError("Customer not found")
        
    # 1. Create Order in database FIRST (to prevent race conditions)
    db_order = Order(
        customer_id=customer.id,
        amount=checkout_req.amount,
        currency=checkout_req.currency,
        status='pending'
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
        
    # 2. Create Stripe Checkout Session with client_reference_id
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer=customer.stripe_customer_id,
        client_reference_id=str(db_order.id),
        line_items=[{
            'price_data': {
                'currency': checkout_req.currency,
                'unit_amount': int(checkout_req.amount * 100), # Convert dollars to cents for Stripe
                'product_data': {
                    'name': checkout_req.product_name,
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=settings.SUCCESS_URL + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=settings.CANCEL_URL,
    )
    
    # 3. Update Order with the session ID
    db_order.stripe_checkout_session_id = session.id
    db.commit()
    db.refresh(db_order)
    
    return session
