from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid # For generating verification codes

from backend.core.database import Base

def generate_verification_code():
    """Generates a unique verification code for certificates."""
    return str(uuid.uuid4())

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    certificate_url = Column(String(255), nullable=True) # To be filled when PDF is generated
    issued_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    verification_code = Column(String(36), unique=True, nullable=False, default=generate_verification_code, index=True)

    # Relationships
    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="issued_certificates") # Changed from "certificates"

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='uq_user_course_certificate'), # User gets one certificate per course
    )

    def __repr__(self):
        return f"<Certificate(id={self.id}, user_id={self.user_id}, course_id={self.course_id}, code='{self.verification_code}')>"
