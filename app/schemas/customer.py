from pydantic import BaseModel, EmailStr
from typing import Optional

class CustomerBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerResponse(CustomerBase):
    id: int
    stripe_customer_id: Optional[str] = None
    
    class Config:
        from_attributes = True
