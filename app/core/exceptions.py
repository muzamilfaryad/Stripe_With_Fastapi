from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

class StripeIntegrationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

class ResourceNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message
        self.status_code = 404

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(StripeIntegrationError)
    async def stripe_error_handler(request: Request, exc: StripeIntegrationError):
        logger.error(f"Stripe Error: {exc.message}")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_handler(request: Request, exc: ResourceNotFoundError):
        logger.warning(f"Not Found: {exc.message}")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
