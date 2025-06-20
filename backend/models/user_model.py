from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.core.database import Base # Import Base from the new location

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String(255), unique=True, index=True, nullable=False) # Firebase User ID
    email = Column(String(255), unique=True, index=True, nullable=False)
    # Password hash is removed as Firebase handles authentication.
    # If you still need to store a password for some reason (e.g., legacy system), reconsider.
    # password_hash = Column(String(255), nullable=False)

    role = Column(String(50), nullable=False, default='Subscriber') # e.g., Guest, Subscriber, Admin, MLM Partner

    referral_code = Column(String(255), unique=True, nullable=True) # User's own referral code

    # To track who referred this user
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationship to access the user who referred this one
    # `referred_by_id` is the direct referrer (L1 upline)
    referrer = relationship("User", remote_side=[id], foreign_keys=[referred_by_id], backref="directly_referred_users")
    # We rename 'referrer' to 'upline_l1' to match new field names for clarity in MLM context.
    # The 'referred_by_id' column will now be primarily associated with 'upline_l1'.

    # Upline structure for MLM
    upline_l1_id = Column(Integer, ForeignKey("users.id", name="fk_user_upline_l1"), nullable=True)
    upline_l2_id = Column(Integer, ForeignKey("users.id", name="fk_user_upline_l2"), nullable=True)
    upline_l3_id = Column(Integer, ForeignKey("users.id", name="fk_user_upline_l3"), nullable=True)

    # Relationships for upline
    upline_l1 = relationship("User", remote_side=[id], foreign_keys=[upline_l1_id], backref="downline_l1", lazy="joined")
    upline_l2 = relationship("User", remote_side=[id], foreign_keys=[upline_l2_id], backref="downline_l2", lazy="joined")
    upline_l3 = relationship("User", remote_side=[id], foreign_keys=[upline_l3_id], backref="downline_l3", lazy="joined")

    # Note: 'referred_users' backref from original 'referrer' relationship might need adjustment if 'referrer' is fully replaced by 'upline_l1'.
    # For now, `referred_by_id` still exists and `referrer` points to it.
    # If `referred_by_id` is a duplicate of `upline_l1_id`, consider consolidating.
    # Let's assume `referred_by_id` is the primary link for direct referral, and `upline_l1_id` is functionally the same.
    # We will ensure `upline_l1_id` is populated from `referred_by_id` or vice versa.

    # Payment Gateway Customer ID
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True) # Stripe Customer ID (cus_xxxxxxxx)
    # Add other gateway customer IDs if needed: chapa_customer_id, etc.

    # Relationships to other tables
    courses_owned = relationship("Course", back_populates="owner", cascade="all, delete-orphan")
    progress_entries = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    # Earnings from referrals
    referral_earnings = relationship("ReferralEarning", foreign_keys="[ReferralEarning.user_id]", back_populates="earning_user", cascade="all, delete-orphan")
    # Referrals made by this user that resulted in earnings (less common to query this way, usually via referred_user_id on earning)
    # earnings_from_referrals_made = relationship("ReferralEarning", foreign_keys="[ReferralEarning.referred_user_id]", back_populates="referred_user_obj")


    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # If you have related tables like subscriptions, payments, they can be defined here
    # Example:
    # subscriptions_example = relationship("Subscription", back_populates="user") # Keeping your commented examples distinct
    # payments_example = relationship("Payment", back_populates="user")

    __table_args__ = (
        UniqueConstraint('email', name='uq_user_email'),
        UniqueConstraint('firebase_uid', name='uq_user_firebase_uid'),
        UniqueConstraint('referral_code', name='uq_user_referral_code'),
        UniqueConstraint('stripe_customer_id', name='uq_user_stripe_customer_id'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', firebase_uid='{self.firebase_uid}', role='{self.role}')>"
