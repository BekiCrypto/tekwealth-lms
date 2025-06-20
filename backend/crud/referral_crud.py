from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import List, Optional, Dict
from decimal import Decimal
import logging

from backend.models.user_model import User
from backend.models.referral_model import ReferralEarning
from backend.models.enums import ReferralCommissionStatus
from backend.schemas import referral_schema as schemas
from backend.services import email_service # Added for sending commission emails
from backend.crud import user_crud # To get user details for email context

logger = logging.getLogger(__name__)

# --- ReferralEarning CRUD ---

def create_referral_earning(db: Session, earning_in: schemas.ReferralEarningCreate) -> ReferralEarning:
    logger.info(f"Creating referral earning for user_id {earning_in.user_id} from referred_user_id {earning_in.referred_user_id}")
    db_earning = ReferralEarning(**earning_in.model_dump())
    db.add(db_earning)
    db.commit()
    db.refresh(db_earning) # To get ID, created_at etc.
    logger.info(f"ReferralEarning (ID: {db_earning.id}) created for user {earning_in.user_id}.")

    # Send email notification to the user who earned the commission
    try:
        earning_user = user_crud.get_user_by_id(db, db_earning.user_id)
        referred_user = user_crud.get_user_by_id(db, db_earning.referred_user_id) if db_earning.referred_user_id else None

        if earning_user:
            email_context = {
                "user_name": earning_user.email, # Or a display name
                "commission_amount": f"{db_earning.commission_amount:.2f}", # Format as currency string
                "referred_user_name": referred_user.email if referred_user else "a referred user",
                "level": db_earning.referral_level,
            }
            email_service.send_templated_email(
                to_email=earning_user.email,
                subject="You've Earned a Referral Commission!",
                html_template_name="referral_commission_earned.html",
                context=email_context
            )
            logger.info(f"Referral commission earned email queued for user {earning_user.email} (Earning ID: {db_earning.id})")
        else:
            logger.warning(f"Earning user ID {db_earning.user_id} not found for sending commission email (Earning ID: {db_earning.id}).")
    except Exception as email_exc:
        logger.error(f"Failed to send referral commission email for earning ID {db_earning.id}: {email_exc}", exc_info=True)
        # Do not let email failure roll back the earning creation or fail the request.

    return db_earning

def get_referral_earning_by_id(db: Session, earning_id: int) -> Optional[ReferralEarning]:
    logger.debug(f"Fetching referral earning by ID: {earning_id}")
    return db.query(ReferralEarning).filter(ReferralEarning.id == earning_id).first()

def get_referral_earnings_for_user(
    db: Session,
    user_id: int,
    status: Optional[ReferralCommissionStatus] = None,
    skip: int = 0,
    limit: int = 20
) -> List[ReferralEarning]:
    logger.debug(f"Fetching referral earnings for user_id {user_id}, status {status}, skip {skip}, limit {limit}")
    query = db.query(ReferralEarning).filter(ReferralEarning.user_id == user_id)
    if status:
        query = query.filter(ReferralEarning.status == status)
    return query.order_by(ReferralEarning.created_at.desc()).offset(skip).limit(limit).all()

def get_all_referral_earnings( # For Admin
    db: Session,
    status: Optional[ReferralCommissionStatus] = None,
    user_id: Optional[int] = None, # Filter by earning user
    referred_user_id: Optional[int] = None, # Filter by source user
    skip: int = 0,
    limit: int = 100
) -> List[ReferralEarning]:
    logger.debug(f"Admin fetching all referral earnings. Status: {status}, UserID: {user_id}, ReferredUID: {referred_user_id}")
    query = db.query(ReferralEarning)
    if status:
        query = query.filter(ReferralEarning.status == status)
    if user_id:
        query = query.filter(ReferralEarning.user_id == user_id)
    if referred_user_id:
        query = query.filter(ReferralEarning.referred_user_id == referred_user_id)
    return query.order_by(ReferralEarning.created_at.desc()).offset(skip).limit(limit).all()


def update_referral_earning_status(
    db: Session,
    earning_id: int,
    new_status: ReferralCommissionStatus,
    notes: Optional[str] = None
) -> Optional[ReferralEarning]:
    db_earning = get_referral_earning_by_id(db, earning_id)
    if not db_earning:
        logger.warning(f"ReferralEarning with ID {earning_id} not found for status update.")
        return None

    logger.info(f"Updating ReferralEarning ID {earning_id} to status {new_status}.")
    db_earning.status = new_status
    if notes is not None: # Allow clearing notes by passing empty string, or explicit None to not change
        db_earning.notes = notes

    db.commit()
    db.refresh(db_earning)
    logger.info(f"ReferralEarning ID {earning_id} status updated to {db_earning.status}.")
    return db_earning

# --- Downline & Stats Logic ---

def get_downline_users_flat(db: Session, user_id: int, max_levels: int = 3) -> Dict[int, List[User]]:
    """
    Fetches downline users up to max_levels in a flat list per level.
    Level 1: Directly referred by user_id.
    Level 2: Referred by Level 1 users.
    Level 3: Referred by Level 2 users.
    Returns a dictionary where keys are levels (1, 2, 3) and values are lists of User objects.
    """
    logger.debug(f"Fetching flat downline for user_id {user_id} up to {max_levels} levels.")
    downline_by_level: Dict[int, List[User]] = {level: [] for level in range(1, max_levels + 1)}

    # Level 1: Directly referred by the user (where upline_l1_id is user_id)
    level1_users = db.query(User).filter(User.upline_l1_id == user_id).all()
    if not level1_users:
        return downline_by_level
    downline_by_level[1] = level1_users

    if max_levels >= 2:
        level1_ids = [u.id for u in level1_users]
        if level1_ids:
            level2_users = db.query(User).filter(User.upline_l1_id.in_(level1_ids)).all()
            if not level2_users:
                return downline_by_level
            downline_by_level[2] = level2_users

            if max_levels >= 3:
                level2_ids = [u.id for u in level2_users]
                if level2_ids:
                    level3_users = db.query(User).filter(User.upline_l1_id.in_(level2_ids)).all()
                    downline_by_level[3] = level3_users

    return downline_by_level


def get_referral_stats_for_user(db: Session, user_id: int) -> schemas.ReferralStats:
    logger.debug(f"Calculating referral stats for user_id {user_id}")

    stats = schemas.ReferralStats()

    # Direct (L1) referrals
    stats.total_direct_referrals = db.query(func.count(User.id)).filter(User.upline_l1_id == user_id).scalar() or 0
    stats.total_l1_referrals = stats.total_direct_referrals # Alias

    # L2 referrals
    level1_ids = db.query(User.id).filter(User.upline_l1_id == user_id).subquery()
    stats.total_l2_referrals = db.query(func.count(User.id)).filter(User.upline_l1_id.in_(level1_ids)).scalar() or 0

    # L3 referrals
    level2_ids = db.query(User.id).filter(User.upline_l1_id.in_(level1_ids)).subquery()
    stats.total_l3_referrals = db.query(func.count(User.id)).filter(User.upline_l1_id.in_(level2_ids)).scalar() or 0

    # Commission stats
    pending_sum = db.query(func.sum(ReferralEarning.commission_amount)).filter(
        ReferralEarning.user_id == user_id,
        ReferralEarning.status == ReferralCommissionStatus.PENDING
    ).scalar() or Decimal("0.00")
    stats.pending_commission_total = pending_sum

    approved_sum = db.query(func.sum(ReferralEarning.commission_amount)).filter(
        ReferralEarning.user_id == user_id,
        ReferralEarning.status == ReferralCommissionStatus.APPROVED
    ).scalar() or Decimal("0.00")
    stats.approved_commission_total = approved_sum

    paid_sum = db.query(func.sum(ReferralEarning.commission_amount)).filter(
        ReferralEarning.user_id == user_id,
        ReferralEarning.status == ReferralCommissionStatus.PAID
    ).scalar() or Decimal("0.00")
    stats.paid_commission_total = paid_sum

    stats.lifetime_commission_total = pending_sum + approved_sum + paid_sum

    return stats
