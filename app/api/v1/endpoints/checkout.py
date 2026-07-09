from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.checkout import CheckoutRequest, CheckoutResponse
from app.services.checkout_service import create_checkout_session

router = APIRouter()

@router.post("/", response_model=CheckoutResponse)
def initiate_checkout(checkout_req: CheckoutRequest, db: Session = Depends(get_db)):
    try:
        session = create_checkout_session(db=db, checkout_req=checkout_req)
        return CheckoutResponse(
            session_id=session.id,
            url=session.url
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
