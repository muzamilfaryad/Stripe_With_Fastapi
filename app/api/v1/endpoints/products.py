from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.product import ProductCreate, ProductResponse
from app.services import product_service

router = APIRouter()

@router.post("/", response_model=ProductResponse)
def create_new_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    try:
        product = product_service.create_product(db=db, product_data=product_in)
        return product
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return product_service.list_products(db)

@router.get("/{product_id}", response_model=ProductResponse)
def get_single_product(product_id: int, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
