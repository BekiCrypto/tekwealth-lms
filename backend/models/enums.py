import enum

class CourseLevel(str, enum.Enum):
    BEGINNER = "Beginner"
    PRO = "Pro" # Intermediate might be a better term if there are 3 levels
    ADVANCED = "Advanced"

class CourseCategory(str, enum.Enum):
    FOREX = "Forex"
    CRYPTO = "Crypto"
    STOCKS = "Stocks" # Changed from STOCK to STOCKS for consistency
    COMMODITIES = "Commodities"

class ModuleContentType(str, enum.Enum):
    VIDEO = "Video"
    PDF = "PDF"
    QUIZ = "Quiz"
    TEXT = "Text" # Adding a generic text content type

class QuestionType(str, enum.Enum):
    MULTIPLE_CHOICE = "MultipleChoice" # Using CamelCase for consistency with other enums if they were classes
    TRUE_FALSE = "TrueFalse"
    SINGLE_CHOICE = "SingleChoice" # Often multiple choice implies only one answer, but being explicit

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled" # Canceled by user, might still be active until period end
    EXPIRED = "expired"   # Period ended and not renewed
    PENDING_PAYMENT = "pending_payment" # Initial payment pending or renewal payment failed
    INCOMPLETE = "incomplete" # Stripe specific: if initial payment fails or requires action

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded" # If you implement refunds

class PaymentGateway(str, enum.Enum):
    STRIPE = "stripe"
    CHAPA = "chapa"
    TELEBIRR = "telebirr"
    MANUAL = "manual" # For admin-recorded payments
    # Add other gateways like PayPal, etc.

class ReferralCommissionStatus(str, enum.Enum):
    PENDING = "pending"     # Commission generated, awaiting approval (e.g., after refund period)
    APPROVED = "approved"   # Commission approved, ready for payout
    PAID = "paid"           # Commission has been paid out
    REJECTED = "rejected"   # Commission rejected (e.g., fraudulent activity, refund)

# Example of how to use these in SQLAlchemy (illustrative, actual use in model.py)
# from sqlalchemy import Enum as SAEnum
# level = Column(SAEnum(CourseLevel, name="course_level_enum", create_type=False), nullable=False)

# The create_type=False flag is often used with Alembic to manage ENUM type creation/deletion manually
# or if the ENUM type is defined directly in PostgreSQL. For simplicity, FastAPI/SQLAlchemy can handle it.
# For PostgreSQL, it's common to create these as native PG ENUM types for efficiency.
# e.g. CREATE TYPE course_level_enum AS ENUM ('Beginner', 'Pro', 'Advanced');
# Then in SQLAlchemy: level = Column(SAEnum(CourseLevel, name="course_level_enum", create_type=False))
# If not using native PG ENUMs, SQLAlchemy will typically use VARCHAR.
# We'll let SQLAlchemy handle it for now, which might mean VARCHAR columns by default
# unless special dialect-specific types are used or `create_type=True` (with caution).
# For this project, we'll assume VARCHAR is acceptable for simplicity of setup without native DB enum management.
# If native DB enums are desired, Alembic migrations would be the place to define them.
