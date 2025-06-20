from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from decimal import Decimal
import os # For commission rates from env

from backend.core.database import get_db
from backend.core.dependencies import get_current_active_user, get_current_admin_user
from backend.models.user_model import User
from backend.models.enums import ReferralCommissionStatus
from backend.schemas import referral_schema as schemas
from backend.crud import referral_crud as crud
from backend.crud import user_crud # For fetching user details if needed for downline display

logger = logging.getLogger(__name__) # Ensure logger is defined if not already
# Configure logger if it's not configured at a higher level, e.g. main.py
# logging.basicConfig(level=logging.INFO) # Example basic config

router = APIRouter(prefix="/referrals", tags=["Referrals & MLM"])

# --- User-Facing Referral Endpoints ---

@router.get("/me/info", response_model=schemas.MyReferralInfo)
def get_my_referral_information(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current authenticated user's referral code and a generated referral link.
    """
    if not current_user.referral_code:
        # This should ideally not happen if referral codes are generated on user creation.
        # Consider generating one here if missing, or raising an error.
        logger.error(f"User {current_user.email} (ID: {current_user.id}) is missing a referral code.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral code not found for user.")

    # Example base URL for referral links - should be configurable
    base_referral_url = os.getenv("APP_FRONTEND_URL", "http://localhost:3000")
    referral_link = f"{base_referral_url}/register?ref={current_user.referral_code}"

    return schemas.MyReferralInfo(
        referral_code=current_user.referral_code,
        referral_link=referral_link
    )

@router.get("/me/downline", response_model=List[schemas.DownlineUserNode])
def get_my_downline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    max_levels: int = Query(3, ge=1, le=3, description="Number of downline levels to fetch (1-3)")
):
    """
    Get the current user's downline, structured by level.
    Returns a flat list where each node indicates its level.
    """
    logger.info(f"Fetching downline for user {current_user.email} (ID: {current_user.id}) up to {max_levels} levels.")

    flat_downline_nodes: List[schemas.DownlineUserNode] = []
    downline_by_level: Dict[int, List[User]] = crud.get_downline_users_flat(db, current_user.id, max_levels)

    for level, users_at_level in downline_by_level.items():
        for user_node_db in users_at_level:
            upline_l1_email_val = None
            if user_node_db.upline_l1: # Check if upline_l1 (User object) is loaded
                upline_l1_email_val = user_node_db.upline_l1.email

            node_schema = schemas.DownlineUserNode(
                user_id=user_node_db.id,
                email=user_node_db.email,
                referral_code=user_node_db.referral_code,
                level=level, # Level relative to the requesting user
                upline_l1_email=upline_l1_email_val
            )
            flat_downline_nodes.append(node_schema)

    return flat_downline_nodes


@router.get("/me/earnings", response_model=List[schemas.ReferralEarningDisplay])
def get_my_referral_earnings(
    status: Optional[ReferralCommissionStatus] = Query(None, description="Filter earnings by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current authenticated user's referral earnings history.
    """
    logger.info(f"Fetching referral earnings for user {current_user.email} (ID: {current_user.id}), status: {status}")
    earnings_db = crud.get_referral_earnings_for_user(db, current_user.id, status=status, skip=skip, limit=limit)

    # Convert DB models to Pydantic display schemas
    earnings_display = []
    for earning in earnings_db:
        earning_user_simple = schemas.UserInReferralDisplay.model_validate(earning.earning_user) if earning.earning_user else None
        referred_user_simple = schemas.UserInReferralDisplay.model_validate(earning.referred_user_obj) if earning.referred_user_obj else None

        earnings_display.append(schemas.ReferralEarningDisplay(
            id=earning.id,
            user=earning_user_simple, # This is the current_user, effectively
            referred_user=referred_user_simple,
            source_payment_id=earning.source_payment_id,
            commission_amount=earning.commission_amount,
            commission_rate=earning.commission_rate,
            referral_level=earning.referral_level,
            status=earning.status,
            notes=earning.notes,
            created_at=earning.created_at,
            updated_at=earning.updated_at
        ))
    return earnings_display

@router.get("/me/stats", response_model=schemas.ReferralStats)
def get_my_referral_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get referral statistics for the current authenticated user.
    """
    logger.info(f"Fetching referral stats for user {current_user.email} (ID: {current_user.id})")
    stats = crud.get_referral_stats_for_user(db, current_user.id)
    return stats

# --- Admin Referral Management Endpoints ---

@router.get("/admin/earnings", response_model=List[schemas.ReferralEarningDisplay])
def admin_get_all_referral_earnings(
    status: Optional[ReferralCommissionStatus] = Query(None, description="Filter earnings by status"),
    user_id: Optional[int] = Query(None, description="Filter by earning user ID"),
    referred_user_id: Optional[int] = Query(None, description="Filter by referred user ID (source of commission)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get a list of all referral earnings, with optional filters.
    """
    logger.info(f"Admin {current_admin.email} fetching all referral earnings. Filters: Status={status}, UserID={user_id}, ReferredUID={referred_user_id}")
    earnings_db = crud.get_all_referral_earnings(db, status, user_id, referred_user_id, skip, limit)

    earnings_display = []
    for earning in earnings_db:
        earning_user_simple = schemas.UserInReferralDisplay.model_validate(earning.earning_user) if earning.earning_user else None
        referred_user_simple = schemas.UserInReferralDisplay.model_validate(earning.referred_user_obj) if earning.referred_user_obj else None
        earnings_display.append(schemas.ReferralEarningDisplay(
            id=earning.id,
            user=earning_user_simple,
            referred_user=referred_user_simple,
            source_payment_id=earning.source_payment_id,
            commission_amount=earning.commission_amount,
            commission_rate=earning.commission_rate,
            referral_level=earning.referral_level,
            status=earning.status,
            notes=earning.notes,
            created_at=earning.created_at,
            updated_at=earning.updated_at
        ))
    return earnings_display


@router.put("/admin/earnings/{earning_id}/status", response_model=schemas.ReferralEarningDisplay)
def admin_update_earning_status(
    earning_id: int,
    status_update: schemas.ReferralEarningUpdate, # Contains new status and optional notes
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Update the status (and notes) of a specific referral earning.
    """
    logger.info(f"Admin {current_admin.email} updating status for earning ID {earning_id} to {status_update.status}")
    if status_update.status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New status must be provided.")

    updated_earning = crud.update_referral_earning_status(db, earning_id, status_update.status, status_update.notes)
    if not updated_earning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Referral earning with ID {earning_id} not found.")

    earning_user_simple = schemas.UserInReferralDisplay.model_validate(updated_earning.earning_user) if updated_earning.earning_user else None
    referred_user_simple = schemas.UserInReferralDisplay.model_validate(updated_earning.referred_user_obj) if updated_earning.referred_user_obj else None

    return schemas.ReferralEarningDisplay(
        id=updated_earning.id,
        user=earning_user_simple,
        referred_user=referred_user_simple,
        source_payment_id=updated_earning.source_payment_id,
        commission_amount=updated_earning.commission_amount,
        commission_rate=updated_earning.commission_rate,
        referral_level=updated_earning.referral_level,
        status=updated_earning.status,
        notes=updated_earning.notes,
        created_at=updated_earning.created_at,
        updated_at=updated_earning.updated_at
    )
