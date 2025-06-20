from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
import logging

from backend.core.database import get_db
from backend.core.dependencies import get_current_admin_user, get_user_or_404 # For fetching user by ID
from backend.models.user_model import User
from backend.schemas import user_schema as schemas # User schemas including AdminUserUpdate, UserDetailAdminDisplay
from backend.schemas import ( # For UserDetailAdminDisplay composition
    subscription_schema as sub_schemas,
    payment_schema as pay_schemas,
    referral_schema as ref_schemas,
    user_progress_schema as up_schemas,
    course_schema as course_schemas
)
from backend.crud import (
    user_crud as crud, # Renamed to user_crud_for_admin_clarity if there was a name clash
    subscription_crud as sub_crud,
    payment_crud as pay_crud,
    referral_crud as ref_crud,
    user_progress_crud as up_crud,
    course_crud, # For fetching course titles for progress summary
    analytics_crud # Added for analytics endpoints
)
from backend.schemas import admin_schema # For analytics response models
from backend.services import email_service # For sending emails
from datetime import date, datetime # For date query parameters in revenue report
from pydantic import BaseModel # For paginated responses
from backend.core.config import settings # For APP_NAME


logger = logging.getLogger(__name__)
# This router will handle general admin functionalities, starting with user management.
# It can be expanded or can include other admin-specific routers.
router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# --- User Management by Admin ---

class PaginatedUsersAdmin(BaseModel): # Pydantic model for paginated response
    total: int
    users: List[schemas.UserDisplay] # Using UserDisplay, can switch to UserDetailAdminDisplay if needed for list view
    page: int
    size: int

@router.get("/users", response_model=PaginatedUsersAdmin)
def admin_list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    skip: int = Query(0, ge=0, alias="page_offset"), # page_offset for clarity, maps to skip
    limit: int = Query(20, ge=1, le=200, alias="page_size"), # page_size for clarity, maps to limit
    # Filtering query parameters
    email_contains: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    referral_code: Optional[str] = Query(None)
):
    """
    Admin: Get a list of all users with pagination and optional filters.
    """
    logger.info(f"Admin {current_admin.email} listing users. Skip: {skip}, Limit: {limit}")

    filters = {
        "email_contains": email_contains,
        "role": role,
        "referral_code": referral_code
    }
    # Remove None filters to pass only active ones
    active_filters = {k: v for k, v in filters.items() if v is not None}

    total_users = crud.count_users(db, filters=active_filters)
    users_db = crud.get_users(db, skip=skip, limit=limit, filters=active_filters)

    # Convert to UserDisplay. If UserDetailAdminDisplay is too heavy for list, keep UserDisplay.
    # users_display = [schemas.UserDisplay.model_validate(user) for user in users_db] # Pydantic v2
    users_display = [schemas.UserDisplay.from_orm(user) for user in users_db] # Pydantic v1

    return PaginatedUsersAdmin(
        total=total_users,
        users=users_display,
        page=(skip // limit) + 1 if limit > 0 else 1, # Calculate page number
        size=limit
    )

@router.get("/users/{user_id}", response_model=schemas.UserDetailAdminDisplay)
def admin_get_user_details(
    user_id: int, # Path parameter
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get detailed information for a specific user.
    """
    logger.info(f"Admin {current_admin.email} fetching details for user ID: {user_id}")
    db_user = get_user_or_404(user_id, db) # Uses dependency to fetch or 404

    # --- Compose UserDetailAdminDisplay ---
    # 1. Core UserDisplay part (already part of UserDetailAdminDisplay inheritance)
    user_display_data = schemas.UserDisplay.from_orm(db_user).model_dump()

    # 2. Active Subscription
    active_sub_db = sub_crud.get_active_user_subscription(db, user_id=db_user.id)
    active_sub_display = sub_schemas.UserSubscriptionDisplay.from_orm(active_sub_db) if active_sub_db else None

    # 3. Payment History Summary (e.g., last 5 payments)
    payments_db = pay_crud.get_payments_for_user(db, user_id=db_user.id, limit=5)
    payments_display = [pay_schemas.PaymentDisplay.from_orm(p) for p in payments_db] if payments_db else []

    # 4. Referral Stats
    ref_stats_data = ref_crud.get_referral_stats_for_user(db, user_id=db_user.id)

    # 5. Course Progress Summary
    user_progress_entries = up_crud.get_user_progress_for_course(db, user_id=db_user.id, course_id=None) # Get all course progresses

    # Create a map of course_id to its progress entries
    course_progress_map = {}
    for up_entry in user_progress_entries:
        if up_entry.course_id not in course_progress_map:
            # Fetch course title - this could be optimized by fetching all relevant courses once
            course_obj = course_crud.get_course(db, up_entry.course_id)
            course_title = course_obj.title if course_obj else "Unknown Course"
            course_progress_map[up_entry.course_id] = {
                "course_id": up_entry.course_id,
                "course_title": course_title,
                "completed_content_ids": set(), # To track unique completed content
                "total_content_items": 0 # Will need to get this from course structure
            }
        if up_entry.completed_at:
            course_progress_map[up_entry.course_id]["completed_content_ids"].add(up_entry.content_id)

    course_progress_summary_list = []
    for course_id_key, data in course_progress_map.items():
        # This is a simplified completion calc. Real one is in up_crud.get_course_completion_percentage
        # For admin panel, maybe just list courses they started. Deeper stats per course can be another endpoint.
        # Using the existing CRUD for accurate percentage:
        completion_perc = up_crud.get_course_completion_percentage(db, user_id=db_user.id, course_id=course_id_key)
        course_progress_summary_list.append(schemas.UserCourseProgressSummary(
            course_id=data["course_id"],
            course_title=data["course_title"],
            completion_percentage=completion_perc
        ))

    # Construct the final response model
    # Pydantic v2: schemas.UserDetailAdminDisplay.model_validate(db_user) and then add extras
    # Pydantic v1: from_orm then add extras, or pass all as dict.
    # For composed schemas, it's often easier to build the dict.

    detailed_user_data = {
        **user_display_data, # Spread the UserDisplay fields
        "active_subscription": active_sub_display,
        "payment_history_summary": payments_display,
        "referral_stats": ref_stats_data,
        "course_progress_summary": course_progress_summary_list,
    }

    return schemas.UserDetailAdminDisplay(**detailed_user_data)


@router.put("/users/{user_id}", response_model=schemas.UserDisplay) # Return basic UserDisplay after update
def admin_update_user(
    user_id: int, # Path parameter
    user_update_in: schemas.AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Update a user's details (e.g., role, email).
    """
    logger.info(f"Admin {current_admin.email} updating user ID: {user_id} with data: {user_update_in.model_dump(exclude_unset=True)}")

    try:
        updated_user = crud.update_user_by_admin(db, user_id, user_update_in)
    except IntegrityError as e: # Catch specific errors like duplicate email
        logger.warning(f"Integrity error during admin update of user {user_id}: {e.detail if hasattr(e, 'detail') else str(e)}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Update failed: {e.detail if hasattr(e, 'detail') else str(e)}")

    if not updated_user:
        # This might be redundant if get_user_by_id inside update_user_by_admin raises 404,
        # but good as a safeguard if it returns None for other reasons.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or update failed.")

    return schemas.UserDisplay.from_orm(updated_user) # Pydantic v1
    # return schemas.UserDisplay.model_validate(updated_user) # Pydantic v2

# Placeholder for activate/deactivate if `is_active` field is added to User model
# @router.put("/users/{user_id}/activate", response_model=schemas.UserDisplay)
# ...
# @router.put("/users/{user_id}/deactivate", response_model=schemas.UserDisplay)
# ...

# This admin router can be expanded with more user management features or include other admin routers.
# For example:
# from .admin_course_routes import router as admin_course_router # If you create this
# router.include_router(admin_course_router, prefix="/courses", tags=["Admin - Courses"])


# --- Platform Analytics Endpoints ---

@router.get("/platform-stats/overview", response_model=admin_schema.PlatformStatsOverview)
def admin_get_platform_stats_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get an overview of platform statistics.
    """
    logger.info(f"Admin {current_admin.email} requesting platform stats overview.")
    stats = analytics_crud.get_platform_stats_overview(db)
    return stats

@router.get("/analytics/courses", response_model=List[admin_schema.CourseAnalyticsInfo])
def admin_get_courses_analytics(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get analytics for all courses (enrollments, completion rates, certificates).
    """
    logger.info(f"Admin {current_admin.email} requesting courses analytics.")
    course_analytics = analytics_crud.get_courses_analytics(db)
    return course_analytics

@router.get("/analytics/revenue-report", response_model=admin_schema.RevenueReport)
def admin_get_revenue_report(
    start_date: date = Query(..., description="Start date for the report (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for the report (YYYY-MM-DD)"),
    interval: str = Query("daily", enum=["daily", "monthly", "yearly"], description="Interval for revenue aggregation"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get a revenue report over a specified time period and interval.
    """
    logger.info(f"Admin {current_admin.email} requesting revenue report from {start_date} to {end_date} with interval {interval}.")
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date cannot be after end date.")

    report = analytics_crud.get_revenue_over_time(db, start_date=start_date, end_date=end_date, interval=interval)
    return report


# --- Admin Management of Subscriptions & Payments ---
# (Adding these here as requested, could also be in subscription_routes.py if not admin-specific)

class PaginatedAdminUserSubscriptions(BaseModel):
    total: int
    subscriptions: List[sub_schemas.UserSubscriptionDisplay]
    page: int
    size: int

@router.get("/subscriptions", response_model=PaginatedAdminUserSubscriptions)
def admin_list_all_user_subscriptions(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    skip: int = Query(0, ge=0, alias="page_offset"),
    limit: int = Query(20, ge=1, le=200, alias="page_size"),
    user_id: Optional[int] = Query(None, description="Filter by User ID"),
    plan_id: Optional[int] = Query(None, description="Filter by Plan ID"),
    status: Optional[str] = Query(None, description="Filter by Subscription Status") # Consider using Enum here
):
    """
    Admin: List all user subscriptions with filters and pagination.
    """
    logger.info(f"Admin {current_admin.email} listing all subscriptions.")
    filters = {"user_id": user_id, "plan_id": plan_id, "status": status}
    active_filters = {k: v for k, v in filters.items() if v is not None}

    # These CRUD functions (get_all_user_subscriptions, count_all_user_subscriptions) need to be created in subscription_crud.py
    total_subs = sub_crud.count_all_user_subscriptions(db, filters=active_filters)
    subs_db = sub_crud.get_all_user_subscriptions(db, skip=skip, limit=limit, filters=active_filters)

    return PaginatedAdminUserSubscriptions(
        total=total_subs,
        subscriptions=[sub_schemas.UserSubscriptionDisplay.from_orm(s) for s in subs_db],
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit
    )


# --- Admin Action: Trigger Subscription Expiry Reminder Emails ---
@router.post("/notifications/trigger-expiry-reminders", status_code=status.HTTP_202_ACCEPTED)
def admin_trigger_subscription_expiry_reminders(
    days_lookahead: int = Query(7, ge=1, le=30, description="Number of days in advance to look for expiring subscriptions"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Manually trigger sending "Subscription Expiring Soon" emails.
    This is a placeholder for a scheduled task.
    """
    logger.info(f"Admin {current_admin.email} triggering subscription expiry reminders for next {days_lookahead} days.")

    expiring_subs = sub_crud.get_subscriptions_expiring_soon(db, days_lookahead=days_lookahead)

    if not expiring_subs:
        return {"message": "No subscriptions found expiring in the specified timeframe."}

    email_send_count = 0
    email_fail_count = 0

    for sub in expiring_subs:
        if sub.user and sub.plan and sub.end_date: # Ensure necessary data is present
            try:
                email_context = {
                    "user_name": sub.user.email, # Or a display name
                    "plan_name": sub.plan.name,
                    "expiry_date": sub.end_date.strftime("%Y-%m-%d %H:%M:%S UTC") # Format date for email
                }
                success = email_service.send_templated_email(
                    to_email=sub.user.email,
                    subject=f"Your {settings.PROJECT_NAME} Subscription is Expiring Soon!",
                    html_template_name="subscription_expiring_soon.html",
                    context=email_context
                )
                if success:
                    email_send_count += 1
                else:
                    email_fail_count += 1
            except Exception as e:
                email_fail_count += 1
                logger.error(f"Failed to send expiry reminder to {sub.user.email} for sub ID {sub.id}: {e}", exc_info=True)
        else:
            logger.warning(f"Skipping expiry reminder for subscription ID {sub.id} due to missing user, plan, or end_date info.")
            email_fail_count +=1

    return {
        "message": f"Subscription expiry reminder process initiated.",
        "found_expiring_subscriptions": len(expiring_subs),
        "emails_sent_successfully": email_send_count,
        "emails_failed_to_send": email_fail_count
    }

@router.get("/subscriptions/{subscription_id}", response_model=sub_schemas.UserSubscriptionDisplay)
def admin_get_user_subscription_details(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Get details of a specific user subscription.
    """
    logger.info(f"Admin {current_admin.email} fetching details for subscription ID: {subscription_id}")
    db_sub = sub_crud.get_user_subscription(db, subscription_id)
    if not db_sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User subscription not found.")
    return db_sub


class PaginatedAdminPayments(BaseModel):
    total: int
    payments: List[pay_schemas.PaymentDisplay]
    page: int
    size: int

@router.get("/payments", response_model=PaginatedAdminPayments)
def admin_list_all_payments(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    skip: int = Query(0, ge=0, alias="page_offset"),
    limit: int = Query(20, ge=1, le=200, alias="page_size"),
    user_id: Optional[int] = Query(None, description="Filter by User ID"),
    status: Optional[str] = Query(None, description="Filter by Payment Status"), # Consider Enum
    gateway: Optional[str] = Query(None, description="Filter by Payment Gateway") # Consider Enum
):
    """
    Admin: List all payments with filters and pagination.
    """
    logger.info(f"Admin {current_admin.email} listing all payments.")
    filters = {"user_id": user_id, "status": status, "payment_gateway": gateway}
    active_filters = {k: v for k, v in filters.items() if v is not None}

    # These CRUD functions (get_all_payments, count_all_payments) need to be created in payment_crud.py
    total_payments = pay_crud.count_all_payments(db, filters=active_filters)
    payments_db = pay_crud.get_all_payments(db, skip=skip, limit=limit, filters=active_filters)

    return PaginatedAdminPayments(
        total=total_payments,
        payments=[pay_schemas.PaymentDisplay.from_orm(p) for p in payments_db],
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit
    )
