from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Assuming ModuleContentDisplay and CourseDisplay might be useful for context
# from .course_schema import ModuleContentDisplay, CourseDisplay # Avoid direct import for now if complex nesting

class UserProgressBase(BaseModel):
    playback_position_seconds: Optional[int] = Field(None, description="Playback position in seconds for video content")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the content was marked as completed")
    score_percentage: Optional[float] = Field(None, ge=0, le=100, description="Score percentage for quiz content (e.g., 85.5)")
    last_accessed_at: Optional[datetime] = Field(None, description="Timestamp of last access (usually auto-updated)")


class UserProgressCreate(UserProgressBase):
    # user_id, content_id, course_id will be set from path/token and context, not directly in request body for typical use cases
    # However, if an admin were to create this, they might need to specify these.
    # For user-driven progress, these are implicit.
    # For this schema, let's assume it's for internal use where these IDs are known.
    user_id: int
    content_id: int
    course_id: int


class UserProgressUpdate(UserProgressBase):
    # All fields are optional for updates
    pass


class UserProgressDisplay(UserProgressBase):
    id: int
    user_id: int
    content_id: int
    course_id: int
    # Potentially include simplified content/course info if needed, e.g., content_title, course_title
    # content: Optional[ModuleContentDisplay] = None # Example: if you want to nest related object
    # course: Optional[CourseDisplay] = None      # Example: if you want to nest related object

    class Config:
        from_attributes = True
