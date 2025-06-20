import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from backend.core.config import settings # To get API key and default model

logger = logging.getLogger(__name__)

# Initialize OpenAI client
# It's good practice to initialize it once and reuse.
# This could be done at module level or within a class structure.
if not settings.OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not set. AI Service will not function.")
    client = None
else:
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
        client = None

def get_ai_chat_response(
    prompt: str,
    system_message: Optional[str] = "You are a helpful AI assistant for an e-learning platform.",
    course_title: Optional[str] = None,
    user_query_context: Optional[str] = None, # Specific context for the user's query if any
    chat_history: Optional[List[Dict[str, str]]] = None # e.g., [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
) -> str:
    """
    Gets a chat response from OpenAI's ChatCompletion API.

    Args:
        prompt: The user's current message/query.
        system_message: The system prompt to guide AI behavior.
        course_title: Optional title of the course for context.
        user_query_context: Optional specific textual context related to the user's query.
        chat_history: Optional list of previous messages in the conversation.

    Returns:
        The text response from the AI, or an error message string.
    """
    if not client:
        return "AI service is not configured. Please contact support."

    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})

    context_parts = []
    if course_title:
        context_parts.append(f"The user is currently interacting with a course titled '{course_title}'.")
    if user_query_context:
        context_parts.append(f"Here is some relevant context for their query: {user_query_context}")

    if context_parts:
        # Add context as a system or assistant message before user history or current prompt
        messages.append({"role": "system", "content": " ".join(context_parts)}) # Or assistant role

    if chat_history:
        messages.extend(chat_history)

    messages.append({"role": "user", "content": prompt})

    try:
        logger.debug(f"Sending chat completion request to OpenAI. Model: {settings.OPENAI_MODEL_NAME}. Messages count: {len(messages)}")
        completion = client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            temperature=0.7, # Adjust for creativity vs. factuality
            max_tokens=1000, # Adjust based on expected response length
            # top_p=1.0,
            # frequency_penalty=0.0,
            # presence_penalty=0.0,
        )
        response_message = completion.choices[0].message.content
        logger.info(f"Received chat response from OpenAI. Finish reason: {completion.choices[0].finish_reason}")
        return response_message.strip() if response_message else "Sorry, I couldn't generate a response."

    except APIError as e:
        logger.error(f"OpenAI API error: {e}", exc_info=True)
        return f"An error occurred with the AI service (API Error): {e}"
    except APITimeoutError:
        logger.error("OpenAI API request timed out.", exc_info=True)
        return "The AI service request timed out. Please try again."
    except RateLimitError:
        logger.error("OpenAI API rate limit exceeded.", exc_info=True)
        return "AI service is currently unavailable due to high demand. Please try again later."
    except Exception as e:
        logger.error(f"An unexpected error occurred while contacting OpenAI: {e}", exc_info=True)
        return "An unexpected error occurred with the AI service."


def generate_quiz_questions_from_text(
    text_content: str,
    num_questions: int = 3,
    question_type: str = "multiple_choice" # Could be enum in future
) -> List[Dict[str, Any]]:
    """
    Generates quiz questions from a given text using OpenAI.

    Args:
        text_content: The text to generate quiz questions from.
        num_questions: Desired number of questions.
        question_type: Type of questions (e.g., "multiple_choice").

    Returns:
        A list of dictionaries, each representing a question, or empty list on error.
        Example: [{"question_text": "...", "options": [{"option_text": "...", "is_correct": True/False}, ...], "question_type": "multiple_choice"}]
    """
    if not client:
        logger.warning("AI service not configured. Cannot generate quiz questions.")
        return []

    if question_type != "multiple_choice": # For now, only support MCQs
        logger.warning(f"Unsupported question type '{question_type}' requested for AI generation.")
        return []

    # Constructing the prompt for the LLM
    prompt_lines = [
        f"Generate {num_questions} multiple-choice quiz questions based on the following text.",
        "Each question should have 4 options. Clearly indicate the single correct option for each question.",
        "Provide the output strictly in JSON format: a list of objects, where each object has keys 'question_text' (string), 'question_type' (string, set to 'multiple_choice'), and 'options' (a list of objects, each with 'option_text' (string) and 'is_correct' (boolean)).",
        "Example for one question:",
        """
        {
            "question_text": "What is the capital of France?",
            "question_type": "multiple_choice",
            "options": [
                {"option_text": "Berlin", "is_correct": false},
                {"option_text": "Madrid", "is_correct": false},
                {"option_text": "Paris", "is_correct": true},
                {"option_text": "Rome", "is_correct": false}
            ]
        }
        """,
        "Ensure the JSON is valid. Do not include any explanations or text outside the JSON list structure.",
        "\nText Content to use:\n---\n",
        text_content,
        "\n---\nGenerated JSON questions:"
    ]
    full_prompt = "\n".join(prompt_lines)

    try:
        logger.debug(f"Sending quiz generation request to OpenAI. Model: {settings.OPENAI_MODEL_NAME}.")
        # Using the chat completion endpoint for structured JSON output is often more reliable
        # by guiding the model with a system message and expecting a JSON response.
        messages = [
            {"role": "system", "content": "You are an AI assistant that generates quiz questions in valid JSON format based on provided text."},
            {"role": "user", "content": full_prompt}
        ]

        completion = client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME, # Or a model known for good JSON output like gpt-4-turbo-preview
            messages=messages,
            temperature=0.5, # Lower temperature for more deterministic JSON structure
            max_tokens=1500, # Adjust based on num_questions and text_content length
            # response_format={"type": "json_object"} # For newer models that support this explicitly
        )

        raw_response = completion.choices[0].message.content
        logger.info(f"Received quiz generation response from OpenAI. Finish reason: {completion.choices[0].finish_reason}")

        if not raw_response:
            logger.error("OpenAI returned an empty response for quiz generation.")
            return []

        # Attempt to parse the JSON response
        # The response might be a string containing JSON, or might need cleaning.
        # Look for the start of the JSON list '[' and end ']'
        try:
            json_start_index = raw_response.find('[')
            json_end_index = raw_response.rfind(']')
            if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
                json_str = raw_response[json_start_index : json_end_index+1]
                import json
                generated_questions = json.loads(json_str)
                # Basic validation of structure (can be more robust with Pydantic models)
                if not isinstance(generated_questions, list):
                    raise ValueError("Generated JSON is not a list.")
                for q in generated_questions:
                    if not all(k in q for k in ["question_text", "options", "question_type"]):
                        raise ValueError("Generated question missing required keys.")
                    if not isinstance(q["options"], list) or not all(isinstance(opt, dict) and "option_text" in opt and "is_correct" in opt for opt in q["options"]):
                        raise ValueError("Generated question has malformed options.")
                logger.info(f"Successfully parsed {len(generated_questions)} questions from OpenAI response.")
                return generated_questions
            else:
                logger.error(f"Could not find valid JSON list in OpenAI response: {raw_response}")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from OpenAI response: {e}. Response was: {raw_response}", exc_info=True)
            return []
        except ValueError as e: # Custom validation errors
            logger.error(f"Validation error in generated JSON structure: {e}. Response was: {raw_response}", exc_info=True)
            return []

    except APIError as e:
        logger.error(f"OpenAI API error during quiz generation: {e}", exc_info=True)
    except APITimeoutError:
        logger.error("OpenAI API request for quiz generation timed out.", exc_info=True)
    except RateLimitError:
        logger.error("OpenAI API rate limit exceeded during quiz generation.", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during quiz generation: {e}", exc_info=True)

    return []
