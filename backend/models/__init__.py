# This file makes the 'models' directory a Python package.

from backend.core.database import Base # Base must be imported before models that use it

from .enums import ( # Import all enums
    CourseLevel, CourseCategory, ModuleContentType, QuestionType,
    SubscriptionStatus, PaymentStatus, PaymentGateway, ReferralCommissionStatus
)

from .user_model import User
from .course_model import (
    Course,
    CourseModule,
    ModuleContent,
    Quiz,
    Question,
    QuestionOption
)
from .user_progress_model import UserProgress
from .certificate_model import Certificate
from .subscription_model import SubscriptionPlan, UserSubscription
from .payment_model import Payment
from .referral_model import ReferralEarning


# You can add other models here as they are created for other features

__all__ = [
    "Base",
    # Models
    "User",
    "Course",
    "CourseModule",
    "ModuleContent",
    "Quiz",
    "Question",
    "QuestionOption",
    "UserProgress",
    "Certificate",
    "SubscriptionPlan",
    "UserSubscription",
    "Payment",
    "ReferralEarning",
    # Enums
    "CourseLevel",
    "CourseCategory",
    "ModuleContentType",
    "QuestionType",
    "SubscriptionStatus",
    "PaymentStatus",
    "PaymentGateway",
    "ReferralCommissionStatus",
]
