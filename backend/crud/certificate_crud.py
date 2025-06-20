from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from backend.models.certificate_model import Certificate, generate_verification_code
from backend.models.user_model import User # For type hinting
from backend.models.course_model import Course # For type hinting
# from backend.schemas import certificate_schema as schemas # Not strictly needed for create if params are explicit

logger = logging.getLogger(__name__)

def create_certificate(db: Session, user_id: int, course_id: int) -> Optional[Certificate]:
    """
    Creates a certificate entry for a user upon course completion.
    Generates a unique verification code.
    Actual PDF URL generation is handled separately.
    """
    logger.debug(f"Attempting to create certificate for user_id {user_id}, course_id {course_id}")

    # Check if certificate already exists
    existing_certificate = db.query(Certificate).filter(
        Certificate.user_id == user_id,
        Certificate.course_id == course_id
    ).first()

    if existing_certificate:
        logger.warning(f"Certificate already exists for user_id {user_id}, course_id {course_id} (ID: {existing_certificate.id}).")
        return existing_certificate # Or raise an error, depending on desired behavior

    # Potentially, check if the user is eligible for a certificate (e.g., course completed)
    # This logic might reside in a service layer or the calling route handler.
    # For now, this CRUD function assumes eligibility check is done prior to calling.

    new_certificate = Certificate(
        user_id=user_id,
        course_id=course_id,
        verification_code=generate_verification_code(), # Ensure this function is robustly unique
        issued_at=datetime.utcnow() # Set issue time
        # certificate_url will be updated later
    )

    try:
        db.add(new_certificate)
        db.commit()
        db.refresh(new_certificate)
        logger.info(f"Certificate created successfully for user_id {user_id}, course_id {course_id} (ID: {new_certificate.id}, Code: {new_certificate.verification_code}).")
        return new_certificate
    except Exception as e: # Catch potential IntegrityError for verification_code if not unique despite UUID
        db.rollback()
        logger.error(f"Error creating certificate for user_id {user_id}, course_id {course_id}: {e}", exc_info=True)
        # Handle cases like non-existent user_id or course_id if FK constraints are deferred or not immediate.
        raise

def get_certificate_by_id(db: Session, certificate_id: int) -> Optional[Certificate]:
    """Fetches a certificate by its primary ID."""
    logger.debug(f"Fetching certificate by ID: {certificate_id}")
    return db.query(Certificate).filter(Certificate.id == certificate_id).first()

def get_certificate_by_verification_code(db: Session, verification_code: str) -> Optional[Certificate]:
    """Fetches a certificate by its unique verification code."""
    logger.debug(f"Fetching certificate by verification code: {verification_code}")
    return db.query(Certificate).filter(Certificate.verification_code == verification_code).first()

def get_certificates_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 10) -> List[Certificate]:
    """Fetches all certificates issued to a specific user."""
    logger.debug(f"Fetching certificates for user_id {user_id} with skip: {skip}, limit: {limit}")
    return db.query(Certificate).filter(Certificate.user_id == user_id).order_by(Certificate.issued_at.desc()).offset(skip).limit(limit).all()

def get_certificates_for_course(db: Session, course_id: int, skip: int = 0, limit: int = 100) -> List[Certificate]:
    """Fetches all certificates issued for a specific course."""
    logger.debug(f"Fetching certificates for course_id {course_id} with skip: {skip}, limit: {limit}")
    return db.query(Certificate).filter(Certificate.course_id == course_id).order_by(Certificate.issued_at.desc()).offset(skip).limit(limit).all()

def update_certificate_url(db: Session, certificate_id: int, certificate_url: str) -> Optional[Certificate]:
    """Updates the certificate_url for a given certificate ID."""
    logger.debug(f"Updating certificate_url for certificate ID: {certificate_id}")
    certificate = get_certificate_by_id(db, certificate_id)
    if not certificate:
        logger.warning(f"Certificate with ID {certificate_id} not found for URL update.")
        return None

    certificate.certificate_url = certificate_url
    try:
        db.commit()
        db.refresh(certificate)
        logger.info(f"Certificate URL for ID {certificate_id} updated to: {certificate_url}")
        return certificate
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating certificate URL for ID {certificate_id}: {e}", exc_info=True)
        raise
