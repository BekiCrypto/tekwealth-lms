from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from backend.core.database import get_db
from backend.core.dependencies import (
    get_current_active_user,
    get_current_admin_user,
    get_course_owner_or_admin,
    get_module_owner_or_admin,
    get_content_owner_or_admin,
    get_course_or_404, # For public access, just fetches or 404
    get_module_or_404,
    get_content_or_404,
)
from backend.models.user_model import User
from backend.models.course_model import Course, CourseModule, ModuleContent # For type hints
from backend.models import enums as model_enums # For query params
from backend.schemas import course_schema as schemas # Alias for clarity
from backend.crud import course_crud as crud # Alias for clarity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Courses & Learning Content"])

# --- Course Endpoints ---
@router.post("/", response_model=schemas.CourseDisplay, status_code=status.HTTP_201_CREATED)
def create_new_course(
    course_in: schemas.CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user) # Only admins can create courses
):
    """
    Create a new course. (Admin only)
    """
    logger.info(f"Admin user {current_user.email} creating course: {course_in.title}")
    # owner_id for courses created by admin can be admin's own ID or null/system ID
    # For now, let's assign it to the admin creating it.
    return crud.create_course(db=db, course_in=course_in, owner_id=current_user.id)

@router.get("/", response_model=List[schemas.CourseDisplay]) # Consider PaginatedCourseList for actual pagination
def read_courses_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    levels: Optional[List[model_enums.CourseLevel]] = Query(None),
    categories: Optional[List[model_enums.CourseCategory]] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get a list of all courses. Publicly accessible.
    Supports filtering by level and category.
    """
    logger.debug(f"Fetching courses with skip: {skip}, limit: {limit}, levels: {levels}, categories: {categories}")
    courses = crud.get_courses(db, skip=skip, limit=limit, levels=levels, categories=categories)
    return courses

@router.get("/{course_id}", response_model=schemas.CourseDisplay)
def read_single_course(
    course: Course = Depends(get_course_or_404) # Path variable 'course_id' implicitly used by Depends
):
    """
    Get details of a specific course. Publicly accessible.
    """
    return course

@router.put("/{course_id}", response_model=schemas.CourseDisplay)
def update_existing_course(
    course_in: schemas.CourseUpdate,
    course: Course = Depends(get_course_owner_or_admin) # Auth check: owner or admin
):
    """
    Update an existing course. (Owner or Admin only)
    """
    db = Session.object_session(course) # Get session from the instance
    logger.info(f"User updating course ID {course.id} (Title: {course.title})")
    return crud.update_course(db=db, course_id=course.id, course_in=course_in)

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_course(
    course: Course = Depends(get_course_owner_or_admin) # Auth check
):
    """
    Delete an existing course. (Owner or Admin only)
    """
    db = Session.object_session(course)
    logger.info(f"User deleting course ID {course.id} (Title: {course.title})")
    if not crud.delete_course(db=db, course_id=course.id):
        # This case should ideally not be reached if get_course_owner_or_admin works
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found for deletion")
    return {"message": "Course deleted successfully"} # This response won't be sent due to 204


# --- CourseModule Endpoints ---
@router.post("/{course_id}/modules/", response_model=schemas.CourseModuleDisplay, status_code=status.HTTP_201_CREATED)
def create_new_module_for_course(
    course_id: int, # Comes from path
    module_in: schemas.CourseModuleCreate,
    # Check if user is owner of the course_id or admin
    # We need to fetch the course first to check ownership
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new module for a specific course. (Owner or Admin of course only)
    """
    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course with ID {course_id} not found.")
    if not (current_user.role == "Admin" or course.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to add modules to this course.")

    logger.info(f"User {current_user.email} creating module '{module_in.title}' for course ID {course_id}")
    return crud.create_course_module(db=db, module_in=module_in, course_id=course_id)

@router.get("/{course_id}/modules/", response_model=List[schemas.CourseModuleDisplay])
def read_modules_for_course(
    course_id: int, # from path
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all modules for a specific course. Publicly accessible.
    """
    # Ensure course exists first
    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course with ID {course_id} not found.")

    logger.debug(f"Fetching modules for course ID {course_id}")
    modules = crud.get_modules_for_course(db, course_id=course_id, skip=skip, limit=limit)
    return modules

# --- Standalone Module, Content Endpoints (using module_id, content_id directly) ---
# These allow fetching/modifying module/content if you have its direct ID.
# The authorization dependencies get_module_owner_or_admin / get_content_owner_or_admin will handle security.

@router.get("/modules/{module_id}", response_model=schemas.CourseModuleDisplay)
def read_single_module(
    module: CourseModule = Depends(get_module_or_404) # Path var 'module_id' used by Depends
):
    """
    Get details of a specific module. Publicly accessible.
    """
    return module

@router.put("/modules/{module_id}", response_model=schemas.CourseModuleDisplay)
def update_existing_module(
    module_in: schemas.CourseModuleUpdate,
    module: CourseModule = Depends(get_module_owner_or_admin) # Auth check
):
    """
    Update an existing module. (Owner or Admin of parent course only)
    """
    db = Session.object_session(module)
    logger.info(f"User updating module ID {module.id} (Title: {module.title})")
    return crud.update_course_module(db=db, module_id=module.id, module_in=module_in)

@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_module(
    module: CourseModule = Depends(get_module_owner_or_admin) # Auth check
):
    """
    Delete an existing module. (Owner or Admin of parent course only)
    """
    db = Session.object_session(module)
    logger.info(f"User deleting module ID {module.id} (Title: {module.title})")
    if not crud.delete_course_module(db=db, module_id=module.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found for deletion")
    return {"message": "Module deleted successfully"}


# --- ModuleContent Endpoints ---
@router.post("/modules/{module_id}/contents/", response_model=schemas.ModuleContentDisplay, status_code=status.HTTP_201_CREATED)
def create_new_content_for_module(
    module_id: int, # from path
    content_in: schemas.ModuleContentCreate,
    # Check if user is owner of the module's parent course or admin
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create new content for a specific module. (Owner or Admin of parent course only)
    If content_type is QUIZ and quiz_data is provided, a quiz and its questions/options will be created.
    """
    module = crud.get_module(db, module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Module with ID {module_id} not found.")

    # Authorization check (owner of parent course or admin)
    parent_course = crud.get_course(db, module.course_id)
    if not parent_course: # Should not happen if DB is consistent
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Parent course not found for module.")
    if not (current_user.role == "Admin" or parent_course.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to add content to this module.")

    logger.info(f"User {current_user.email} creating content '{content_in.title}' for module ID {module_id}")

    db_content = crud.create_module_content(db=db, content_in=content_in, module_id=module_id)

    if content_in.content_type == model_enums.ModuleContentType.QUIZ and content_in.quiz_data:
        if db_content.quiz_association: # Should not happen on create
             logger.warning(f"Content ID {db_content.id} of type QUIZ already has a quiz. Skipping new quiz creation.")
        else:
            try:
                logger.info(f"Creating quiz for content ID {db_content.id} titled '{content_in.quiz_data.title}'")
                # The create_quiz_for_content function handles creating questions and options too.
                crud.create_quiz_for_content(db=db, quiz_in=content_in.quiz_data, module_content_id=db_content.id)
                db.refresh(db_content) # Refresh to load the quiz_association
            except Exception as e:
                # If quiz creation fails, we might want to roll back content creation or log critical error
                logger.error(f"Error creating quiz for content ID {db_content.id}: {e}", exc_info=True)
                # Potentially delete db_content if quiz was essential and failed
                # crud.delete_module_content(db, db_content.id) # Example rollback
                # db.commit()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Content created, but failed to create associated quiz: {e}")

    return db_content


@router.get("/modules/{module_id}/contents/", response_model=List[schemas.ModuleContentDisplay])
def read_contents_for_module(
    module_id: int, # from path
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all content items for a specific module. Publicly accessible.
    """
    module = crud.get_module(db, module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Module with ID {module_id} not found.")

    logger.debug(f"Fetching contents for module ID {module_id}")
    contents = crud.get_contents_for_module(db, module_id=module_id, skip=skip, limit=limit)
    return contents

@router.get("/contents/{content_id}", response_model=schemas.ModuleContentDisplay)
def read_single_content(
    content: ModuleContent = Depends(get_content_or_404) # Path var 'content_id' used by Depends
):
    """
    Get details of a specific content item. Publicly accessible.
    """
    return content

@router.put("/contents/{content_id}", response_model=schemas.ModuleContentDisplay)
def update_existing_content(
    content_in: schemas.ModuleContentUpdate,
    content: ModuleContent = Depends(get_content_owner_or_admin) # Auth check
):
    """
    Update an existing content item. (Owner or Admin of parent course only)
    Note: Updating quiz_data via this endpoint might be complex.
    Prefer dedicated quiz management endpoints if significant quiz changes are needed.
    """
    db = Session.object_session(content)
    logger.info(f"User updating content ID {content.id} (Title: {content.title})")

    updated_content = crud.update_module_content(db=db, content_id=content.id, content_in=content_in)

    # Handle quiz update if quiz_data is provided and type is QUIZ
    if content_in.quiz_data and updated_content.content_type == model_enums.ModuleContentType.QUIZ:
        if updated_content.quiz_association:
            logger.info(f"Updating associated quiz (ID: {updated_content.quiz_association.id}) for content ID {updated_content.id}")
            crud.update_quiz(db=db, quiz_id=updated_content.quiz_association.id, quiz_in=content_in.quiz_data)
        elif isinstance(content_in.quiz_data, schemas.QuizCreate): # If no existing quiz, and create data is provided
            logger.info(f"Creating new quiz for content ID {updated_content.id} during update.")
            try:
                crud.create_quiz_for_content(db=db, quiz_in=content_in.quiz_data, module_content_id=updated_content.id)
            except Exception as e:
                 logger.error(f"Error creating quiz during content update for ID {updated_content.id}: {e}", exc_info=True)
                 # Don't raise error here, content itself was updated. Log and continue or raise specific warning.

    db.refresh(updated_content) # Refresh to ensure all associations are loaded
    return updated_content


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_content(
    content: ModuleContent = Depends(get_content_owner_or_admin) # Auth check
):
    """
    Delete an existing content item. (Owner or Admin of parent course only)
    """
    db = Session.object_session(content)
    logger.info(f"User deleting content ID {content.id} (Title: {content.title})")
    if not crud.delete_module_content(db=db, content_id=content.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found for deletion")
    return {"message": "Content deleted successfully"}


# --- Quiz Specific Endpoints (Optional - if more granular control is needed beyond content creation) ---

@router.get("/quizzes/{quiz_id}", response_model=schemas.QuizDisplay)
def read_single_quiz(
    quiz_id: int, # from path
    db: Session = Depends(get_db)
    # Add authorization if quizzes should not be public without context
    # current_user: User = Depends(get_current_active_user) # Example: if only for logged-in users
):
    """
    Get details of a specific quiz, including its questions and options.
    Publicly accessible if its parent content/module/course is.
    (Authorization can be added based on parent content's ownership if needed)
    """
    logger.debug(f"Fetching quiz with ID: {quiz_id}")
    quiz = crud.get_quiz_with_questions(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quiz with ID {quiz_id} not found.")

    # Example of checking parent content authorization (if this quiz endpoint is hit directly)
    # parent_content = crud.get_content(db, quiz.module_content_id)
    # if not parent_content: ... error ...
    # authorized_content = await get_content_owner_or_admin(content=parent_content, current_user=current_user, db=db)
    # If we reach here, user is authorized for the parent content (if it's not a public endpoint)

    return quiz

# Further endpoints for managing questions within a quiz, options within a question, etc.,
# can be added if the initial creation within ModuleContent POST/PUT is not sufficient.
# Example:
# POST /quizzes/{quiz_id}/questions/ (schemas.QuestionDisplay)
# PUT /questions/{question_id} (schemas.QuestionDisplay)
# DELETE /questions/{question_id}
# POST /questions/{question_id}/options/ (schemas.QuestionOptionDisplay)
# ...and so on.
# For this subtask, quiz creation is primarily handled within the ModuleContent creation.
# The GET /quizzes/{quiz_id} is provided for direct fetching.
# Updating a quiz structure (questions/options) is complex and typically done by
# deleting and recreating questions, or via very specific question/option management endpoints.
# The current crud.update_quiz only updates quiz's own fields (title, description).
