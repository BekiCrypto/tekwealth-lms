from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
import logging

from backend.core.database import get_db
from backend.core.dependencies import get_current_active_user, get_current_admin_user # Or a course owner/admin dependency
from backend.models.user_model import User
from backend.schemas import ai_schema as schemas # AI specific schemas
from backend.services import ai_service # The service layer for OpenAI calls
from backend.crud import course_crud # To fetch course context if needed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Powered Features"])

@router.post("/chat", response_model=schemas.AIChatResponse)
async def handle_ai_chat(
    chat_request: schemas.AIChatRequest,
    db: Session = Depends(get_db), # If context fetching needs DB
    current_user: User = Depends(get_current_active_user) # Ensure user is authenticated
):
    """
    Handles a user's chat message, gets a response from the AI assistant.
    Optionally uses course context if `course_id` is provided.
    """
    logger.info(f"User {current_user.email} initiated AI chat. Prompt: '{chat_request.prompt[:50]}...'")

    course_title_context: Optional[str] = None
    # More detailed context can be fetched here, e.g., specific module content if relevant IDs are passed.
    if chat_request.course_id:
        course = course_crud.get_course(db, chat_request.course_id)
        if course:
            course_title_context = course.title
            logger.debug(f"AI chat context: Course ID {chat_request.course_id}, Title: {course.title}")
        else:
            logger.warning(f"Course ID {chat_request.course_id} provided for AI chat not found.")
            # Decide if this should be an error or just proceed without course context.
            # For now, proceed without, but AI will be informed if course not found.
            course_title_context = f"(Course ID {chat_request.course_id} not found)"


    # Prepare chat history if provided
    history_for_ai = []
    if chat_request.chat_history:
        for msg in chat_request.chat_history:
            history_for_ai.append({"role": msg.role, "content": msg.content})

    ai_response_text = ai_service.get_ai_chat_response(
        prompt=chat_request.prompt,
        course_title=course_title_context,
        # user_query_context= "some specific text from a module could go here", # Example
        chat_history=history_for_ai
    )

    if "AI service is not configured" in ai_response_text or \
       "An error occurred" in ai_response_text or \
       "timed out" in ai_response_text:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ai_response_text)

    return schemas.AIChatResponse(ai_message=ai_response_text)


@router.post("/generate-quiz-questions", response_model=schemas.QuizGenerationResponse)
async def generate_quiz_from_text_content(
    request_data: schemas.QuizGenerationRequest,
    # Protected for admin or course owner for now
    # current_user: User = Depends(get_current_admin_user) # Or a more specific content owner/admin dependency
    current_user: User = Depends(get_current_active_user) # MVP: Any authenticated user can try
):
    """
    Generates a list of quiz questions based on provided text content using AI.
    (Further integration would involve saving these as drafts or directly into courses).
    """
    logger.info(f"User {current_user.email} requested AI quiz generation. Num questions: {request_data.num_questions}. Content length: {len(request_data.text_content)}")

    if len(request_data.text_content) < 100: # Arbitrary minimum length
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text content is too short for meaningful quiz generation.")

    generated_questions_raw = ai_service.generate_quiz_questions_from_text(
        text_content=request_data.text_content,
        num_questions=request_data.num_questions
        # question_type can be added if supported by service and schema
    )

    if not generated_questions_raw:
        logger.error(f"AI service failed to generate quiz questions for user {current_user.email}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate quiz questions from AI service.")

    # Validate and parse into the response schema.
    # The ai_service.generate_quiz_questions_from_text already tries to parse into the correct dict structure.
    # Pydantic will validate it here when creating QuizGenerationResponse.
    try:
        # Ensure the raw dictionaries conform to GeneratedQuestion schema parts
        # This is implicitly done by Pydantic when creating QuizGenerationResponse
        # If parsing/validation failed in service, generated_questions_raw would be empty or raise error there.
        parsed_questions = [schemas.GeneratedQuestion(**q) for q in generated_questions_raw]
    except Exception as e: # Catch potential Pydantic validation errors if structure is off
        logger.error(f"Failed to validate AI generated questions against schema: {e}", exc_info=True)
        logger.error(f"Raw questions received from AI: {generated_questions_raw}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI generated unexpected question format.")


    return schemas.QuizGenerationResponse(generated_questions=parsed_questions)
