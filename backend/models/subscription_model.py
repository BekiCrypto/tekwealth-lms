from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, TIMESTAMP, DECIMAL,
    Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta

from backend.core.database import Base
from backend.models.enums import SubscriptionStatus

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True) # e.g., "Monthly Premium", "Annual Pro"
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False) # e.g., 29.99
    currency = Column(String(10), nullable=False, default="USD")

    # Duration in days. Nullable for lifetime or other non-fixed period plans.
    duration_days = Column(Integer, nullable=True)

    # Payment gateway specific plan/price IDs
    stripe_price_id = Column(String(255), nullable=True, unique=True) # Stripe Price ID (price_xxxxxxxx)
    chapa_plan_id = Column(String(255), nullable=True, unique=True) # Placeholder for Chapa
    telebirr_plan_id = Column(String(255), nullable=True, unique=True) # Placeholder for Telebirr

    is_active = Column(Boolean, default=True, nullable=False) # Admins can deactivate plans

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship to UserSubscription
    user_subscriptions = relationship("UserSubscription", back_populates="plan")

    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, name='{self.name}', price={self.price} {self.currency})>"

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False) # Don't delete plan if users are subscribed

    start_date = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    end_date = Column(TIMESTAMP(timezone=True), nullable=True) # Nullable for lifetime plans or if managed by Stripe period end

    status = Column(SAEnum(SubscriptionStatus, name="subscription_status_enum", values_callable=lambda obj: [e.value for e in obj]),
                    nullable=False, default=SubscriptionStatus.PENDING_PAYMENT, index=True)

    # Stripe specific fields
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True) # sub_xxxxxxxx
    # Timestamps for the current billing period from Stripe, helps manage access
    current_period_start = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end = Column(TIMESTAMP(timezone=True), nullable=True)
    # If true, the subscription will cancel at current_period_end (set via Stripe dashboard or API)
    cancel_at_period_end = Column(Boolean, default=False)
    # payment_method_id = Column(String(255), nullable=True) # Optional: Store default payment method ID for subscription

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="user_subscriptions")
    payments = relationship("Payment", back_populates="user_subscription") # Payments made for this subscription

    def __repr__(self):
        return f"<UserSubscription(id={self.id}, user_id={self.user_id}, plan_id={self.plan_id}, status='{self.status}')>"

    # Helper to calculate end_date if plan has duration and start_date is known
    def calculate_end_date(self):
        if self.start_date and self.plan and self.plan.duration_days:
            return self.start_date + timedelta(days=self.plan.duration_days)
        return None

    # Example: Check if subscription is currently active based on dates and status
    # This logic can become complex with grace periods, payment failures, etc.
    # For Stripe-managed subscriptions, `status` and `current_period_end` are key.
    def is_currently_active(self) -> bool:
        if self.status == SubscriptionStatus.ACTIVE:
            if self.end_date: # Fixed duration or Stripe period end known
                return datetime.utcnow().replace(tzinfo=None) < self.end_date.replace(tzinfo=None) # Naive comparison for simplicity
            return True # Lifetime or no explicit end_date, but status is active
        return False
