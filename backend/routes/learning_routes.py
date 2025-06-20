from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from backend.core.database import get_db
from backend.core.dependencies import get_current_active_user # For authenticated user
from backend.models.user_model import User # For type hinting current_user
from backend.models.course_model import Course, ModuleContent, Quiz # For type hinting
from backend.schemas import (
    user_progress_schema as up_schemas,
    certificate_schema as cert_schemas,
    quiz_submission_schema as quiz_sub_schemas,
    course_schema as course_schemas # For MyCourseDisplay
)
from backend.crud import (
    user_progress_crud as up_crud,
    certificate_crud as cert_crud,
    course_crud as course_crud # For get_course, get_quiz_with_questions, submit_quiz
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/learn", tags=["Learning & Progress"])

# --- Custom Schema for My Courses ---
class MyCourseDisplay(course_schemas.CourseDisplay):
    completion_percentage: float = Field(0.0, description="User's completion percentage for this course")
    last_accessed_content_id: Optional[int] = Field(None, description="ID of the last content item accessed by the user in this course")


# --- Learning Flow Endpoints ---

@router.get("/my-courses", response_model=List[MyCourseDisplay])
def get_my_enrolled_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns a list of courses the user is enrolled in (or has progress in).
    Includes completion percentage for each course.
    (Actual enrollment check based on subscription is stubbed for now).
    """
    logger.info(f"Fetching 'my-courses' for user {current_user.email} (ID: {current_user.id})")

    # Stub: For now, let's assume user has access to all courses they've interacted with,
    # or simply list all courses and calculate progress for them.
    # A real implementation would check against a Subscription/Enrollment model.

    all_courses = course_crud.get_courses(db, limit=1000) # Get all courses (adjust as needed)

    my_courses_display_list = []
    for course in all_courses:
        completion_percentage = up_crud.get_course_completion_percentage(db, current_user.id, course.id)
        last_accessed_progress = up_crud.get_last_accessed_content_for_course(db, current_user.id, course.id)

        # Use CourseDisplay to serialize the course data first
        course_data = course_schemas.CourseDisplay.model_validate(course) # Pydantic v2
        # course_data = course_schemas.CourseDisplay.from_orm(course) # Pydantic v1

        my_course_item = MyCourseDisplay(
            **course_data.model_dump(),
            completion_percentage=completion_percentage,
            last_accessed_content_id=last_accessed_progress.content_id if last_accessed_progress else None
        )
        my_courses_display_list.append(my_course_item)

    return my_courses_display_list


@router.post("/progress/content/{content_id}", response_model=up_schemas.UserProgressDisplay)
def update_user_content_progress(
    content_id: int,
    progress_in: up_schemas.UserProgressUpdate, # e.g., {"playback_position_seconds": 30, "completed_at": "timestamp"}
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update user's progress for a specific piece of content (e.g., video position, mark as complete).
    """
    logger.info(f"User {current_user.email} updating progress for content_id {content_id}")

    # Fetch content to get its course_id for denormalization in UserProgress
    content = course_crud.get_content(db, content_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found.")
    if not content.module or not content.module.course_id: # Ensure data integrity
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Content is not properly linked to a course.")

    # TODO: Add check if user has access to this content via subscription/enrollment

    progress = up_crud.create_or_update_user_progress(
        db=db,
        user_id=current_user.id,
        content_id=content_id,
        course_id=content.module.course_id,
        progress_in=progress_in
    )
    return progress


@router.get("/progress/course/{course_id}", response_model=List[up_schemas.UserProgressDisplay])
def get_user_progress_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all progress entries for the current user in a specific course.
    """
    logger.info(f"User {current_user.email} fetching progress for course_id {course_id}")
    # TODO: Add check if user has access to this course via subscription/enrollment

    # Ensure course exists
    course = course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    progress_entries = up_crud.get_user_progress_for_course(db, current_user.id, course_id)
    return progress_entries


@router.post("/quizzes/{quiz_id}/submit", response_model=quiz_sub_schemas.QuizResultDisplay)
def submit_user_quiz_answers(
    quiz_id: int,
    submission: quiz_sub_schemas.QuizSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit answers for a quiz. Calculates score and updates user progress.
    """
    logger.info(f"User {current_user.email} submitting answers for quiz_id {quiz_id}")

    # Fetch quiz to ensure it exists and to get related module_content_id
    db_quiz = course_crud.get_quiz_with_questions(db, quiz_id)
    if not db_quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    if not db_quiz.content_association or not db_quiz.content_association.module:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Quiz is not properly linked to content and course.")

    # TODO: Add check if user has access to this quiz via course enrollment

    try:
        result = course_crud.submit_quiz(db, quiz_id, current_user.id, submission)
        return result
    except ValueError as ve: # Catch specific errors from submit_quiz like "Quiz not found"
        logger.warning(f"Value error during quiz submission for quiz {quiz_id} by user {current_user.email}: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error during quiz submission for quiz {quiz_id} by user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while submitting the quiz.")


@router.post("/courses/{course_id}/issue-certificate", response_model=cert_schemas.CertificateDisplay)
def issue_course_certificate(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Issues a certificate to the current user if the course is completed.
    """
    logger.info(f"User {current_user.email} requesting certificate for course_id {course_id}")

    # Ensure course exists
    course = course_crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    # TODO: Add check if user is enrolled in this course

    completion_percentage = up_crud.get_course_completion_percentage(db, current_user.id, course_id)
    # Define completion threshold (e.g., 100%)
    COMPLETION_THRESHOLD = 100.0
    if completion_percentage < COMPLETION_THRESHOLD:
        logger.warning(f"User {current_user.email} attempt to issue certificate for course {course_id} failed. Completion: {completion_percentage}% (Threshold: {COMPLETION_THRESHOLD}%)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course not yet completed. Completion: {completion_percentage}%. Required: {COMPLETION_THRESHOLD}%."
        )

    try:
        certificate = cert_crud.create_certificate(db, current_user.id, course_id)
        if not certificate: # Should not happen if create_certificate raises errors properly
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create certificate record.")
        logger.info(f"Certificate (ID: {certificate.id}, Code: {certificate.verification_code}) issued to user {current_user.email} for course {course_id}.")
        # Note: certificate_url is not set here. This would be another step.
        return certificate
    except Exception as e: # Catch potential IntegrityError if certificate already exists and not handled by CRUD
        logger.error(f"Error issuing certificate for user {current_user.email}, course {course_id}: {e}", exc_info=True)
        # Check if it's because it already exists
        existing_cert = db.query(Certificate).filter(Certificate.user_id == current_user.id, Certificate.course_id == course_id).first()
        if existing_cert:
            return existing_cert # Return existing certificate if already issued
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not issue certificate.")


@router.get("/certificates/my-certificates", response_model=List[cert_schemas.CertificateDisplay])
def get_my_certificates_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Lists all certificates issued to the current authenticated user.
    """
    logger.info(f"Fetching certificates for user {current_user.email}")
    certificates = cert_crud.get_certificates_for_user(db, current_user.id)
    return certificates


@router.get("/certificates/verify/{verification_code}", response_model=cert_schemas.CertificateDisplay)
def verify_certificate_by_code(
    verification_code: str,
    db: Session = Depends(get_db)
):
    """
    Verifies a certificate by its unique verification code. Publicly accessible.
    """
    logger.info(f"Verifying certificate with code: {verification_code}")
    certificate = cert_crud.get_certificate_by_verification_code(db, verification_code)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found or invalid verification code.")

    # Eager load user and course details if not automatically handled by relationship depth
    # For Pydantic v2, if using .model_validate(certificate), ensure relationships are loaded.
    # This is generally handled by SQLAlchemy's default lazy loading or specific options in CRUD.
    return certificate


@router.post("/ai-tutor/ask", tags=["AI Tutor (Experimental)"])
async def ask_ai_tutor(
    course_id: int = Body(..., description="ID of the course context for the question"),
    question_text: str = Body(..., min_length=10, max_length=1000, description="User's question to the AI tutor"),
    # current_user: User = Depends(get_current_active_user) # Uncomment if endpoint needs auth
):
    """
    Stub endpoint for the AI Tutor.
    Accepts a course ID and a question, returns a placeholder AI response.
    (Authentication can be added as needed)
    """
    logger.info(f"AI Tutor question received for course_id {course_id}: '{question_text}'")
    # In a real implementation, this would:
    # 1. Verify user has access to the course (if authenticated).
    # 2. Fetch course content, or specific content related to the question context if provided.
    # 3. Prepare a prompt for an LLM (e.g., OpenAI, Gemini).
    # 4. Call the LLM API.
    # 5. Process the LLM's response.
    # 6. Return the response to the user.

    # Placeholder response:
    ai_response = f"Thank you for your question about course {course_id}: '{question_text}'. "\
                  "I am an AI Tutor still in development. "\
                  "Soon, I will be able to provide helpful answers based on the course content!"

    return {"course_id": course_id, "question": question_text, "ai_response": ai_response}
