import logging
from fastapi import HTTPException, status
from firebase_admin import auth
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError, RevokedIdTokenError

from backend.core.firebase_config import get_firebase_app # Ensure Firebase app is initialized
from backend.schemas.user_schema import TokenData # For typing the decoded token

logger = logging.getLogger(__name__)

def verify_firebase_id_token(id_token: str) -> TokenData:
    """
    Verifies a Firebase ID token and extracts user information.

    Args:
        id_token: The Firebase ID token string.

    Returns:
        TokenData: A Pydantic model containing firebase_uid and email.

    Raises:
        HTTPException:
            - 401 UNAUTHORIZED if the token is invalid, expired, or revoked.
            - 401 UNAUTHORIZED if essential claims (user_id, email) are missing.
            - 500 INTERNAL_SERVER_ERROR for other Firebase Admin SDK errors.
    """
    try:
        # Ensure Firebase app is initialized before calling auth functions
        get_firebase_app()

        decoded_token = auth.verify_id_token(id_token)

        firebase_uid = decoded_token.get("uid")
        email = decoded_token.get("email")

        if not firebase_uid or not email:
            logger.warning("Firebase ID token is missing 'uid' or 'email' claims.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials: Missing essential token claims.",
            )

        # You could also check for email_verified if your app requires it:
        # if not decoded_token.get("email_verified"):
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Email not verified. Please verify your email address.",
        #     )

        logger.info(f"Firebase ID token verified successfully for UID: {firebase_uid}, Email: {email}")
        return TokenData(firebase_uid=firebase_uid, email=email)

    except (InvalidIdTokenError, ExpiredIdTokenError, RevokedIdTokenError) as e:
        logger.warning(f"Firebase ID token verification failed: {e}")
        detail_message = "Invalid or expired authentication token."
        if isinstance(e, ExpiredIdTokenError):
            detail_message = "Authentication token has expired. Please log in again."
        elif isinstance(e, RevokedIdTokenError):
            detail_message = "Authentication token has been revoked. Please log in again."

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # This catches other potential errors from firebase_admin.auth,
        # such as issues connecting to Firebase services if not handled by the SDK itself.
        logger.error(f"An unexpected error occurred during Firebase ID token verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify authentication token due to a server error.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# If you were to implement your own JWTs (e.g., for session management after Firebase auth)
# you would add functions like create_access_token here.
# For now, we rely solely on Firebase ID tokens.

# Example:
# from datetime import datetime, timedelta
# from jose import JWTError, jwt
# from backend.schemas.user_schema import TokenData as AppTokenData # Your app's token data schema

# SECRET_KEY = "YOUR_VERY_SECRET_KEY" # Should be in env variables
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# def verify_app_token(token: str, credentials_exception: HTTPException) -> AppTokenData:
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub") # Or firebase_uid, email, etc.
#         if username is None:
#             raise credentials_exception
#         # You might want a more specific AppTokenData schema here
#         token_data = AppTokenData(firebase_uid=username, email=payload.get("email"))
#     except JWTError:
#         raise credentials_exception
#     return token_data
