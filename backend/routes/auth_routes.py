from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
import logging
import secrets # For generating referral codes

from backend.core.database import get_db
from backend.core.dependencies import get_current_active_user
from backend.core.security import verify_firebase_id_token
from backend.crud.user_crud import (
    create_user,
    get_user_by_firebase_uid,
    get_user_by_email,
    get_user_by_referral_code,
)
from backend.models.user_model import User
from backend.schemas.user_schema import (
    UserRegisterRequest,
    UserLoginRequest,
    UserDisplay,
    AuthResponse,
    UserCreateInternal,
    TokenData
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

def generate_unique_referral_code(db: Session) -> str:
    """Generates a unique referral code."""
    while True:
        code = secrets.token_hex(4).upper() # e.g., 8-character hex string
        if not get_user_by_referral_code(db, code):
            return code

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user_after_firebase(
    payload: UserRegisterRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Register a new user in the application's database after successful
    authentication and registration with Firebase on the client-side.

    The client must obtain a Firebase ID token and send it in the request body.
    Optionally, a referral code used during sign-up can be provided.
    """
    logger.info(f"Registration attempt with Firebase ID token.")

    try:
        token_data: TokenData = verify_firebase_id_token(payload.firebase_id_token)
    except HTTPException as e:
        logger.warning(f"Firebase ID token verification failed during registration: {e.detail}")
        raise e # Re-raise the exception from verify_firebase_id_token

    firebase_uid = token_data.firebase_uid
    email = token_data.email

    logger.info(f"Token verified for UID: {firebase_uid}, Email: {email}")

    # Check if user already exists by Firebase UID or Email
    if get_user_by_firebase_uid(db, firebase_uid=firebase_uid):
        logger.warning(f"Registration failed: User with Firebase UID {firebase_uid} already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this Firebase UID already exists.",
        )
    if get_user_by_email(db, email=email):
        logger.warning(f"Registration failed: User with email {email} already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
        )

    referred_by_user_id: int | None = None
    if payload.referral_code_used:
        referrer = get_user_by_referral_code(db, payload.referral_code_used)
        if not referrer:
            logger.warning(f"Referral code '{payload.referral_code_used}' not found.")
            # Depending on policy, you might reject or just ignore invalid codes
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid referral code: {payload.referral_code_used}",
            )
        referred_by_user_id = referrer.id
        logger.info(f"User referred by: {referrer.email} (ID: {referrer.id}) using code: {payload.referral_code_used}")


    # Generate a unique referral code for the new user
    new_referral_code = generate_unique_referral_code(db)

    user_create_data = UserCreateInternal(
        firebase_uid=firebase_uid,
        email=email,
        role='Subscriber', # Default role
        referral_code=new_referral_code, # Assign the new user their own referral code
        referred_by_id=referred_by_user_id # Link to the user who referred them
    )

    db_user = create_user(db, user_data=user_create_data)

    if not db_user:
        logger.error(f"Failed to create user in database for Firebase UID: {firebase_uid}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user account. Please try again later.",
        )

    logger.info(f"User {email} (UID: {firebase_uid}) successfully registered and created in DB (ID: {db_user.id}).")
    return AuthResponse(
        message="User registered successfully.",
        user=UserDisplay.from_orm(db_user) # Pydantic V1
        # user=UserDisplay.model_validate(db_user) # Pydantic V2
    )


@router.post("/login", response_model=AuthResponse)
async def login_user_with_firebase(
    payload: UserLoginRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Logs in a user who has authenticated with Firebase on the client-side.
    The client must obtain a Firebase ID token and send it in the request body.
    This endpoint verifies the token and confirms the user's existence in the local DB.
    """
    logger.info("Login attempt with Firebase ID token.")

    try:
        token_data: TokenData = verify_firebase_id_token(payload.firebase_id_token)
    except HTTPException as e:
        logger.warning(f"Firebase ID token verification failed during login: {e.detail}")
        raise e

    firebase_uid = token_data.firebase_uid
    logger.info(f"Token verified for UID: {firebase_uid}. Fetching user from DB.")

    user = get_user_by_firebase_uid(db, firebase_uid=firebase_uid)
    if not user:
        logger.warning(f"Login failed: User with Firebase UID {firebase_uid} not found in local database.")
        # This could mean the user authenticated with Firebase but missed the /register step,
        # or their account was deleted from the local DB.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # Or 403 if preferred
            detail="User not registered in our system or account is inactive. Please complete registration or contact support.",
        )

    logger.info(f"User {user.email} (Firebase UID: {firebase_uid}) logged in successfully.")
    return AuthResponse(
        message="Login successful.",
        user=UserDisplay.from_orm(user) # Pydantic V1
        # user=UserDisplay.model_validate(user) # Pydantic V2
    )


@router.get("/users/me", response_model=UserDisplay)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user's details.
    Requires a valid Firebase ID token in the Authorization header.
    """
    logger.info(f"Fetching details for current user: {current_user.email} (ID: {current_user.id})")
    # The UserDisplay schema will handle converting the User model instance
    return current_user # FastAPI will automatically serialize using UserDisplay
    # For Pydantic V2, if you have issues with direct return:
    # return UserDisplay.model_validate(current_user)

# Example of how to use Pydantic v2 model_validate if from_orm is deprecated for your version
# from pydantic import VERSION as PYDANTIC_VERSION
# IS_PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")
# def model_to_schema(model_instance, schema_class):
# if IS_PYDANTIC_V2:
# return schema_class.model_validate(model_instance)
# else:
# return schema_class.from_orm(model_instance)
