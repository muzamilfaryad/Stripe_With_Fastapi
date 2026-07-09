from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import CRUDBase
from app.models.product import Product, Price
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    
class ProductUpdate(BaseModel):
    name: Optional[str] = None

class CRUDProduct(CRUDBase[Product, ProductCreate, ProductUpdate]):
    def get_price(self, db: Session, price_id: int) -> Optional[Price]:
        return db.query(Price).filter(Price.id == price_id).first()

product = CRUDProduct(Product)
