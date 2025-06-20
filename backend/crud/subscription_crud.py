from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func # For count
from typing import List, Optional, Dict, Any # For filters
import logging
from datetime import datetime, timedelta # Added timedelta

from backend.models.subscription_model import SubscriptionPlan, UserSubscription
from backend.models.enums import SubscriptionStatus
from backend.schemas import subscription_schema as schemas # Alias for clarity

logger = logging.getLogger(__name__)


# Helper for applying filters to UserSubscription list queries
def _apply_user_subscription_filters(query, filters: Optional[Dict[str, Any]] = None):
    if not filters:
        return query
    if "user_id" in filters and filters["user_id"] is not None:
        query = query.filter(UserSubscription.user_id == filters["user_id"])
    if "plan_id" in filters and filters["plan_id"] is not None:
        query = query.filter(UserSubscription.plan_id == filters["plan_id"])
    if "status" in filters and filters["status"] is not None:
        # Ensure status is of type SubscriptionStatus if passed as string
        try:
            status_enum = SubscriptionStatus(filters["status"])
            query = query.filter(UserSubscription.status == status_enum)
        except ValueError:
            logger.warning(f"Invalid status value '{filters['status']}' for filtering UserSubscriptions. Ignoring status filter.")
    # Add more filters like date ranges, stripe_subscription_id etc. if needed
    return query

# --- SubscriptionPlan CRUD ---

def create_subscription_plan(db: Session, plan_in: schemas.SubscriptionPlanCreate) -> SubscriptionPlan:
    logger.info(f"Creating subscription plan: {plan_in.name}")
    db_plan = SubscriptionPlan(**plan_in.model_dump())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    logger.info(f"Subscription plan '{db_plan.name}' (ID: {db_plan.id}) created.")
    return db_plan

def get_subscription_plan(db: Session, plan_id: int) -> Optional[SubscriptionPlan]:
    logger.debug(f"Fetching subscription plan with ID: {plan_id}")
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

def get_subscription_plan_by_stripe_id(db: Session, stripe_price_id: str) -> Optional[SubscriptionPlan]:
    logger.debug(f"Fetching subscription plan by Stripe Price ID: {stripe_price_id}")
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.stripe_price_id == stripe_price_id).first()

def get_active_subscription_plans(db: Session, skip: int = 0, limit: int = 100) -> List[SubscriptionPlan]:
    logger.debug(f"Fetching active subscription plans with skip: {skip}, limit: {limit}")
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).offset(skip).limit(limit).all()

def update_subscription_plan(db: Session, plan_id: int, plan_in: schemas.SubscriptionPlanUpdate) -> Optional[SubscriptionPlan]:
    db_plan = get_subscription_plan(db, plan_id)
    if not db_plan:
        logger.warning(f"Subscription plan with ID {plan_id} not found for update.")
        return None

    update_data = plan_in.model_dump(exclude_unset=True)
    logger.debug(f"Updating plan ID {plan_id} with data: {update_data}")
    for field, value in update_data.items():
        setattr(db_plan, field, value)

    db.commit()
    db.refresh(db_plan)
    logger.info(f"Subscription plan '{db_plan.name}' (ID: {db_plan.id}) updated.")
    return db_plan

# --- UserSubscription CRUD ---

def create_user_subscription(
    db: Session,
    user_id: int,
    plan_id: int,
    status: SubscriptionStatus,
    start_date: Optional[datetime] = None, # Can be set by caller, e.g. from Stripe period start
    end_date: Optional[datetime] = None,   # Can be set by caller
    stripe_subscription_id: Optional[str] = None,
    current_period_start: Optional[datetime] = None,
    current_period_end: Optional[datetime] = None,
    cancel_at_period_end: bool = False
) -> UserSubscription:
    logger.info(f"Creating user subscription for user_id {user_id}, plan_id {plan_id}, status {status}")

    # Potentially deactivate other active subscriptions for the same user here,
    # or ensure this logic is handled by a service layer.
    # For now, this CRUD just creates the new record.

    db_user_subscription = UserSubscription(
        user_id=user_id,
        plan_id=plan_id,
        status=status,
        start_date=start_date if start_date else datetime.utcnow(),
        end_date=end_date, # Can be None for lifetime or Stripe-managed subs
        stripe_subscription_id=stripe_subscription_id,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end
    )
    db.add(db_user_subscription)
    db.commit()
    db.refresh(db_user_subscription)
    logger.info(f"UserSubscription (ID: {db_user_subscription.id}) created for user {user_id}.")
    return db_user_subscription

def get_user_subscription(db: Session, subscription_id: int) -> Optional[UserSubscription]:
    logger.debug(f"Fetching user subscription with ID: {subscription_id}")
    return db.query(UserSubscription).filter(UserSubscription.id == subscription_id).first()

def get_user_subscription_by_stripe_id(db: Session, stripe_subscription_id: str) -> Optional[UserSubscription]:
    logger.debug(f"Fetching user subscription by Stripe Subscription ID: {stripe_subscription_id}")
    return db.query(UserSubscription).filter(UserSubscription.stripe_subscription_id == stripe_subscription_id).first()

def get_active_user_subscription(db: Session, user_id: int) -> Optional[UserSubscription]:
    """Returns the current, genuinely active subscription for a user."""
    logger.debug(f"Fetching active subscription for user_id {user_id}")
    # This logic might need to be more sophisticated, e.g., checking end_date vs current time.
    # For Stripe, status 'active' and 'trialing' are good. 'past_due' might mean temporary issues.
    # 'canceled' could still mean active until period end if cancel_at_period_end is true.
    return db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status.in_([SubscriptionStatus.ACTIVE]) # Potentially add SubscriptionStatus.TRIALING if you use it
        # Add more precise filtering based on current_period_end if relying on Stripe for active status
        # UserSubscription.current_period_end > datetime.utcnow()
    ).order_by(UserSubscription.created_at.desc()).first() # Get the latest one if multiple somehow exist

def update_user_subscription_status(
    db: Session,
    subscription_id: int, # Our DB UserSubscription ID
    status: SubscriptionStatus,
    end_date: Optional[datetime] = None,
    current_period_start: Optional[datetime] = None,
    current_period_end: Optional[datetime] = None,
    cancel_at_period_end: Optional[bool] = None
) -> Optional[UserSubscription]:
    db_sub = get_user_subscription(db, subscription_id)
    if not db_sub:
        logger.warning(f"UserSubscription with ID {subscription_id} not found for status update.")
        return None

    logger.info(f"Updating UserSubscription ID {subscription_id} to status {status}. End date: {end_date}")
    db_sub.status = status
    if end_date is not None: # Explicitly passed, e.g. for cancellation or expiry
        db_sub.end_date = end_date
    if current_period_start is not None:
        db_sub.current_period_start = current_period_start
    if current_period_end is not None:
        db_sub.current_period_end = current_period_end
    if cancel_at_period_end is not None:
        db_sub.cancel_at_period_end = cancel_at_period_end
        if cancel_at_period_end and current_period_end: # If canceling at period end, set end_date for clarity
            db_sub.end_date = current_period_end

    db.commit()
    db.refresh(db_sub)
    logger.info(f"UserSubscription ID {subscription_id} status updated to {db_sub.status}.")
    return db_sub

def process_subscription_renewal( # Specific to Stripe, called from webhook handler
    db: Session,
    stripe_subscription_id: str,
    new_period_start: datetime,
    new_period_end: datetime
) -> Optional[UserSubscription]:
    db_sub = get_user_subscription_by_stripe_id(db, stripe_subscription_id)
    if not db_sub:
        logger.warning(f"UserSubscription with Stripe ID {stripe_subscription_id} not found for renewal processing.")
        return None

    logger.info(f"Processing renewal for Stripe subscription {stripe_subscription_id}. New period: {new_period_start} - {new_period_end}")
    db_sub.status = SubscriptionStatus.ACTIVE
    db_sub.current_period_start = new_period_start
    db_sub.current_period_end = new_period_end
    db_sub.start_date = new_period_start # Update start_date to reflect current billing period start
    db_sub.end_date = new_period_end # Update end_date to reflect current billing period end
    db_sub.cancel_at_period_end = False # Renewal implies it's not set to cancel at period end anymore

    db.commit()
    db.refresh(db_sub)
    logger.info(f"UserSubscription for Stripe ID {stripe_subscription_id} renewed. DB ID: {db_sub.id}")
    return db_sub

def cancel_user_subscription_locally( # Called from webhook or direct cancel endpoint
    db: Session,
    stripe_subscription_id: str, # Use Stripe ID as primary key for webhook actions
    cancel_at_period_end: bool,
    new_status: SubscriptionStatus, # e.g. CANCELED
    actual_end_date: Optional[datetime] = None # If known (e.g. period end for cancel_at_period_end, or now for immediate cancel)
):
    db_sub = get_user_subscription_by_stripe_id(db, stripe_subscription_id)
    if not db_sub:
        logger.warning(f"UserSubscription with Stripe ID {stripe_subscription_id} not found for cancellation.")
        return None

    logger.info(f"Canceling UserSubscription (DB ID: {db_sub.id}, Stripe ID: {stripe_subscription_id}). Status: {new_status}, Cancel at period end: {cancel_at_period_end}")
    db_sub.status = new_status
    db_sub.cancel_at_period_end = cancel_at_period_end
    if actual_end_date:
        db_sub.end_date = actual_end_date
    elif cancel_at_period_end and db_sub.current_period_end:
        db_sub.end_date = db_sub.current_period_end # Mark that it will end then

    db.commit()
    db.refresh(db_sub)
    logger.info(f"UserSubscription (DB ID: {db_sub.id}) marked as {new_status}.")
    return db_sub


# --- Admin UserSubscription Listing ---

def get_all_user_subscriptions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[UserSubscription]:
    """
    Admin: Retrieves a list of all user subscriptions with pagination and optional filtering.
    """
    logger.debug(f"Admin fetching all user subscriptions. Skip: {skip}, Limit: {limit}, Filters: {filters}")
    query = db.query(UserSubscription)
    query = _apply_user_subscription_filters(query, filters)
    return query.order_by(UserSubscription.id.desc()).offset(skip).limit(limit).all()

def count_all_user_subscriptions(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """
    Admin: Counts all user subscriptions with optional filtering.
    """
    logger.debug(f"Admin counting all user subscriptions. Filters: {filters}")
    query = db.query(func.count(UserSubscription.id))
    query = _apply_user_subscription_filters(query, filters)
    return query.scalar() or 0

def get_subscriptions_expiring_soon(db: Session, days_lookahead: int = 7) -> List[UserSubscription]:
    """
    Retrieves active user subscriptions that are set to expire within the given number of days.
    This checks the `end_date` field.
    """
    if days_lookahead < 0:
        raise ValueError("days_lookahead must be non-negative.")

    target_date_from = datetime.utcnow() # Subscriptions ending from now
    target_date_to = datetime.utcnow() + timedelta(days=days_lookahead)

    logger.debug(f"Fetching subscriptions expiring between {target_date_from.date()} and {target_date_to.date()}")

    query = db.query(UserSubscription).options(joinedload(UserSubscription.user), joinedload(UserSubscription.plan)).filter(
        UserSubscription.status == SubscriptionStatus.ACTIVE,
        UserSubscription.end_date.isnot(None), # Must have an end date
        UserSubscription.end_date >= target_date_from,
        UserSubscription.end_date <= target_date_to,
        UserSubscription.cancel_at_period_end == False # Only those not already set to cancel
    ).order_by(UserSubscription.end_date.asc())

    return query.all()
