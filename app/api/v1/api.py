from fastapi import APIRouter
from app.api.v1.endpoints import customers, payments, webhooks, products, subscriptions

api_router = APIRouter()
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(payments.router, prefix="/payments", tags=["checkout"])
api_router.include_router(webhooks.router, tags=["webhooks"])  # No prefix - webhook at /api/v1/webhook
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])

