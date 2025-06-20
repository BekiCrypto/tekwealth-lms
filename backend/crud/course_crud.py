from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Type
import logging

from backend.models import enums
from backend.models.user_model import User
from backend.models.course_model import (
    Course, CourseModule, ModuleContent, Quiz, Question, QuestionOption
)
from backend.schemas import course_schema as schemas, user_progress_schema, quiz_submission_schema
from backend.crud.user_progress_crud import create_or_update_user_progress
from backend.crud import user_crud # To get user details for email context
from backend.services import email_service # For sending quiz results email
from datetime import datetime

logger = logging.getLogger(__name__)

# Helper function for updating entities
def update_db_object(db_obj, update_data: schemas.BaseModel) -> Type[Base]:
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, value)
    return db_obj

# --- Course CRUD ---
def create_course(db: Session, course_in: schemas.CourseCreate, owner_id: int) -> Course:
    logger.debug(f"Creating course titled '{course_in.title}' for owner_id {owner_id}")
    db_course = Course(
        **course_in.model_dump(),
        owner_id=owner_id
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    logger.info(f"Course '{db_course.title}' (ID: {db_course.id}) created successfully.")
    return db_course

def get_course(db: Session, course_id: int) -> Optional[Course]:
    logger.debug(f"Fetching course with ID: {course_id}")
    return db.query(Course).filter(Course.id == course_id).first()

def get_courses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    levels: Optional[List[enums.CourseLevel]] = None,
    categories: Optional[List[enums.CourseCategory]] = None,
    owner_id: Optional[int] = None
) -> List[Course]:
    logger.debug(f"Fetching courses with skip: {skip}, limit: {limit}, levels: {levels}, categories: {categories}, owner_id: {owner_id}")
    query = db.query(Course)
    if levels:
        query = query.filter(Course.level.in_(levels))
    if categories:
        query = query.filter(Course.category.in_(categories))
    if owner_id is not None:
        query = query.filter(Course.owner_id == owner_id)

    return query.order_by(Course.id.desc()).offset(skip).limit(limit).all()

def update_course(db: Session, course_id: int, course_in: schemas.CourseUpdate) -> Optional[Course]:
    db_course = get_course(db, course_id)
    if not db_course:
        logger.warning(f"Course with ID {course_id} not found for update.")
        return None

    logger.debug(f"Updating course ID: {course_id} with data: {course_in.model_dump(exclude_unset=True)}")
    db_course = update_db_object(db_course, course_in)

    db.commit()
    db.refresh(db_course)
    logger.info(f"Course '{db_course.title}' (ID: {db_course.id}) updated successfully.")
    return db_course

def delete_course(db: Session, course_id: int) -> bool:
    db_course = get_course(db, course_id)
    if not db_course:
        logger.warning(f"Course with ID {course_id} not found for deletion.")
        return False

    logger.debug(f"Deleting course ID: {course_id} ('{db_course.title}')")
    db.delete(db_course)
    db.commit()
    logger.info(f"Course ID: {course_id} ('{db_course.title}') deleted successfully.")
    return True

# --- CourseModule CRUD ---
def create_course_module(db: Session, module_in: schemas.CourseModuleCreate, course_id: int) -> CourseModule:
    logger.debug(f"Creating module '{module_in.title}' for course_id {course_id}")
    # Ensure course exists
    course = get_course(db, course_id)
    if not course:
        logger.error(f"Course with ID {course_id} not found. Cannot create module.")
        raise ValueError(f"Course with ID {course_id} not found.") # Or handle more gracefully

    db_module = CourseModule(**module_in.model_dump(), course_id=course_id)
    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    logger.info(f"Module '{db_module.title}' (ID: {db_module.id}) created for course ID {course_id}.")
    return db_module

def get_module(db: Session, module_id: int) -> Optional[CourseModule]:
    logger.debug(f"Fetching module with ID: {module_id}")
    return db.query(CourseModule).filter(CourseModule.id == module_id).first()

def get_modules_for_course(db: Session, course_id: int, skip: int = 0, limit: int = 100) -> List[CourseModule]:
    logger.debug(f"Fetching modules for course_id {course_id} with skip: {skip}, limit: {limit}")
    return db.query(CourseModule).filter(CourseModule.course_id == course_id).order_by(CourseModule.module_order).offset(skip).limit(limit).all()

def update_course_module(db: Session, module_id: int, module_in: schemas.CourseModuleUpdate) -> Optional[CourseModule]:
    db_module = get_module(db, module_id)
    if not db_module:
        logger.warning(f"Module with ID {module_id} not found for update.")
        return None

    logger.debug(f"Updating module ID: {module_id} with data: {module_in.model_dump(exclude_unset=True)}")
    db_module = update_db_object(db_module, module_in)

    db.commit()
    db.refresh(db_module)
    logger.info(f"Module '{db_module.title}' (ID: {db_module.id}) updated successfully.")
    return db_module

def delete_course_module(db: Session, module_id: int) -> bool:
    db_module = get_module(db, module_id)
    if not db_module:
        logger.warning(f"Module with ID {module_id} not found for deletion.")
        return False

    logger.debug(f"Deleting module ID: {module_id} ('{db_module.title}')")
    db.delete(db_module)
    db.commit()
    logger.info(f"Module ID: {module_id} ('{db_module.title}') deleted successfully.")
    return True

# --- ModuleContent CRUD ---
def create_module_content(db: Session, content_in: schemas.ModuleContentCreate, module_id: int) -> ModuleContent:
    logger.debug(f"Creating content '{content_in.title}' for module_id {module_id}")
    module = get_module(db, module_id)
    if not module:
        logger.error(f"Module with ID {module_id} not found. Cannot create content.")
        raise ValueError(f"Module with ID {module_id} not found.")

    content_data = content_in.model_dump(exclude={'quiz_data'}) # Exclude quiz_data for now
    db_content = ModuleContent(**content_data, module_id=module_id)

    if content_in.content_type == enums.ModuleContentType.QUIZ and content_in.quiz_data:
        logger.debug(f"Content type is QUIZ, creating associated quiz for '{content_in.title}'")
        quiz_in = content_in.quiz_data
        # The Quiz model expects module_content_id, which isn't available until db_content is flushed.
        # So, we create Quiz separately or handle it carefully.
        # For now, let's create content, then quiz, then associate.
        # A more robust way involves creating Quiz with questions/options first, then linking its ID.
        # Or, create content, flush to get ID, create quiz, then link.

        # Simplified: Create content first, then quiz, then associate.
        # This means the quiz creation logic needs to be called *after* content is flushed.
        # This function will just create the ModuleContent object for now.
        # The association of Quiz will be handled in the route or a service layer.
        pass # Quiz creation and association will be handled by a dedicated function or route logic

    db.add(db_content)
    db.commit()
    db.refresh(db_content)
    logger.info(f"Content '{db_content.title}' (ID: {db_content.id}) created for module ID {module_id}.")
    return db_content

def get_content(db: Session, content_id: int) -> Optional[ModuleContent]:
    logger.debug(f"Fetching content with ID: {content_id}")
    return db.query(ModuleContent).filter(ModuleContent.id == content_id).first()

def get_contents_for_module(db: Session, module_id: int, skip: int = 0, limit: int = 100) -> List[ModuleContent]:
    logger.debug(f"Fetching contents for module_id {module_id} with skip: {skip}, limit: {limit}")
    return db.query(ModuleContent).filter(ModuleContent.module_id == module_id).order_by(ModuleContent.content_order).offset(skip).limit(limit).all()

def update_module_content(db: Session, content_id: int, content_in: schemas.ModuleContentUpdate) -> Optional[ModuleContent]:
    db_content = get_content(db, content_id)
    if not db_content:
        logger.warning(f"Content with ID {content_id} not found for update.")
        return None

    logger.debug(f"Updating content ID: {content_id} with data: {content_in.model_dump(exclude_unset=True, exclude={'quiz_data'})}")
    db_content = update_db_object(db_content, content_in)

    # Handling quiz update is more complex and might need dedicated logic
    # if content_in.quiz_data and db_content.content_type == enums.ModuleContentType.QUIZ:
    #   ... update or create quiz ...

    db.commit()
    db.refresh(db_content)
    logger.info(f"Content '{db_content.title}' (ID: {db_content.id}) updated successfully.")
    return db_content

def delete_module_content(db: Session, content_id: int) -> bool:
    db_content = get_content(db, content_id)
    if not db_content:
        logger.warning(f"Content with ID {content_id} not found for deletion.")
        return False

    logger.debug(f"Deleting content ID: {content_id} ('{db_content.title}')")
    db.delete(db_content) # Associated quiz (if any) should be deleted by cascade if set up correctly
    db.commit()
    logger.info(f"Content ID: {content_id} ('{db_content.title}') deleted successfully.")
    return True

# --- Quiz, Question, QuestionOption CRUD ---
# These are more complex due to nesting.

def create_quiz_for_content(db: Session, quiz_in: schemas.QuizCreate, module_content_id: int) -> Quiz:
    logger.debug(f"Creating quiz '{quiz_in.title}' for module_content_id {module_content_id}")
    content_item = get_content(db, module_content_id)
    if not content_item:
        logger.error(f"ModuleContent with ID {module_content_id} not found. Cannot create quiz.")
        raise ValueError(f"ModuleContent with ID {module_content_id} not found.")
    if content_item.content_type != enums.ModuleContentType.QUIZ:
        logger.error(f"ModuleContent ID {module_content_id} is not of type QUIZ. Cannot attach quiz.")
        raise ValueError(f"ModuleContent ID {module_content_id} is not of type QUIZ.")
    if content_item.quiz_association: # Check if quiz already exists
        logger.error(f"ModuleContent ID {module_content_id} already has a quiz (ID: {content_item.quiz_association.id}).")
        raise IntegrityError(f"Quiz already exists for ModuleContent ID {module_content_id}.", params={}, orig=None)


    db_quiz = Quiz(
        title=quiz_in.title,
        description=quiz_in.description,
        module_content_id=module_content_id
    )
    db.add(db_quiz)
    # Must commit or flush to get db_quiz.id for questions
    db.flush() # Flush to get ID without ending transaction

    questions_to_add = []
    for q_idx, question_in in enumerate(quiz_in.questions):
        db_question = Question(
            quiz_id=db_quiz.id,
            question_text=question_in.question_text,
            question_type=question_in.question_type,
            question_order=question_in.question_order if question_in.question_order is not None else q_idx,
            explanation=question_in.explanation
        )
        db.add(db_question)
        db.flush() # Get question ID for options

        options_to_add = []
        for opt_in in question_in.options:
            db_option = QuestionOption(
                question_id=db_question.id,
                option_text=opt_in.option_text,
                is_correct=opt_in.is_correct
            )
            options_to_add.append(db_option)
        if options_to_add:
            db.add_all(options_to_add)

        # db_question.options.extend(options_to_add) # Alternative way to add options if relationship is configured for it
        questions_to_add.append(db_question)

    # db_quiz.questions.extend(questions_to_add) # Alternative way

    db.commit() # Commit everything: quiz, questions, options
    db.refresh(db_quiz)
    # Need to refresh questions and options if accessed immediately
    for q in db_quiz.questions:
        db.refresh(q)
        for opt in q.options:
            db.refresh(opt)

    logger.info(f"Quiz '{db_quiz.title}' (ID: {db_quiz.id}) and its questions/options created for content ID {module_content_id}.")
    return db_quiz

def get_quiz_with_questions(db: Session, quiz_id: int) -> Optional[Quiz]:
    logger.debug(f"Fetching quiz with ID: {quiz_id} along with questions and options")
    # This will load related questions and options due to relationship configurations (lazy/eager loading)
    return db.query(Quiz).filter(Quiz.id == quiz_id).first()
    # For explicit loading (if not configured for eager loading by default):
    # from sqlalchemy.orm import joinedload, subqueryload
    # return db.query(Quiz).options(
    #     joinedload(Quiz.questions).subqueryload(Question.options)
    # ).filter(Quiz.id == quiz_id).first()


def update_quiz(db: Session, quiz_id: int, quiz_in: schemas.QuizUpdate) -> Optional[Quiz]:
    db_quiz = get_quiz_with_questions(db, quiz_id)
    if not db_quiz:
        logger.warning(f"Quiz with ID {quiz_id} not found for update.")
        return None

    logger.debug(f"Updating quiz ID: {quiz_id} with data: {quiz_in.model_dump(exclude_unset=True, exclude={'questions'})}")
    # Update basic quiz fields
    if quiz_in.title is not None:
        db_quiz.title = quiz_in.title
    if quiz_in.description is not None:
        db_quiz.description = quiz_in.description

    # Updating questions and options is complex:
    # - Identify new, updated, deleted questions.
    # - For each question, identify new, updated, deleted options.
    # This typically requires more sophisticated logic, possibly deleting all existing
    # questions/options and recreating them from quiz_in.questions, or doing a detailed diff.
    # For simplicity in this example, we'll skip direct update of questions/options here.
    # This should be handled by dedicated endpoints for questions/options or more advanced service logic.
    if quiz_in.questions is not None:
        logger.warning(f"Updating questions within a quiz (ID: {quiz_id}) via this method is not fully supported. Please manage questions separately.")
        # Placeholder for more complex logic if needed in future:
        # current_question_ids = {q.id for q in db_quiz.questions}
        # incoming_questions_map = {q.id: q for q in quiz_in.questions if isinstance(q, schemas.QuestionUpdate) and q.id}
        # ... etc.

    db.commit()
    db.refresh(db_quiz)
    logger.info(f"Quiz '{db_quiz.title}' (ID: {db_quiz.id}) updated.")
    return db_quiz

# CRUD for Questions and Options can be added similarly if direct manipulation is needed.
# For example:
# def create_question_for_quiz(db: Session, question_in: schemas.QuestionCreate, quiz_id: int) -> Question: ...
# def update_question(db: Session, question_id: int, question_in: schemas.QuestionUpdate) -> Optional[Question]: ...
# def delete_question(db: Session, question_id: int) -> bool: ...
# And similar for QuestionOption.

# For now, Quiz creation includes its questions and options. Updating them would typically be
# done by deleting and recreating, or by more granular Question/Option CRUD if required by API design.


def submit_quiz(
    db: Session,
    quiz_id: int,
    user_id: int,
    submission_in: quiz_submission_schema.QuizSubmissionCreate
) -> quiz_submission_schema.QuizResultDisplay:
    """
    Processes a quiz submission, calculates the score, and records the attempt.
    The score is stored in UserProgress for the ModuleContent associated with the Quiz.
    """
    logger.info(f"Processing quiz submission for quiz_id {quiz_id} by user_id {user_id}")

    db_quiz = get_quiz_with_questions(db, quiz_id)
    if not db_quiz:
        logger.error(f"Quiz with ID {quiz_id} not found for submission.")
        raise ValueError(f"Quiz with ID {quiz_id} not found.")
    if not db_quiz.content_association: # Should always exist if data is consistent
        logger.error(f"Quiz ID {quiz_id} is not associated with any ModuleContent.")
        raise ValueError(f"Quiz ID {quiz_id} has no parent ModuleContent.")

    module_content_id = db_quiz.module_content_id
    course_id = db_quiz.content_association.module.course_id # Get course_id from grandparent

    total_questions = len(db_quiz.questions)
    if total_questions == 0:
        logger.warning(f"Quiz ID {quiz_id} has no questions. Score is 0%.")
        # Record progress even for empty quiz?
        progress_update_data = user_progress_schema.UserProgressUpdate(
            score_percentage=0.0,
            completed_at=datetime.utcnow() # Mark as completed
        )
        create_or_update_user_progress(db, user_id, module_content_id, course_id, progress_update_data)
        return quiz_submission_schema.QuizResultDisplay(
            quiz_id=quiz_id,
            module_content_id=module_content_id,
            score_percentage=0.0,
            total_questions=0,
            correct_answers_count=0,
            message="Quiz has no questions."
        )

    correct_answers_count = 0
    # answer_feedback_list = [] # For detailed feedback, if implemented later

    # Create a map of question_id to correct option_ids for faster lookup
    correct_options_map = {}
    for q in db_quiz.questions:
        correct_options_map[q.id] = {opt.id for opt in q.options if opt.is_correct}

    for answer in submission_in.answers:
        question_id = answer.question_id
        selected_option_id = answer.selected_option_id

        # Basic validation: does the question belong to this quiz?
        # This can be more robust by fetching the question and checking its quiz_id.
        if question_id not in correct_options_map:
            logger.warning(f"Answer provided for question_id {question_id} which is not in quiz {quiz_id}. Skipping.")
            # Or raise error: raise ValueError(f"Invalid question_id {question_id} for quiz {quiz_id}")
            continue

        is_correct = False
        if selected_option_id and selected_option_id in correct_options_map[question_id]:
            correct_answers_count += 1
            is_correct = True

        # For detailed feedback (future enhancement)
        # current_q = next((q for q in db_quiz.questions if q.id == question_id), None)
        # correct_opt_id = list(correct_options_map[question_id])[0] if correct_options_map[question_id] else None
        # explanation = current_q.explanation if current_q else None
        # answer_feedback_list.append(quiz_submission_schema.AnswerFeedback(
        #     question_id=question_id,
        #     submitted_answer=answer,
        #     is_correct=is_correct,
        #     correct_option_id=correct_opt_id,
        #     explanation=explanation
        # ))

    score_percentage = round((correct_answers_count / total_questions) * 100, 2) if total_questions > 0 else 0.0
    logger.info(f"Quiz {quiz_id} submitted by user {user_id}. Score: {correct_answers_count}/{total_questions} ({score_percentage}%)")

    # Update UserProgress for the ModuleContent (which is the Quiz)
    progress_update_data = user_progress_schema.UserProgressUpdate(
        score_percentage=score_percentage,
        completed_at=datetime.utcnow() # Mark quiz content as completed upon submission
    )
    create_or_update_user_progress(
        db=db,
        user_id=user_id,
        content_id=module_content_id,
        course_id=course_id,
        progress_in=progress_update_data
    )

    # Send quiz results email
    try:
        user = user_crud.get_user_by_id(db, user_id)
        if user:
            email_context = {
                "user_name": user.email, # Or a display name
                "quiz_title": db_quiz.title,
                "course_title": db_quiz.content_association.module.course.title, # Assumes relationships are loaded or accessible
                "course_id": course_id,
                "score_percentage": score_percentage,
            }
            email_service.send_templated_email(
                to_email=user.email,
                subject=f"Your Results for Quiz: {db_quiz.title}",
                html_template_name="quiz_results.html",
                context=email_context
            )
            logger.info(f"Quiz results email queued for user {user.email} for quiz {db_quiz.title}")
        else:
            logger.warning(f"User with ID {user_id} not found for sending quiz results email.")
    except Exception as email_exc:
        logger.error(f"Failed to send quiz results email to user ID {user_id}: {email_exc}", exc_info=True)
        # Do not let email failure roll back the quiz submission transaction or fail the request.

    return quiz_submission_schema.QuizResultDisplay(
        quiz_id=quiz_id,
        module_content_id=module_content_id,
        score_percentage=score_percentage,
        total_questions=total_questions,
        correct_answers_count=correct_answers_count,
        # feedback=answer_feedback_list # If detailed feedback is enabled
    )
