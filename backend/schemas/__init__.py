# This file makes the 'schemas' directory a Python package.

from .user_schema import (
    UserBase, UserCreateInternal, UserDisplay, TokenData,
    UserRegisterRequest, UserLoginRequest, AuthResponse, UserUpdate,
    AdminUserUpdate, UserDetailAdminDisplay, UserCourseProgressSummary
)

from .course_schema import (
    CourseBase, CourseCreate, CourseUpdate, CourseDisplay,
    CourseModuleBase, CourseModuleCreate, CourseModuleUpdate, CourseModuleDisplay,
    ModuleContentBase, ModuleContentCreate, ModuleContentUpdate, ModuleContentDisplay,
    QuizBase, QuizCreate, QuizUpdate, QuizDisplay,
    QuestionBase, QuestionCreate, QuestionUpdate, QuestionDisplay,
    QuestionOptionBase, QuestionOptionCreate, QuestionOptionUpdate, QuestionOptionDisplay,
    PaginatedCourseList, UserDisplayRef
)

from .user_progress_schema import (
    UserProgressBase, UserProgressCreate, UserProgressUpdate, UserProgressDisplay
)

from .certificate_schema import (
    CertificateBase, CertificateCreate, CertificateDisplay
)

from .quiz_submission_schema import (
    QuizAnswerBase, QuizAnswerCreate, QuizSubmissionCreate, QuizResultDisplay, AnswerFeedback
)

from .subscription_schema import (
    SubscriptionPlanBase, SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanDisplay,
    UserSubscriptionBase, UserSubscriptionCreate, UserSubscriptionUpdate, UserSubscriptionDisplay
)

from .payment_schema import (
    PaymentBase, PaymentCreate, PaymentUpdate, PaymentDisplay,
    PaymentIntentCreateRequest, PaymentIntentResponse, StripeWebhookPayload
)

from .referral_schema import (
    UserInReferralDisplay, # Helper for nesting
    ReferralEarningBase, ReferralEarningCreate, ReferralEarningUpdate, ReferralEarningDisplay,
    DownlineUserNode, ReferralStats, MyReferralInfo
)

from .ai_schema import (
    AIChatMessage, AIChatRequest, AIChatResponse,
    QuizGenerationRequest, GeneratedQuestionOption, GeneratedQuestion, QuizGenerationResponse
)

from .admin_schema import ( # Added Admin/Analytics Schemas
    PlatformStatsOverview, CourseAnalyticsInfo, RevenueDataPoint, RevenueReport
)


__all__ = [
    # User Schemas
    "UserBase", "UserCreateInternal", "UserDisplay", "TokenData",
    "UserRegisterRequest", "UserLoginRequest", "AuthResponse", "UserUpdate",
    "AdminUserUpdate", "UserDetailAdminDisplay", "UserCourseProgressSummary",

    # Course Schemas
    "CourseBase", "CourseCreate", "CourseUpdate", "CourseDisplay",
    "CourseModuleBase", "CourseModuleCreate", "CourseModuleUpdate", "CourseModuleDisplay",
    "ModuleContentBase", "ModuleContentCreate", "ModuleContentUpdate", "ModuleContentDisplay",
    "QuizBase", "QuizCreate", "QuizUpdate", "QuizDisplay",
    "QuestionBase", "QuestionCreate", "QuestionUpdate", "QuestionDisplay",
    "QuestionOptionBase", "QuestionOptionCreate", "QuestionOptionUpdate", "QuestionOptionDisplay",
    "PaginatedCourseList", "UserDisplayRef",

    # User Progress Schemas
    "UserProgressBase", "UserProgressCreate", "UserProgressUpdate", "UserProgressDisplay",

    # Certificate Schemas
    "CertificateBase", "CertificateCreate", "CertificateDisplay",

    # Quiz Submission Schemas
    "QuizAnswerBase", "QuizAnswerCreate", "QuizSubmissionCreate", "QuizResultDisplay", "AnswerFeedback",

    # Subscription Schemas
    "SubscriptionPlanBase", "SubscriptionPlanCreate", "SubscriptionPlanUpdate", "SubscriptionPlanDisplay",
    "UserSubscriptionBase", "UserSubscriptionCreate", "UserSubscriptionUpdate", "UserSubscriptionDisplay",

    # Payment Schemas
    "PaymentBase", "PaymentCreate", "PaymentUpdate", "PaymentDisplay",
    "PaymentIntentCreateRequest", "PaymentIntentResponse", "StripeWebhookPayload",

    # Referral Schemas
    "UserInReferralDisplay",
    "ReferralEarningBase", "ReferralEarningCreate", "ReferralEarningUpdate", "ReferralEarningDisplay",
    "DownlineUserNode", "ReferralStats", "MyReferralInfo",

    # AI Schemas
    "AIChatMessage", "AIChatRequest", "AIChatResponse",
    "QuizGenerationRequest", "GeneratedQuestionOption", "GeneratedQuestion", "QuizGenerationResponse",

    # Admin/Analytics Schemas
    "PlatformStatsOverview", "CourseAnalyticsInfo", "RevenueDataPoint", "RevenueReport",
]

# Forward reference resolution for Pydantic v1 (UserDetailAdminDisplay uses TYPE_CHECKING for v2 compatibility)
# If UserDetailAdminDisplay directly used string forward refs like 'UserSubscriptionDisplay',
# and if UserSubscriptionDisplay also had refs, this is where you'd call .update_forward_refs().
# e.g., UserDetailAdminDisplay.update_forward_refs()
# (This assumes UserDetailAdminDisplay itself is imported here, which it is via user_schema)
# For Pydantic v2, this is mostly automatic.
# Check user_schema.py for how UserDetailAdminDisplay handles its forward refs.
# It currently uses `if TYPE_CHECKING:` for imports, which is good for static type checking
# and Pydantic v2's runtime resolution.
# If any `NameError` occurs at runtime due to unresolved forward refs,
# explicit `Model.model_rebuild()` calls for relevant models might be needed here.
