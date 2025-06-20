from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
import logging
from typing import List, Optional, Dict, Any

from backend.models.user_model import User
from backend.schemas.user_schema import UserCreateInternal, AdminUserUpdate
from backend.services import email_service # Added for sending welcome email
from backend.core.config import settings # For APP_FRONTEND_URL in email context

logger = logging.getLogger(__name__)


# Helper function to apply filters to a query
def _apply_user_filters(query, filters: Optional[Dict[str, Any]] = None):
    if not filters:
        return query

    if "email_contains" in filters and filters["email_contains"]:
        query = query.filter(User.email.ilike(f"%{filters['email_contains']}%"))
    if "role" in filters and filters["role"]:
        query = query.filter(User.role == filters["role"])
    if "referral_code" in filters and filters["referral_code"]:
        query = query.filter(User.referral_code == filters["referral_code"])
    # Add more filters as needed, e.g., for is_active, date ranges, etc.
    return query

def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Fetches a user by their internal database ID."""
    logger.debug(f"Fetching user by ID: {user_id}")
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetches a user by their email address."""
    logger.debug(f"Fetching user by email: {email}")
    return db.query(User).filter(User.email == email).first()

def get_user_by_firebase_uid(db: Session, firebase_uid: str) -> User | None:
    """Fetches a user by their Firebase UID."""
    logger.debug(f"Fetching user by Firebase UID: {firebase_uid}")
    return db.query(User).filter(User.firebase_uid == firebase_uid).first()

def get_user_by_referral_code(db: Session, referral_code: str) -> User | None:
    """Fetches a user by their referral code."""
    logger.debug(f"Fetching user by referral code: {referral_code}")
    return db.query(User).filter(User.referral_code == referral_code).first()

def create_user(db: Session, user_data: UserCreateInternal) -> User | None:
    """
    Creates a new user in the database.
    Assumes firebase_uid and email are provided from a verified Firebase ID token.
    """
    logger.info(f"Attempting to create user for email: {user_data.email}, Firebase UID: {user_data.firebase_uid}, referred_by_id: {user_data.referred_by_id}")

    # Check for existing user by Firebase UID or email to prevent duplicates
    # This is an additional safeguard, though the /register route logic should also check.
    if get_user_by_firebase_uid(db, user_data.firebase_uid):
        logger.warning(f"User creation failed: Firebase UID {user_data.firebase_uid} already exists.")
        # Consider raising an specific exception or returning a clear indicator.
        return None
    if get_user_by_email(db, user_data.email):
        logger.warning(f"User creation failed: Email {user_data.email} already exists.")
        return None

    db_user = User(
        firebase_uid=user_data.firebase_uid,
        email=user_data.email,
        role=user_data.role or 'Subscriber', # Default role if not provided
        referral_code=user_data.referral_code, # This is the new user's OWN referral code
        # referred_by_id is the direct referrer (L1 upline ID)
        # This ID should be validated and fetched by the calling service/route (e.g. from referral_code_used)
        # and then passed into UserCreateInternal.
        referred_by_id=user_data.referred_by_id
    )

    # Populate upline structure
    if user_data.referred_by_id:
        referrer_l1 = get_user_by_id(db, user_data.referred_by_id)
        if referrer_l1:
            db_user.upline_l1_id = referrer_l1.id
            # It's crucial that User model relationships for upline_l1, upline_l2 are correctly configured
            # to access referrer_l1.upline_l1_id (which is referrer_l1's own L1, becoming new user's L2)
            # and referrer_l1.upline_l2_id (becoming new user's L3).
            # Assuming User model has direct access to these after fetching referrer_l1:
            if referrer_l1.upline_l1_id: # This is the L1 of the L1 referrer = L2 for new user
                db_user.upline_l2_id = referrer_l1.upline_l1_id
                # To get L3 for new user, we need L2 of the L1 referrer.
                # This requires fetching referrer_l1's L1 upline (User object) to access its upline_l1_id.
                # If upline_l1, upline_l2 etc. on User model are relationships that load the User object, this is easier.
                # Assuming `referrer_l1.upline_l1` is the User object of referrer_l1's L1 upline.
                if referrer_l1.upline_l1 and referrer_l1.upline_l1.upline_l1_id: # L1 of L1's L1 = L2 of L1 = L3 for new user
                     # Correction: L3 for new user is L2 of their L1 referrer.
                     # L2 of referrer_l1 is referrer_l1.upline_l2_id
                    db_user.upline_l3_id = referrer_l1.upline_l2_id # This was correct in prompt.
            logger.info(f"Upline structure for {user_data.email}: L1={db_user.upline_l1_id}, L2={db_user.upline_l2_id}, L3={db_user.upline_l3_id}")
        else:
            logger.warning(f"Referrer with ID {user_data.referred_by_id} not found. Cannot set upline for {user_data.email}.")
            # This case should ideally be prevented by validation in the route.

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User created successfully: {db_user.email} (ID: {db_user.id}). Upline L1: {db_user.upline_l1_id}")

        # Send welcome email
        try:
            email_context = {
                "user_name": db_user.email, # Or a display name if available
                "referral_code": db_user.referral_code,
                # APP_FRONTEND_URL is already added globally in email_service.send_templated_email
            }
            email_service.send_templated_email(
                to_email=db_user.email,
                subject="Welcome to Our Platform!", # Subject can be from a template too
                html_template_name="welcome.html",
                context=email_context
            )
            logger.info(f"Welcome email queued for user {db_user.email}")
        except Exception as e_mail_exc:
            # Log email sending failure but don't let it fail user creation
            logger.error(f"Failed to send welcome email to {db_user.email}: {e_mail_exc}", exc_info=True)

        return db_user
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during user creation for {user_data.email}: {e}", exc_info=True)
        # This could happen if, despite checks, a race condition leads to a duplicate
        # or if other constraints (like referral_code uniqueness) are violated.
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during user creation for {user_data.email}: {e}", exc_info=True)
        return None

# Future CRUD operations for users can be added here:
# def delete_user(db: Session, user_id: int) -> bool: ...


# --- Admin User Management CRUD ---

def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[User]:
    """
    Retrieves a list of users with pagination and optional filtering.
    """
    logger.debug(f"Fetching users with skip: {skip}, limit: {limit}, filters: {filters}")
    query = db.query(User)
    query = _apply_user_filters(query, filters)
    return query.order_by(User.id.asc()).offset(skip).limit(limit).all()

def count_users(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """
    Counts users with optional filtering.
    """
    logger.debug(f"Counting users with filters: {filters}")
    query = db.query(func.count(User.id))
    query = _apply_user_filters(query, filters)
    return query.scalar() or 0


def update_user_by_admin(db: Session, user_id: int, data_in: AdminUserUpdate) -> Optional[User]:
    """
    Updates a user's information by an admin.
    Allows updating fields like role, email.
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        logger.warning(f"User with ID {user_id} not found for admin update.")
        return None

    update_data = data_in.model_dump(exclude_unset=True)
    logger.info(f"Admin updating user ID {user_id} with data: {update_data}")

    if "email" in update_data and update_data["email"] != db_user.email:
        # Check if the new email already exists
        existing_user_with_new_email = get_user_by_email(db, update_data["email"])
        if existing_user_with_new_email and existing_user_with_new_email.id != user_id:
            logger.warning(f"Admin update failed: New email '{update_data['email']}' already in use by another user.")
            raise IntegrityError(f"Email '{update_data['email']}' already exists.", params={}, orig=None) # Or custom exception

    for field, value in update_data.items():
        setattr(db_user, field, value)

    try:
        db.commit()
        db.refresh(db_user)
        logger.info(f"User ID {user_id} updated successfully by admin.")
        return db_user
    except IntegrityError as e: # Catch potential unique constraint violations (e.g. email)
        db.rollback()
        logger.error(f"Database integrity error during admin update for user {user_id}: {e}", exc_info=True)
        raise # Re-raise to be handled by route
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during admin update for user {user_id}: {e}", exc_info=True)
        raise


# If is_active field is added to User model:
# def activate_user(db: Session, user_id: int) -> Optional[User]:
#     db_user = get_user_by_id(db, user_id)
#     if db_user and not db_user.is_active:
#         db_user.is_active = True
#         db.commit()
#         db.refresh(db_user)
#         logger.info(f"User ID {user_id} activated.")
#     return db_user

# def deactivate_user(db: Session, user_id: int) -> Optional[User]:
#     db_user = get_user_by_id(db, user_id)
#     if db_user and db_user.is_active:
#         db_user.is_active = False
#         db.commit()
#         db.refresh(db_user)
#         logger.info(f"User ID {user_id} deactivated.")
#     return db_user
