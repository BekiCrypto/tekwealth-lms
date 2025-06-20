import os
from dotenv import load_dotenv
from typing import Optional, List

# Load .env file from the backend directory (where this config.py might be, or its parent)
# Assuming .env is in the 'backend' folder, and this config.py is in 'backend/core/'
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

class Settings:
    PROJECT_NAME: str = "MLM E-Learning Platform API"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mydb")

    # Firebase
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo") # Default model

    # Stripe
    STRIPE_API_KEY: Optional[str] = os.getenv("STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    # Example Price IDs (better stored in DB per plan, but can be defaults)
    # STRIPE_PRICE_ID_MONTHLY: Optional[str] = os.getenv("STRIPE_PRICE_ID_MONTHLY")
    # STRIPE_PRICE_ID_YEARLY: Optional[str] = os.getenv("STRIPE_PRICE_ID_YEARLY")

    # CORS
    CORS_ALLOWED_ORIGINS_STR: str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS_STR.split(',') if origin.strip()]

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Referral Commission Rates (as decimals, e.g., "0.10" for 10%)
    COMMISSION_RATE_L1_STR: str = os.getenv("COMMISSION_RATE_L1", "0.10")
    COMMISSION_RATE_L2_STR: str = os.getenv("COMMISSION_RATE_L2", "0.05")
    COMMISSION_RATE_L3_STR: str = os.getenv("COMMISSION_RATE_L3", "0.02")

    # JWT (If using own JWTs in addition to Firebase)
    # JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-very-secret-jwt-key")
    # JWT_ALGORITHM: str = "HS256"
    # JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Application settings
    APP_FRONTEND_URL: str = os.getenv("APP_FRONTEND_URL", "http://localhost:3000")

    # Email settings
    EMAIL_HOST: Optional[str] = os.getenv("EMAIL_HOST")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587")) # Default to 587 for TLS
    EMAIL_USERNAME: Optional[str] = os.getenv("EMAIL_USERNAME")
    EMAIL_PASSWORD: Optional[str] = os.getenv("EMAIL_PASSWORD")
    EMAIL_FROM_ADDRESS: Optional[str] = os.getenv("EMAIL_FROM_ADDRESS")
    EMAIL_FROM_NAME: Optional[str] = os.getenv("EMAIL_FROM_NAME", PROJECT_NAME) # Use Project Name as default sender name
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
    EMAIL_USE_SSL: bool = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
    # Path to email templates directory, relative to the backend root
    # Example: backend/templates/emails
    EMAILS_TEMPLATES_DIR: str = os.getenv("EMAILS_TEMPLATES_DIR", "backend/templates/emails")


settings = Settings()

# Example usage:
# from backend.core.config import settings
# api_key = settings.OPENAI_API_KEY
