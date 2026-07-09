from fastapi import FastAPI
from app.core.config import settings
from app.core import stripe_client  # Initializes stripe.api_key
from app.api.v1.api import api_router
import app.core.logging  # Initializes logging
from app.core.exceptions import register_exception_handlers

app = FastAPI(title=settings.APP_NAME)
register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    return {"message": "Welcome to the Stripe Coding Challenge API!"}
