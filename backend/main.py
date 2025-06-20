from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
load_dotenv(os.path.join(os.path.dirname(__file__), '.env')) # Ensure .env in backend folder is loaded

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

# Import core components
from backend.core.firebase_config import initialize_firebase_app
from backend.core.database import create_db_and_tables, engine, Base
from backend.routes import api_router_v1 # Import the main API router

# Import models to ensure they are registered with Base.metadata for table creation
# This is crucial if create_db_and_tables() is used.
from backend.models import ( # noqa F401 - Imports are for SQLAlchemy Base metadata registration
    user_model,
    course_model,
    user_progress_model,
    certificate_model,
    subscription_model,
    payment_model,
    referral_model      # Added
)


app = FastAPI(
    title="MLM E-Learning Platform API",
    description="API for the MLM E-Learning Platform, managing courses, users, subscriptions, and referrals.",
    version="0.1.0",
    # You can add other global configurations like root_path, openapi_url, etc.
)

# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    try:
        initialize_firebase_app()
        logger.info("Firebase Admin SDK initialized successfully during startup.")
    except Exception as e:
        logger.error(f"Critical error during Firebase initialization on startup: {e}", exc_info=True)
        # Depending on the severity, you might want to prevent the app from starting
        # or allow it to start with Firebase-dependent features disabled.

    # Initialize database tables (for development/testing)
    # In production, use Alembic migrations.
    # Make sure all your models are imported so Base.metadata knows about them.
    try:
        logger.info("Attempting to create database tables if they don't exist (dev mode)...")
        # Base.metadata.create_all(bind=engine) # This line is equivalent to create_db_and_tables if all models are imported
        create_db_and_tables() # This function should ideally import all models
        logger.info("Database tables checked/created.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        # Consider the impact of this error on application startup.

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    # Clean up resources here if needed, e.g., close database connections pool
    # (SQLAlchemy engine usually handles this automatically with connection pooling)

# --- Middleware ---
# CORS (Cross-Origin Resource Sharing) Middleware
origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(',')
logger.info(f"Allowed CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for request {request.method} {request.url}: {exc}", exc_info=True)
    # Avoid exposing detailed error messages in production for generic exceptions
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."},
    )

# --- API Routers ---
app.include_router(api_router_v1) # This includes all routes from backend.routes (e.g., /api/v1/auth/...)

@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to the MLM E-Learning Platform API! Navigate to /docs for API documentation."}

# --- Main execution (for development) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    logger.info(f"Starting Uvicorn server on {host}:{port} with log level {log_level}")
    uvicorn.run(app, host=host, port=port, log_level=log_level)
