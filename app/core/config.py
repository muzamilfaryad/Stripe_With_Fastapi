from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Stripe API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    
    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # URLs
    SUCCESS_URL: str
    CANCEL_URL: str
    
    # CORS - comma-separated origins in .env
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]

    model_config = ConfigDict(env_file=".env")

settings = Settings()
