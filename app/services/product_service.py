import stripe
from sqlalchemy.orm import Session
from app.models.product import Product, Price
from app.schemas.product import ProductCreate

def create_product(db: Session, product_data: ProductCreate) -> Product:
    # 1. Create Product in Stripe
    stripe_product = stripe.Product.create(
        name=product_data.name,
        description=product_data.description
    )
    
    # 2. Save Product to DB
    db_product = Product(
        stripe_product_id=stripe_product.id,
        name=product_data.name,
        description=product_data.description
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # 3. Create Prices
    for price_data in product_data.prices:
        recurring_dict = {}
        if price_data.recurring_interval:
            recurring_dict = {"interval": price_data.recurring_interval}
            
        stripe_price = stripe.Price.create(
            product=stripe_product.id,
            unit_amount=int(price_data.unit_amount * 100), # Send cents to Stripe
            currency=price_data.currency,
            recurring=recurring_dict if recurring_dict else None
        )
        
        db_price = Price(
            stripe_price_id=stripe_price.id,
            product_id=db_product.id,
            currency=price_data.currency,
            unit_amount=price_data.unit_amount,
            recurring_interval=price_data.recurring_interval
        )
        db.add(db_price)
    
    db.commit()
    db.refresh(db_product)
    
    return db_product

def list_products(db: Session):
    return db.query(Product).all()

def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()
