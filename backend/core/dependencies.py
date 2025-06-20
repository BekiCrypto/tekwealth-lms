from fastapi import Depends, HTTPException, status, Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session
import logging

from backend.core.database import get_db # Re-export or use directly
from backend.core.security import verify_firebase_id_token
from backend.crud.user_crud import get_user_by_firebase_uid, get_user_by_id
from backend.crud.course_crud import get_course, get_module, get_content # For ownership checks
from backend.models.user_model import User
from backend.models.course_model import Course, CourseModule, ModuleContent # For type hinting
from backend.schemas.user_schema import TokenData

logger = logging.getLogger(__name__)

# Dependency to get the current user from a Firebase ID token
async def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    Verifies the Firebase ID token from the Authorization header,
    then fetches the user from the database.
    """
    authorization: str = request.headers.get("Authorization")
    scheme, param = get_authorization_scheme_param(authorization)

    if not authorization or scheme.lower() != "bearer":
        logger.warning("Missing or invalid Bearer token in Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_id_token: str = param

    try:
        token_data: TokenData = verify_firebase_id_token(firebase_id_token)
    except HTTPException as e:
        # Re-raise the exception from verify_firebase_id_token (which already has correct status and detail)
        logger.warning(f"Token verification failed: {e.detail}")
        raise e # Ensure WWW-Authenticate header is preserved if set by verify_firebase_id_token

    user = get_user_by_firebase_uid(db, firebase_uid=token_data.firebase_uid)
    if user is None:
        logger.warning(f"User not found in DB for Firebase UID: {token_data.firebase_uid} from token.")
        # This case might indicate that the user authenticated with Firebase
        # but their account wasn't created/synced in our local database.
        # This could happen if the /register call after Firebase sign-up failed or was missed.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, # Or 404 if preferred, but 403 implies valid token, user not provisioned
            detail="User account not found or not fully registered in the system.",
        )

    logger.info(f"Authenticated user retrieved: {user.email} (ID: {user.id})")
    return user


# --- User Status/Role Dependencies ---
async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Placeholder for checking if a user is active.
    For now, it just returns the current user.
    You can extend this to check an `is_active` flag on the User model if needed.
    """
    # if not current_user.is_active: # Example: if you add an is_active field to User model
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Checks if the current user has the 'Admin' role.
    """
    if current_user.role != "Admin":
        logger.warning(f"Admin access denied for user: {current_user.email} (Role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted: Requires admin privileges.",
        )
    logger.info(f"Admin access granted for user: {current_user.email}")
    return current_user


# --- Resource Specific Fetching and Authorization Dependencies ---

# Get Course or Raise 404
def get_course_or_404(course_id: int, db: Session = Depends(get_db)) -> Course:
    course = get_course(db, course_id)
    if not course:
        logger.warning(f"Course with ID {course_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course with ID {course_id} not found.")
    return course

# Get Module or Raise 404
def get_module_or_404(module_id: int, db: Session = Depends(get_db)) -> CourseModule:
    module = get_module(db, module_id)
    if not module:
        logger.warning(f"Module with ID {module_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Module with ID {module_id} not found.")
    return module

# Get Content or Raise 404
def get_content_or_404(content_id: int, db: Session = Depends(get_db)) -> ModuleContent:
    content = get_content(db, content_id)
    if not content:
        logger.warning(f"Content with ID {content_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Content with ID {content_id} not found.")
    return content


# Dependency for Course Ownership or Admin
async def get_course_owner_or_admin(
    course: Course = Depends(get_course_or_404), # Gets course by ID from path
    current_user: User = Depends(get_current_active_user)
) -> Course:
    if not course: # Should be handled by get_course_or_404, but as a safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if current_user.role == "Admin" or course.owner_id == current_user.id:
        logger.info(f"User {current_user.email} authorized for course {course.id} (Role: {current_user.role}, Owner: {course.owner_id == current_user.id})")
        return course # User is admin or owner

    logger.warning(f"User {current_user.email} not authorized for course {course.id}. Not admin or owner.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to perform this action on the specified course.",
    )

# Dependency for Module Ownership (via parent Course) or Admin
async def get_module_owner_or_admin(
    module: CourseModule = Depends(get_module_or_404), # Gets module by ID from path
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db) # Need db session to fetch parent course
) -> CourseModule:
    if not module: # Safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    # Fetch the parent course to check ownership
    parent_course = get_course(db, module.course_id)
    if not parent_course:
        logger.error(f"Orphaned module detected: Module ID {module.id} has no parent course with ID {module.course_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Module's parent course not found.")

    if current_user.role == "Admin" or parent_course.owner_id == current_user.id:
        logger.info(f"User {current_user.email} authorized for module {module.id} via course {parent_course.id}")
        return module

    logger.warning(f"User {current_user.email} not authorized for module {module.id}.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to perform this action on the specified module.",
    )

# Dependency for Content Ownership (via parent Module's Course) or Admin
async def get_content_owner_or_admin(
    content: ModuleContent = Depends(get_content_or_404), # Gets content by ID from path
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db) # Need db session
) -> ModuleContent:
    if not content: # Safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found.")

    parent_module = get_module(db, content.module_id)
    if not parent_module:
        logger.error(f"Orphaned content detected: Content ID {content.id} has no parent module with ID {content.module_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Content's parent module not found.")

    parent_course = get_course(db, parent_module.course_id)
    if not parent_course:
        logger.error(f"Orphaned module/content: Module ID {parent_module.id} has no parent course with ID {parent_module.course_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Content's parent course not found.")

    if current_user.role == "Admin" or parent_course.owner_id == current_user.id:
        logger.info(f"User {current_user.email} authorized for content {content.id} via course {parent_course.id}")
        return content

    logger.warning(f"User {current_user.email} not authorized for content {content.id}.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to perform this action on the specified content.",
    )


# Dependency to get user by ID from path (example, if needed for some endpoints)
# This is more generic, not course-specific.
def get_user_or_404(user_id: int, db: Session = Depends(get_db)) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found.")
    return user
