from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Assuming UserDisplay and CourseDisplay might be useful context
from .user_schema import UserDisplay # Assuming UserDisplay doesn't cause circular import here
from .course_schema import CourseDisplay # Assuming CourseDisplay doesn't cause circular import here
# If circular imports are an issue, use ForwardRef as done in course_schema.py

class CertificateBase(BaseModel):
    pass # Base might be empty if all fields are identifiers or auto-generated initially

class CertificateCreate(CertificateBase):
    # user_id and course_id will typically be derived from context (e.g., authenticated user, course path param)
    # and not part of the direct request body for issuing a certificate to oneself.
    # If an admin were creating this, they might specify these.
    # For this schema, let's assume it's for internal use or specific admin endpoints.
    user_id: int
    course_id: int
    # certificate_url and verification_code are usually generated by the backend.

class CertificateDisplay(CertificateBase):
    id: int
    user_id: int
    course_id: int
    certificate_url: Optional[str] = Field(None, description="URL to the generated certificate PDF")
    issued_at: datetime
    verification_code: str = Field(..., description="Unique code to verify the certificate")

    user: Optional[UserDisplay] = Field(None, description="Details of the user who earned the certificate")
    course: Optional[CourseDisplay] = Field(None, description="Details of the course for which the certificate was issued")

    class Config:
        from_attributes = True
