import firebase_admin
from firebase_admin import credentials
import os
import logging

logger = logging.getLogger(__name__)

_firebase_app_initialized = False

def initialize_firebase_app():
    """
    Initializes the Firebase Admin SDK using service account credentials.
    The path to the service account JSON file should be set in the
    GOOGLE_APPLICATION_CREDENTIALS environment variable.
    """
    global _firebase_app_initialized
    if _firebase_app_initialized:
        logger.info("Firebase app already initialized.")
        return firebase_admin.get_app()

    try:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

        if not os.path.exists(cred_path):
            logger.error(f"Firebase service account key file not found at path: {cred_path}")
            raise FileNotFoundError(f"Firebase service account key file not found at path: {cred_path}")

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_app_initialized = True
        logger.info("Firebase Admin SDK initialized successfully.")
        return firebase_admin.get_app()
    except Exception as e:
        logger.error(f"Error initializing Firebase Admin SDK: {e}", exc_info=True)
        # Depending on the application's needs, you might want to re-raise the exception
        # or handle it in a way that allows the app to continue running with limited functionality.
        # For now, we'll re-raise to make it clear that initialization failed.
        raise

def get_firebase_app():
    """
    Returns the initialized Firebase app.
    Initializes the app if it hasn't been initialized yet.
    """
    if not _firebase_app_initialized:
        return initialize_firebase_app()
    return firebase_admin.get_app()

# Example of how to potentially use it (optional, for testing or direct script runs)
if __name__ == "__main__":
    # This part will only run when the script is executed directly.
    # For a real application, initialization should be triggered by the app startup.
    print("Attempting to initialize Firebase Admin SDK (ensure GOOGLE_APPLICATION_CREDENTIALS is set)...")
    try:
        # In a real app, you'd call initialize_firebase_app() during startup.
        # For example, in your FastAPI main.py using an @app.on_event("startup") handler.
        app = get_firebase_app()
        print(f"Firebase app '{app.name}' initialized.")
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        print("Please ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly")
        print("and points to a valid Firebase service account JSON key file.")

# It's good practice to ensure the core directory exists.
# The tool used to create this file should handle directory creation.
# If not, one might use:
# if not os.path.exists("backend/core"):
#    os.makedirs("backend/core")
# However, this script assumes the directory `backend/core` is already created by the agent.
