from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.base import CRUDBase
from app.models.order import Order
from pydantic import BaseModel

# Using dummy schemas to satisfy typing
class OrderCreate(BaseModel):
    customer_id: int
    product_id: int
    status: str = "pending"
    
class OrderUpdate(BaseModel):
    status: Optional[str] = None

class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
    def get_by_customer(self, db: Session, *, customer_id: int) -> List[Order]:
        return db.query(self.model).filter(Order.customer_id == customer_id).all()

order = CRUDOrder(Order)
