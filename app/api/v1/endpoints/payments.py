from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.payment import PaymentCreateRequest, PaymentIntentResponse
from app.repositories.product_repository import product as product_repo
from app.repositories.order_repository import order as order_repo, OrderCreate
from app.repositories.payment_repository import payment as payment_repo, PaymentCreate
from app.services.stripe_service import stripe_service

router = APIRouter()

from app.models.customer import Customer

@router.post("/", response_model=PaymentIntentResponse)
def create_payment(request: PaymentCreateRequest, db: Session = Depends(get_db)):
    # 0. Validate Customer
    db_customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 1. Validate Product & Price
    db_product = product_repo.get(db, request.product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # Find the active price for this product
    active_price = next((p for p in db_product.prices if p.active), None)
    if not active_price:
        raise HTTPException(status_code=400, detail="Product has no active price")
        
    amount_cents = active_price.unit_amount
    currency = active_price.currency

    try:
        # 2. Create Order
        db_order = order_repo.create(db, obj_in=OrderCreate(
            customer_id=request.customer_id,
            product_id=request.product_id,
            status="pending"
        ))
        
        # 3. Create PaymentIntent via Stripe Service
        intent = stripe_service.create_payment_intent(
            amount_cents=amount_cents,
            currency=currency,
            metadata={"order_id": str(db_order.id)}
        )
        
        # 4. Create Payment Record
        db_payment = payment_repo.create(db, obj_in=PaymentCreate(
            order_id=db_order.id,
            amount_cents=amount_cents,
            currency=currency,
            status="pending"
        ))
        
        # Update payment with intent ID
        payment_repo.update(db, db_obj=db_payment, obj_in={"stripe_payment_intent_id": intent.id})

        return PaymentIntentResponse(
            client_secret=intent.client_secret,
            payment_id=db_payment.id
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
