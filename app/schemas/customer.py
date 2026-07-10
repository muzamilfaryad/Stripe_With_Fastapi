from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class CustomerBase(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Customer name")

class CustomerCreate(CustomerBase):
    pass

class CustomerResponse(CustomerBase):
    id: int
    stripe_customer_id: Optional[str] = None
    
    class Config:
        from_attributes = True
