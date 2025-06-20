from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case
from decimal import Decimal
from datetime import date, timedelta, datetime
from typing import List, Dict

from backend.models.user_model import User
from backend.models.subscription_model import UserSubscription
from backend.models.course_model import Course, ModuleContent, CourseModule
from backend.models.referral_model import ReferralEarning
from backend.models.payment_model import Payment
from backend.models.certificate_model import Certificate
from backend.models.user_progress_model import UserProgress

from backend.models.enums import SubscriptionStatus, PaymentStatus, ReferralCommissionStatus

from backend.schemas import admin_schema as schemas # For response models
from backend.crud import user_crud # For count_users

import logging
logger = logging.getLogger(__name__)

def get_platform_stats_overview(db: Session) -> schemas.PlatformStatsOverview:
    logger.debug("Calculating platform stats overview.")

    total_users = user_crud.count_users(db) # Reusing existing CRUD

    active_subscriptions = db.query(func.count(UserSubscription.id)).filter(
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    total_courses = db.query(func.count(Course.id)).scalar() or 0

    total_referral_earnings_pending = db.query(func.sum(ReferralEarning.commission_amount)).filter(
        ReferralEarning.status == ReferralCommissionStatus.PENDING
    ).scalar() or Decimal("0.00")

    total_revenue_all_time = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.SUCCEEDED
    ).scalar() or Decimal("0.00")

    return schemas.PlatformStatsOverview(
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        total_courses=total_courses,
        total_referral_earnings_pending=total_referral_earnings_pending,
        total_revenue_all_time=total_revenue_all_time,
    )

def get_courses_analytics(db: Session) -> List[schemas.CourseAnalyticsInfo]:
    logger.debug("Calculating courses analytics.")
    courses = db.query(Course).all()
    analytics_results: List[schemas.CourseAnalyticsInfo] = []

    for course in courses:
        # Enrolled users count: Defined as users who have at least one progress entry for any content in this course.
        # This is a simplification; a more robust count might look at active subscriptions to this course if it's not part of a general plan.
        enrolled_users_count = db.query(func.count(func.distinct(UserProgress.user_id))).filter(
            UserProgress.course_id == course.id
        ).scalar() or 0

        # Average completion rate
        # Get total number of content items in the course
        total_contents_in_course = db.query(func.count(ModuleContent.id)).join(CourseModule).filter(
            CourseModule.course_id == course.id
        ).scalar() or 0

        avg_completion_rate = 0.0
        if enrolled_users_count > 0 and total_contents_in_course > 0:
            # Sum of completion percentages for each user in this course / number of users with progress
            # This requires calculating completion for each user first.
            # Simpler: (total completed content items by all users in course) / (total content items * enrolled_users_count)
            # More accurate: Average of individual user completion percentages.

            # Let's calculate completion per user and average that.
            users_with_progress = db.query(UserProgress.user_id).filter(UserProgress.course_id == course.id).distinct().all()
            user_ids_with_progress = [uid[0] for uid in users_with_progress]

            total_completion_sum = Decimal(0.0)
            if user_ids_with_progress:
                for user_id in user_ids_with_progress:
                    completed_by_user = db.query(func.count(UserProgress.id)).filter(
                        UserProgress.user_id == user_id,
                        UserProgress.course_id == course.id,
                        UserProgress.completed_at.isnot(None)
                    ).scalar() or 0
                    user_completion_rate = (Decimal(completed_by_user) / Decimal(total_contents_in_course)) * 100
                    total_completion_sum += user_completion_rate
                avg_completion_rate = float(total_completion_sum / Decimal(len(user_ids_with_progress)))

        total_certificates_issued = db.query(func.count(Certificate.id)).filter(
            Certificate.course_id == course.id
        ).scalar() or 0

        analytics_results.append(schemas.CourseAnalyticsInfo(
            course_id=course.id,
            course_title=course.title,
            enrolled_users_count=enrolled_users_count,
            average_completion_rate=round(avg_completion_rate, 2),
            total_certificates_issued=total_certificates_issued,
        ))
    return analytics_results

def get_revenue_over_time(db: Session, start_date: date, end_date: date, interval: str = 'daily') -> schemas.RevenueReport:
    logger.debug(f"Calculating revenue report from {start_date} to {end_date}, interval: {interval}")

    query = db.query(
        # func.sum(Payment.amount).label("total_amount"),
        # func.date_trunc(interval, Payment.paid_at).label("period_start") # Not directly usable for all intervals with date_trunc
    ).filter(
        Payment.status == PaymentStatus.SUCCEEDED,
        Payment.paid_at >= start_date,
        Payment.paid_at < (end_date + timedelta(days=1)) # Ensure end_date is inclusive
    )

    data_points_dict: Dict[str, Decimal] = {}

    if interval == 'daily':
        query = query.add_columns(func.sum(Payment.amount).label("total_amount"), func.date(Payment.paid_at).label("period"))
        query = query.group_by(func.date(Payment.paid_at)).order_by(func.date(Payment.paid_at))
        results = query.all()
        for res in results:
            data_points_dict[res.period.isoformat()] = res.total_amount
    elif interval == 'monthly':
        query = query.add_columns(func.sum(Payment.amount).label("total_amount"),
                                  extract('year', Payment.paid_at).label("year"),
                                  extract('month', Payment.paid_at).label("month"))
        query = query.group_by(extract('year', Payment.paid_at), extract('month', Payment.paid_at))
        query = query.order_by(extract('year', Payment.paid_at), extract('month', Payment.paid_at))
        results = query.all()
        for res in results:
            period_label = f"{int(res.year)}-{int(res.month):02d}"
            data_points_dict[period_label] = res.total_amount
    elif interval == 'yearly':
        query = query.add_columns(func.sum(Payment.amount).label("total_amount"), extract('year', Payment.paid_at).label("year"))
        query = query.group_by(extract('year', Payment.paid_at)).order_by(extract('year', Payment.paid_at))
        results = query.all()
        for res in results:
            data_points_dict[str(int(res.year))] = res.total_amount
    else:
        raise ValueError("Invalid interval. Choose from 'daily', 'monthly', 'yearly'.")

    # Fill missing dates/periods with zero if needed (for charting continuity)
    # This part can be complex and depends on desired output. For now, direct results.

    revenue_data_points = [schemas.RevenueDataPoint(period=key, amount=value) for key, value in data_points_dict.items()]
    total_revenue_in_period = sum(dp.amount for dp in revenue_data_points)

    return schemas.RevenueReport(
        report_start_date=start_date,
        report_end_date=end_date,
        interval=interval,
        data_points=revenue_data_points,
        total_revenue_in_period=total_revenue_in_period
    )
