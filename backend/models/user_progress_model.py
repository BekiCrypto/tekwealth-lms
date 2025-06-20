from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, UniqueConstraint, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.core.database import Base

class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("module_content.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False) # Denormalized for easier querying

    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    playback_position_seconds = Column(Integer, nullable=True) # For videos
    score_percentage = Column(Float, nullable=True) # For quizzes (e.g., 85.5 for 85.5%)

    last_accessed_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="progress_entries") # Changed from "progress"
    content = relationship("ModuleContent", back_populates="user_progress_entries") # Changed from "user_progress"
    course = relationship("Course", back_populates="user_progress_entries") # Changed from "user_progress"

    __table_args__ = (
        UniqueConstraint('user_id', 'content_id', name='uq_user_content_progress'),
    )

    def __repr__(self):
        return f"<UserProgress(id={self.id}, user_id={self.user_id}, content_id={self.content_id}, course_id={self.course_id}, completed={'Yes' if self.completed_at else 'No'})>"
