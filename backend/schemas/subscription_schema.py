from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from decimal import Decimal # For price

from backend.models.enums import SubscriptionStatus # Import the enum

# --- SubscriptionPlan Schemas ---
class SubscriptionPlanBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Name of the subscription plan")
    description: Optional[str] = Field(None, max_length=1000, description="Detailed description of the plan")
    price: Decimal = Field(..., gt=0, description="Price of the plan")
    currency: str = Field("USD", max_length=10, description="Currency code (e.g., USD, EUR)")
    duration_days: Optional[int] = Field(None, gt=0, description="Duration of the plan in days (null for lifetime)")
    is_active: bool = Field(True, description="Whether the plan is currently active and available for new subscriptions")

class SubscriptionPlanCreate(SubscriptionPlanBase):
    # Gateway specific IDs are usually set by admin or system, not direct user input during creation of plan itself by API.
    # These can be part of an update schema or a separate admin interface.
    stripe_price_id: Optional[str] = Field(None, max_length=255, description="Stripe Price ID (e.g., price_xxxxxxxxxxxx)")
    chapa_plan_id: Optional[str] = Field(None, max_length=255, description="Chapa Plan ID (placeholder)")
    telebirr_plan_id: Optional[str] = Field(None, max_length=255, description="Telebirr Plan ID (placeholder)")

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=10)
    duration_days: Optional[int] = Field(None, gt=0, nullable=True) # Allow setting to null explicitly
    is_active: Optional[bool] = None
    stripe_price_id: Optional[str] = Field(None, max_length=255, nullable=True)
    chapa_plan_id: Optional[str] = Field(None, max_length=255, nullable=True)
    telebirr_plan_id: Optional[str] = Field(None, max_length=255, nullable=True)

class SubscriptionPlanDisplay(SubscriptionPlanBase):
    id: int
    stripe_price_id: Optional[str] = None # Display if available
    # Do not display other gateway plan IDs unless necessary for client
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- UserSubscription Schemas ---
class UserSubscriptionBase(BaseModel):
    user_id: int # Usually set from current user context
    plan_id: int # From request, e.g., when user chooses a plan
    status: SubscriptionStatus = Field(..., description="Status of the user's subscription")
    start_date: datetime = Field(default_factory=datetime.utcnow, description="Start date of the subscription")
    end_date: Optional[datetime] = Field(None, description="End date of the subscription (null for lifetime or if managed by Stripe period end)")

    # Stripe specific fields, might be updated via webhooks or after successful subscription
    stripe_subscription_id: Optional[str] = Field(None, max_length=255, description="Stripe Subscription ID (sub_xxxxxxxxxxxx)")
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class UserSubscriptionCreate(BaseModel): # Schema for initiating a subscription by user
    plan_id: int = Field(..., description="ID of the chosen subscription plan")
    # user_id is from token. start_date, end_date, status, stripe_subscription_id are set by backend.


class UserSubscriptionUpdate(BaseModel): # For admin or webhook updates
    status: Optional[SubscriptionStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = Field(None, nullable=True) # Allow unsetting end_date
    stripe_subscription_id: Optional[str] = Field(None, max_length=255, nullable=True)
    current_period_start: Optional[datetime] = Field(None, nullable=True)
    current_period_end: Optional[datetime] = Field(None, nullable=True)
    cancel_at_period_end: Optional[bool] = None


class UserSubscriptionDisplay(UserSubscriptionBase):
    id: int
    plan: SubscriptionPlanDisplay # Nested display of the plan details
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
