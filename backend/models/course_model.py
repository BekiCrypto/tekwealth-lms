from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, TIMESTAMP,
    Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.enums import CourseLevel, CourseCategory, ModuleContentType, QuestionType

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    level = Column(SAEnum(CourseLevel, name="course_level_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    category = Column(SAEnum(CourseCategory, name="course_category_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True) # Course can exist even if owner is deleted, or use CASCADE

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="courses_owned")
    modules = relationship("CourseModule", back_populates="course", cascade="all, delete-orphan", order_by="CourseModule.module_order")
    user_progress_entries = relationship("UserProgress", back_populates="course", cascade="all, delete-orphan")
    issued_certificates = relationship("Certificate", back_populates="course", cascade="all, delete-orphan")


    def __repr__(self):
        return f"<Course(id={self.id}, title='{self.title}')>"

class CourseModule(Base):
    __tablename__ = "course_modules"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    module_order = Column(Integer, nullable=False, default=0) # To order modules within a course

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    course = relationship("Course", back_populates="modules")
    contents = relationship("ModuleContent", back_populates="module", cascade="all, delete-orphan", order_by="ModuleContent.content_order")

    __table_args__ = (UniqueConstraint('course_id', 'module_order', name='uq_course_module_order'),)


    def __repr__(self):
        return f"<CourseModule(id={self.id}, title='{self.title}', course_id={self.course_id})>"

class ModuleContent(Base):
    __tablename__ = "module_content"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content_order = Column(Integer, nullable=False, default=0) # To order content within a module
    content_type = Column(SAEnum(ModuleContentType, name="module_content_type_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False)

    # Content specific fields
    content_url = Column(String(255), nullable=True) # For VIDEO, PDF
    text_content = Column(Text, nullable=True) # For TEXT type content
    # quiz_id is implicitly handled by the one-to-one relationship with Quiz model below

    estimated_completion_time_minutes = Column(Integer, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    module = relationship("CourseModule", back_populates="contents")
    # One-to-one relationship: A ModuleContent of type QUIZ will have one Quiz entry.
    quiz_association = relationship("Quiz", back_populates="content_association", uselist=False, cascade="all, delete-orphan")
    user_progress_entries = relationship("UserProgress", back_populates="content", cascade="all, delete-orphan")


    __table_args__ = (UniqueConstraint('module_id', 'content_order', name='uq_module_content_order'),)

    def __repr__(self):
        return f"<ModuleContent(id={self.id}, title='{self.title}', type='{self.content_type}')>"

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    # Link to ModuleContent: Each quiz is a specific type of ModuleContent
    module_content_id = Column(Integer, ForeignKey("module_content.id", ondelete="CASCADE"), unique=True, nullable=False)

    title = Column(String(255), nullable=False) # Quiz title (can be same as ModuleContent title)
    description = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    content_association = relationship("ModuleContent", back_populates="quiz_association")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan", order_by="Question.question_order")

    def __repr__(self):
        return f"<Quiz(id={self.id}, title='{self.title}', module_content_id={self.module_content_id})>"

class Question(Base):
    __tablename__ = "quiz_questions" # Changed from "questions" to avoid conflict if a generic "questions" table exists

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SAEnum(QuestionType, name="question_type_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    question_order = Column(Integer, nullable=False, default=0) # To order questions within a quiz
    explanation = Column(Text, nullable=True) # Explanation for the correct answer

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.id")

    __table_args__ = (UniqueConstraint('quiz_id', 'question_order', name='uq_quiz_question_order'),)

    def __repr__(self):
        return f"<Question(id={self.id}, quiz_id={self.quiz_id}, type='{self.question_type}')>"

class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    question = relationship("Question", back_populates="options")

    def __repr__(self):
        return f"<QuestionOption(id={self.id}, question_id={self.question_id}, correct={self.is_correct})>"

# Note on Enums:
# Using `values_callable=lambda obj: [e.value for e in obj]` makes the SAEnum use the string values from the Python enum.
# This is generally preferred for cross-database compatibility if not using native DB enum types.
# If using native DB enums (e.g., PostgreSQL CREATE TYPE), set `create_type=False` and manage the type with Alembic.
# For this project, we're letting SQLAlchemy define them, likely as VARCHARs, which is fine for many cases.
# The `name` attribute in SAEnum (e.g., "course_level_enum") is important if `create_type=True` is ever used,
# or if you plan to switch to native DB enums managed by Alembic. It defines the DB enum type name.
