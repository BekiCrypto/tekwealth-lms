from pydantic import BaseModel, Field
from typing import List, Optional, Union

# --- Quiz Answer Schemas ---
class QuizAnswerBase(BaseModel):
    question_id: int = Field(..., description="ID of the question being answered")
    # For multiple choice or single choice from predefined options
    selected_option_id: Optional[int] = Field(None, description="ID of the selected option (for MCQs/SCQs)")
    # For True/False, selected_option_id could refer to an option representing True or False,
    # or a boolean field could be used, e.g., answer_boolean: Optional[bool]
    # For open-ended questions (not in current QuestionType enum but for future)
    # answer_text: Optional[str] = Field(None, description="Text answer for open-ended questions")

    # Example validation: one of selected_option_id or answer_text must be provided
    # @root_validator
    # def check_answer_provided(cls, values):
    #     if values.get('selected_option_id') is None and values.get('answer_text') is None:
    #         raise ValueError('Either selected_option_id or answer_text must be provided')
    #     if values.get('selected_option_id') is not None and values.get('answer_text') is not None:
    #         raise ValueError('Provide either selected_option_id or answer_text, not both')
    #     return values

class QuizAnswerCreate(QuizAnswerBase):
    pass

# --- Quiz Submission Schemas ---
class QuizSubmissionCreate(BaseModel):
    # quiz_id is typically a path parameter, not in the body for user submission
    # user_id is derived from the authenticated user token
    answers: List[QuizAnswerCreate] = Field(..., description="List of answers submitted by the user")

# --- Quiz Result Schemas ---
# For displaying feedback on individual answers (more detailed)
class AnswerFeedback(BaseModel):
    question_id: int
    submitted_answer: QuizAnswerBase # What the user submitted
    is_correct: bool
    correct_option_id: Optional[int] = None # If applicable
    # correct_answer_text: Optional[str] = None # For open-ended
    explanation: Optional[str] = None # Explanation from the Question model

class QuizResultDisplay(BaseModel):
    quiz_id: int
    module_content_id: int # The ModuleContent ID this quiz is part of
    score_percentage: float = Field(..., ge=0, le=100, description="Overall score percentage (e.g., 85.5)")
    total_questions: int = Field(..., gt=0, description="Total number of questions in the quiz")
    correct_answers_count: int = Field(..., ge=0, description="Number of correctly answered questions")
    # feedback: Optional[List[AnswerFeedback]] = None # Detailed feedback per question (can be large)
    message: Optional[str] = "Quiz submitted successfully. Your score has been recorded."

    class Config:
        from_attributes = True # If this schema is ever populated from a model attribute directly.
                               # Usually, it's constructed in the backend route.
