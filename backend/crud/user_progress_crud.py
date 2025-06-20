from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
import logging
from datetime import datetime

from backend.models.user_progress_model import UserProgress
from backend.models.course_model import Course, ModuleContent # For counting total content
from backend.schemas import user_progress_schema as schemas # Alias for clarity

logger = logging.getLogger(__name__)

def create_or_update_user_progress(
    db: Session,
    user_id: int,
    content_id: int,
    course_id: int, # Explicitly pass course_id for clarity and direct use
    progress_in: schemas.UserProgressUpdate
) -> UserProgress:
    """
    Creates or updates a user's progress for a specific piece of content.
    Marks content as completed if progress_in.completed_at is set.
    Updates playback position, score, etc.
    """
    logger.debug(f"Updating progress for user_id {user_id}, content_id {content_id}, course_id {course_id}")

    progress = db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.content_id == content_id
    ).first()

    if not progress:
        logger.info(f"No existing progress found for user {user_id} on content {content_id}. Creating new entry.")
        progress_data_dict = progress_in.model_dump(exclude_unset=True)
        progress = UserProgress(
            user_id=user_id,
            content_id=content_id,
            course_id=course_id, # Ensure course_id is set
            **progress_data_dict
        )
        # If completed_at is provided in this initial creation, ensure it's set.
        # If not, it remains None. last_accessed_at is auto-updated by DB.
        db.add(progress)
    else:
        logger.info(f"Existing progress found (ID: {progress.id}). Updating.")
        update_data = progress_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(progress, field, value)

        # Ensure last_accessed_at is updated if not handled by DB on every update
        progress.last_accessed_at = datetime.utcnow() # Or func.now() if DB supports it well here

    try:
        db.commit()
        db.refresh(progress)
        logger.info(f"User progress for user {user_id}, content {content_id} saved successfully (ID: {progress.id}).")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving user progress for user {user_id}, content {content_id}: {e}", exc_info=True)
        raise

    return progress

def get_user_progress_for_content(db: Session, user_id: int, content_id: int) -> Optional[UserProgress]:
    """Fetches a specific progress entry for a user and content item."""
    logger.debug(f"Fetching progress for user_id {user_id}, content_id {content_id}")
    return db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.content_id == content_id
    ).first()

def get_user_progress_for_course(db: Session, user_id: int, course_id: int) -> List[UserProgress]:
    """Fetches all progress entries for a user in a specific course."""
    logger.debug(f"Fetching all progress for user_id {user_id}, course_id {course_id}")
    return db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.course_id == course_id
    ).order_by(UserProgress.last_accessed_at.desc()).all()

def get_course_completion_percentage(db: Session, user_id: int, course_id: int) -> float:
    """
    Calculates the percentage of content completed by a user for a specific course.
    Completion is determined by the `completed_at` field in UserProgress.
    """
    logger.debug(f"Calculating completion percentage for user_id {user_id}, course_id {course_id}")

    # Count total number of 'completable' content items in the course.
    # This could be all content items, or you might exclude certain types if they don't count towards completion.
    # For now, assume all ModuleContent items are completable.
    total_course_contents = db.query(func.count(ModuleContent.id)).join(CourseModule).filter(CourseModule.course_id == course_id).scalar()

    if total_course_contents == 0:
        logger.info(f"Course ID {course_id} has no content items. Completion is 0%.")
        return 0.0

    # Count completed content items for the user in this course
    completed_contents_count = db.query(func.count(UserProgress.id)).filter(
        UserProgress.user_id == user_id,
        UserProgress.course_id == course_id,
        UserProgress.completed_at.isnot(None) # Check if completed_at is set
    ).scalar()

    if completed_contents_count == 0:
        logger.info(f"User {user_id} has not completed any content for course ID {course_id}. Completion is 0%.")
        return 0.0

    completion_percentage = (completed_contents_count / total_course_contents) * 100
    logger.info(f"User {user_id} course ID {course_id}: {completed_contents_count}/{total_course_contents} completed. Percentage: {completion_percentage:.2f}%")

    return round(completion_percentage, 2)

def get_last_accessed_content_for_course(db: Session, user_id: int, course_id: int) -> Optional[UserProgress]:
    """Gets the most recently accessed piece of content by a user within a specific course."""
    logger.debug(f"Fetching last accessed content for user_id {user_id}, course_id {course_id}")
    return db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.course_id == course_id
    ).order_by(UserProgress.last_accessed_at.desc()).first()

# Could add more specific functions like:
# - mark_content_as_started(db, user_id, content_id, course_id)
# - mark_content_as_completed(db, user_id, content_id, course_id)
# - update_video_playback_position(db, user_id, content_id, course_id, position_seconds)
# - record_quiz_score(db, user_id, content_id, course_id, score_percentage)
# The current create_or_update_user_progress handles these via the UserProgressUpdate schema.
