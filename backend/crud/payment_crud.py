from sqlalchemy.orm import Session
from sqlalchemy import func # For count
from typing import List, Optional, Dict, Any # For filters
import logging
from datetime import datetime

from backend.models.payment_model import Payment
from backend.models.enums import PaymentStatus, PaymentGateway
from backend.schemas import payment_schema as schemas # Alias for clarity

logger = logging.getLogger(__name__)


# Helper for applying filters to Payment list queries
def _apply_payment_filters(query, filters: Optional[Dict[str, Any]] = None):
    if not filters:
        return query
    if "user_id" in filters and filters["user_id"] is not None:
        query = query.filter(Payment.user_id == filters["user_id"])
    if "status" in filters and filters["status"] is not None:
        try:
            status_enum = PaymentStatus(filters["status"])
            query = query.filter(Payment.status == status_enum)
        except ValueError:
            logger.warning(f"Invalid status value '{filters['status']}' for filtering Payments. Ignoring status filter.")
    if "payment_gateway" in filters and filters["payment_gateway"] is not None:
        try:
            gateway_enum = PaymentGateway(filters["payment_gateway"])
            query = query.filter(Payment.payment_gateway == gateway_enum)
        except ValueError:
            logger.warning(f"Invalid gateway value '{filters['payment_gateway']}' for filtering Payments. Ignoring gateway filter.")
    # Add more filters like date ranges, amount ranges etc. if needed
    return query

def create_payment_record(db: Session, payment_in: schemas.PaymentCreate) -> Payment:
    """
    Creates a new payment record in the database.
    Initial status is usually PENDING, updated by webhook or polling.
    """
    logger.info(f"Creating payment record for user_id {payment_in.user_id}, amount {payment_in.amount} {payment_in.currency}")

    # Ensure required fields for a base payment record are present
    db_payment = Payment(
        user_id=payment_in.user_id,
        user_subscription_id=payment_in.user_subscription_id,
        amount=payment_in.amount,
        currency=payment_in.currency,
        status=payment_in.status if payment_in.status else PaymentStatus.PENDING, # Default to PENDING
        payment_gateway=payment_in.payment_gateway,
        transaction_id=payment_in.transaction_id, # May be null initially
        payment_intent_id=payment_in.payment_intent_id, # May be null initially
        paid_at=payment_in.paid_at # May be null initially
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    logger.info(f"Payment record (ID: {db_payment.id}) created for user {payment_in.user_id}.")
    return db_payment

def get_payment_by_id(db: Session, payment_id: int) -> Optional[Payment]:
    logger.debug(f"Fetching payment by ID: {payment_id}")
    return db.query(Payment).filter(Payment.id == payment_id).first()

def get_payment_by_transaction_id(db: Session, transaction_id: str, gateway: Optional[PaymentGateway] = None) -> Optional[Payment]:
    """Fetches a payment by its gateway transaction ID."""
    logger.debug(f"Fetching payment by transaction_id: {transaction_id} (Gateway: {gateway or 'any'})")
    query = db.query(Payment).filter(Payment.transaction_id == transaction_id)
    if gateway:
        query = query.filter(Payment.payment_gateway == gateway)
    return query.first()

def get_payment_by_payment_intent_id(db: Session, payment_intent_id: str) -> Optional[Payment]:
    """Fetches a payment by its Stripe PaymentIntent ID."""
    logger.debug(f"Fetching payment by payment_intent_id: {payment_intent_id}")
    return db.query(Payment).filter(Payment.payment_intent_id == payment_intent_id).first()


def get_payments_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> List[Payment]:
    """Fetches all payment records for a specific user, most recent first."""
    logger.debug(f"Fetching payments for user_id {user_id} with skip: {skip}, limit: {limit}")
    return db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

def get_payments_for_subscription(db: Session, user_subscription_id: int, skip: int = 0, limit: int = 100) -> List[Payment]:
    """Fetches all payment records for a specific user subscription."""
    logger.debug(f"Fetching payments for user_subscription_id {user_subscription_id} with skip: {skip}, limit: {limit}")
    return db.query(Payment).filter(Payment.user_subscription_id == user_subscription_id).order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()


def update_payment_status(
    db: Session,
    payment_id_internal: Optional[int] = None, # Our DB Payment ID
    payment_intent_id_stripe: Optional[str] = None, # Stripe's PI ID
    transaction_id_gateway: Optional[str] = None, # Gateway's TXN ID
    new_status: PaymentStatus,
    paid_at: Optional[datetime] = None, # Should be set when status is SUCCEEDED
    invoice_url: Optional[str] = None,
    receipt_url: Optional[str] = None,
    error_message: Optional[str] = None,
    # If creating payment record based on webhook data and it doesn't exist yet:
    create_if_not_exists: bool = False,
    payment_data_for_create: Optional[schemas.PaymentCreate] = None
) -> Optional[Payment]:
    """
    Updates a payment record's status and related information.
    Can find the payment by internal ID, Stripe PaymentIntent ID, or other gateway transaction ID.
    If `create_if_not_exists` is True, it will create a payment record if one isn't found,
    using `payment_data_for_create`.
    """
    logger.info(f"Updating payment status. InternalID: {payment_id_internal}, StripePI_ID: {payment_intent_id_stripe}, GatewayTXN_ID: {transaction_id_gateway}. New Status: {new_status}")

    db_payment: Optional[Payment] = None
    if payment_id_internal:
        db_payment = get_payment_by_id(db, payment_id_internal)
    elif payment_intent_id_stripe:
        db_payment = get_payment_by_payment_intent_id(db, payment_intent_id_stripe)
    elif transaction_id_gateway: # This might need gateway context if IDs are not globally unique
        db_payment = get_payment_by_transaction_id(db, transaction_id_gateway)

    if not db_payment:
        if create_if_not_exists and payment_data_for_create:
            logger.warning(f"Payment record not found. Attempting to create based on webhook data.")
            # Ensure the provided data for creation also includes the new status and other relevant fields
            payment_data_for_create.status = new_status
            payment_data_for_create.paid_at = paid_at if new_status == PaymentStatus.SUCCEEDED else None
            payment_data_for_create.invoice_url = invoice_url
            payment_data_for_create.receipt_url = receipt_url
            payment_data_for_create.error_message = error_message
            # Ensure key identifiers used for lookup are also in payment_data_for_create
            if payment_intent_id_stripe: payment_data_for_create.payment_intent_id = payment_intent_id_stripe
            if transaction_id_gateway: payment_data_for_create.transaction_id = transaction_id_gateway

            db_payment = create_payment_record(db, payment_data_for_create)
            logger.info(f"Payment record created (ID: {db_payment.id}) from webhook/update data.")
            return db_payment
        else:
            logger.error(f"Payment record not found for update and not creating new one. Identifiers: InternalID {payment_id_internal}, StripePI_ID {payment_intent_id_stripe}, GatewayTXN_ID {transaction_id_gateway}")
            return None

    logger.debug(f"Found payment record (ID: {db_payment.id}). Updating status to {new_status}.")
    db_payment.status = new_status
    if paid_at is not None and new_status == PaymentStatus.SUCCEEDED:
        db_payment.paid_at = paid_at
    if invoice_url is not None:
        db_payment.invoice_url = invoice_url
    if receipt_url is not None:
        db_payment.receipt_url = receipt_url
    if error_message is not None:
        db_payment.error_message = error_message

    # If a transaction_id or payment_intent_id is being newly provided (e.g. from gateway after creation)
    if transaction_id_gateway and not db_payment.transaction_id:
        db_payment.transaction_id = transaction_id_gateway
    if payment_intent_id_stripe and not db_payment.payment_intent_id:
        db_payment.payment_intent_id = payment_intent_id_stripe

    try:
        db.commit()
        db.refresh(db_payment)
        logger.info(f"Payment record (ID: {db_payment.id}) status updated to {db_payment.status}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating payment status for payment ID {db_payment.id}: {e}", exc_info=True)
        raise

    return db_payment


# --- Admin Payment Listing ---

def get_all_payments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[Payment]:
    """
    Admin: Retrieves a list of all payments with pagination and optional filtering.
    """
    logger.debug(f"Admin fetching all payments. Skip: {skip}, Limit: {limit}, Filters: {filters}")
    query = db.query(Payment)
    query = _apply_payment_filters(query, filters)
    return query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

def count_all_payments(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """
    Admin: Counts all payments with optional filtering.
    """
    logger.debug(f"Admin counting all payments. Filters: {filters}")
    query = db.query(func.count(Payment.id))
    query = _apply_payment_filters(query, filters)
    return query.scalar() or 0
