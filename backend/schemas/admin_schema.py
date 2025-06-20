from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime # For date/datetime fields
from decimal import Decimal # For monetary values

# --- Platform Overview Stats ---
class PlatformStatsOverview(BaseModel):
    total_users: int = Field(..., description="Total number of registered users")
    active_subscriptions: int = Field(..., description="Total number of currently active user subscriptions")
    total_courses: int = Field(..., description="Total number of courses on the platform")
    total_referral_earnings_pending: Decimal = Field(..., description="Total amount of pending referral commissions")
    total_revenue_all_time: Decimal = Field(..., description="Total revenue generated from successful payments")
    # Could add more like: new_users_last_30_days, revenue_last_30_days, etc.

# --- Course Analytics ---
class CourseAnalyticsInfo(BaseModel):
    course_id: int
    course_title: str
    enrolled_users_count: int = Field(..., description="Number of users who have interacted with or are enrolled in the course")
    average_completion_rate: float = Field(..., ge=0, le=100, description="Average course completion rate among users with progress")
    total_certificates_issued: int = Field(..., description="Total number of certificates issued for this course")

# --- Revenue Reporting ---
class RevenueDataPoint(BaseModel):
    period: str # Could be date (YYYY-MM-DD), month (YYYY-MM), or year (YYYY)
    amount: Decimal = Field(..., description="Total revenue for this period")

class RevenueReport(BaseModel):
    report_start_date: date
    report_end_date: date
    interval: str # daily, monthly, yearly
    data_points: List[RevenueDataPoint] = Field(..., description="List of revenue data points for the report period")
    total_revenue_in_period: Decimal = Field(..., description="Total revenue within the specified report period")

# --- Schemas for Admin listing of Subscriptions/Payments (can also live in subscription_schema/payment_schema if preferred) ---
# For now, keeping them here for admin context, but they might just be paginated versions of existing Display schemas.

# Example: If you need a specific admin view for UserSubscription that's different from UserSubscriptionDisplay
# class UserSubscriptionAdminView(UserSubscriptionDisplay): # Inherits and can add/override fields
#     # admin_notes: Optional[str] = None
#     pass

# class PaginatedAdminUserSubscriptions(BaseModel):
#     total: int
#     subscriptions: List[UserSubscriptionAdminView] # Or just UserSubscriptionDisplay
#     page: int
#     size: int

# class PaginatedAdminPayments(BaseModel):
#     total: int
#     payments: List[PaymentDisplay] # PaymentDisplay is likely sufficient
#     page: int
#     size: int

# These paginated responses can also be generic or defined directly in routes if simple.
# For now, the existing Display schemas will be used in lists in the admin routes.
# The specific pagination response models will be defined in the admin_routes.py if needed, similar to PaginatedUsersAdmin.
