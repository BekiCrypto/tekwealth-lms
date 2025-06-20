# This file makes the 'crud' directory a Python package.

from .user_crud import (
    get_user_by_id,
    get_user_by_email,
    get_user_by_firebase_uid,
    get_user_by_referral_code,
    create_user,
    get_users,
    count_users,
    update_user_by_admin
)

from .course_crud import (
    create_course, get_course, get_courses, update_course, delete_course,
    create_course_module, get_module, get_modules_for_course, update_course_module, delete_course_module,
    create_module_content, get_content, get_contents_for_module, update_module_content, delete_module_content,
    create_quiz_for_content, get_quiz_with_questions, update_quiz, submit_quiz
)

from .user_progress_crud import (
    create_or_update_user_progress,
    get_user_progress_for_content,
    get_user_progress_for_course,
    get_course_completion_percentage,
    get_last_accessed_content_for_course
)

from .certificate_crud import (
    create_certificate, get_certificate_by_id, get_certificate_by_verification_code,
    get_certificates_for_user, get_certificates_for_course, update_certificate_url
)

from .subscription_crud import (
    create_subscription_plan, get_subscription_plan, get_active_subscription_plans, update_subscription_plan,
    get_subscription_plan_by_stripe_id,
    create_user_subscription, get_user_subscription, get_active_user_subscription, update_user_subscription_status,
    get_user_subscription_by_stripe_id, process_subscription_renewal, cancel_user_subscription_locally,
    get_all_user_subscriptions, count_all_user_subscriptions # Added admin listing functions
)

from .payment_crud import (
    create_payment_record, get_payment_by_id, get_payment_by_transaction_id, get_payment_by_payment_intent_id,
    get_payments_for_user, get_payments_for_subscription, update_payment_status,
    get_all_payments, count_all_payments # Added admin listing functions
)

from .referral_crud import (
    create_referral_earning, get_referral_earning_by_id, get_referral_earnings_for_user,
    get_all_referral_earnings, update_referral_earning_status,
    get_downline_users_flat, get_referral_stats_for_user
)

from .analytics_crud import (
    get_platform_stats_overview,
    get_courses_analytics,
    get_revenue_over_time
)


__all__ = [
    # User CRUD
    "get_user_by_id", "get_user_by_email", "get_user_by_firebase_uid", "get_user_by_referral_code", "create_user",
    "get_users", "count_users", "update_user_by_admin",

    # Course CRUD
    "create_course", "get_course", "get_courses", "update_course", "delete_course",
    "create_course_module", "get_module", "get_modules_for_course", "update_course_module", "delete_course_module",
    "create_module_content", "get_content", "get_contents_for_module", "update_module_content", "delete_module_content",
    "create_quiz_for_content", "get_quiz_with_questions", "update_quiz", "submit_quiz",

    # User Progress CRUD
    "create_or_update_user_progress", "get_user_progress_for_content", "get_user_progress_for_course",
    "get_course_completion_percentage", "get_last_accessed_content_for_course",

    # Certificate CRUD
    "create_certificate", "get_certificate_by_id", "get_certificate_by_verification_code",
    "get_certificates_for_user", "get_certificates_for_course", "update_certificate_url",

    # Subscription CRUD
    "create_subscription_plan", "get_subscription_plan", "get_active_subscription_plans", "update_subscription_plan",
    "get_subscription_plan_by_stripe_id",
    "create_user_subscription", "get_user_subscription", "get_active_user_subscription", "update_user_subscription_status",
    "get_user_subscription_by_stripe_id", "process_subscription_renewal", "cancel_user_subscription_locally",
    "get_all_user_subscriptions", "count_all_user_subscriptions",


    # Payment CRUD
    "create_payment_record", "get_payment_by_id", "get_payment_by_transaction_id", "get_payment_by_payment_intent_id",
    "get_payments_for_user", "get_payments_for_subscription", "update_payment_status",
    "get_all_payments", "count_all_payments",

    # Referral CRUD
    "create_referral_earning", "get_referral_earning_by_id", "get_referral_earnings_for_user",
    "get_all_referral_earnings", "update_referral_earning_status",
    "get_downline_users_flat", "get_referral_stats_for_user",

    # Analytics CRUD
    "get_platform_stats_overview", "get_courses_analytics", "get_revenue_over_time",
]
