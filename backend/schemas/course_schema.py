from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Union
from datetime import datetime

from backend.models.enums import CourseLevel, CourseCategory, ModuleContentType, QuestionType
# Assuming UserDisplay schema will be available for owner information
# To avoid circular imports, we can use forward references if UserDisplay imports CourseDisplay
# from .user_schema import UserDisplay # Full import might cause issues if user_schema also imports course_schema
from typing import ForwardRef

UserDisplayRef = ForwardRef('UserDisplay') # Forward reference for UserDisplay

# --- QuestionOption Schemas ---
class QuestionOptionBase(BaseModel):
    option_text: str = Field(..., min_length=1, max_length=500, description="Text content of the option")
    is_correct: bool = Field(False, description="Is this the correct option?")

class QuestionOptionCreate(QuestionOptionBase):
    pass

class QuestionOptionUpdate(BaseModel):
    option_text: Optional[str] = Field(None, min_length=1, max_length=500)
    is_correct: Optional[bool] = None

class QuestionOptionDisplay(QuestionOptionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Question Schemas ---
class QuestionBase(BaseModel):
    question_text: str = Field(..., min_length=10, description="The text of the question")
    question_type: QuestionType = Field(..., description="Type of question (e.g., MultipleChoice)")
    question_order: Optional[int] = Field(0, description="Order of the question within the quiz")
    explanation: Optional[str] = Field(None, max_length=1000, description="Explanation for the correct answer")

class QuestionCreate(QuestionBase):
    options: List[QuestionOptionCreate] = Field(default_factory=list, description="List of options for this question")

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(None, min_length=10)
    question_type: Optional[QuestionType] = None
    question_order: Optional[int] = None
    explanation: Optional[str] = Field(None, max_length=1000)
    options: Optional[List[Union[QuestionOptionCreate, QuestionOptionUpdate, int]]] = None # For adding, updating, or linking existing by ID (advanced)

class QuestionDisplay(QuestionBase):
    id: int
    options: List[QuestionOptionDisplay] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Quiz Schemas ---
class QuizBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Title of the quiz")
    description: Optional[str] = Field(None, max_length=2000, description="Detailed description of the quiz")

class QuizCreate(QuizBase):
    questions: List[QuestionCreate] = Field(default_factory=list, description="List of questions for this quiz")

class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    questions: Optional[List[Union[QuestionCreate, QuestionUpdate, int]]] = None # For adding, updating, or linking

class QuizDisplay(QuizBase):
    id: int
    module_content_id: int # Link back to the ModuleContent
    questions: List[QuestionDisplay] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- ModuleContent Schemas ---
class ModuleContentBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Title of the content item")
    content_order: Optional[int] = Field(0, description="Order of content within the module")
    content_type: ModuleContentType = Field(..., description="Type of content (Video, PDF, Quiz, Text)")
    content_url: Optional[HttpUrl] = Field(None, description="URL for Video/PDF content. Use str if HttpUrl is too strict.")
    text_content: Optional[str] = Field(None, description="Text for Text type content")
    estimated_completion_time_minutes: Optional[int] = Field(None, gt=0, description="Estimated time in minutes to complete this content")

class ModuleContentCreate(ModuleContentBase):
    # If content_type is QUIZ, quiz_data should be provided.
    quiz_data: Optional[QuizCreate] = Field(None, description="Quiz details, if content type is QUIZ")

    # Basic validation, more complex validation can be done in routers or services
    # @validator('quiz_data', always=True)
    # def check_quiz_data_for_quiz_type(cls, v, values):
    #     if values.get('content_type') == ModuleContentType.QUIZ and not v:
    #         raise ValueError('quiz_data is required for content_type QUIZ')
    #     if values.get('content_type') != ModuleContentType.QUIZ and v:
    #         raise ValueError('quiz_data should only be provided for content_type QUIZ')
    #     return v

class ModuleContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content_order: Optional[int] = None
    content_type: Optional[ModuleContentType] = None # Be cautious allowing type changes
    content_url: Optional[HttpUrl] = None
    text_content: Optional[str] = None
    estimated_completion_time_minutes: Optional[int] = Field(None, gt=0)
    quiz_data: Optional[Union[QuizCreate, QuizUpdate]] = None # For creating or updating associated quiz

class ModuleContentDisplay(ModuleContentBase):
    id: int
    quiz_association: Optional[QuizDisplay] = None # Display quiz if associated
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- CourseModule Schemas ---
class CourseModuleBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Title of the module")
    module_order: Optional[int] = Field(0, description="Order of the module within the course")

class CourseModuleCreate(CourseModuleBase):
    # Contents will be added via separate endpoints for simplicity in this version
    # contents: List[ModuleContentCreate] = Field(default_factory=list)
    pass

class CourseModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    module_order: Optional[int] = None
    # contents: Optional[List[Union[ModuleContentCreate, ModuleContentUpdate, int]]] = None # For managing contents

class CourseModuleDisplay(CourseModuleBase):
    id: int
    course_id: int
    contents: List[ModuleContentDisplay] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Course Schemas ---
class CourseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Title of the course")
    description: Optional[str] = Field(None, description="Detailed description of the course")
    level: CourseLevel = Field(..., description="Difficulty level of the course")
    category: CourseCategory = Field(..., description="Category of the course")

class CourseCreate(CourseBase):
    # Modules will be added via separate endpoints for simplicity in this version
    # modules: List[CourseModuleCreate] = Field(default_factory=list)
    # owner_id will be set from the authenticated user in the route
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    level: Optional[CourseLevel] = None
    category: Optional[CourseCategory] = None
    # modules: Optional[List[Union[CourseModuleCreate, CourseModuleUpdate, int]]] = None # For managing modules

class CourseDisplay(CourseBase):
    id: int
    owner_id: Optional[int] = None # Made optional to handle if owner is None (e.g. system course)
    owner: Optional[UserDisplayRef] = None # Using ForwardRef for UserDisplay
    modules: List[CourseModuleDisplay] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Update ForwardRefs - This needs to be done after all relevant schemas are defined.
# This is typically done in the __init__.py of the schemas package or at the end of this file
# if UserDisplay is also defined here (which it isn't).
# For now, this forward ref will be resolved if UserDisplay is imported correctly where CourseDisplay is used.
# If user_schema.py also uses CourseDisplay, then both need careful handling of imports or use ForwardRef.
# Example: user_schema.UserDisplay.update_forward_refs(CourseDisplay=CourseDisplay)
# course_schema.CourseDisplay.update_forward_refs(UserDisplay=user_schema.UserDisplay)
# For simplicity, we'll assume this resolution happens correctly at runtime.
# The actual update_forward_refs call is typically done in __init__.py files or main model aggregation spots.

# Placeholder for list responses with pagination (optional, can be generic)
class PaginatedCourseList(BaseModel):
    total: int
    items: List[CourseDisplay]
    page: int
    size: int
# Similar paginated lists can be defined for other entities if needed.
