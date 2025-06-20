from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List # Any for webhook data
from datetime import datetime
from decimal import Decimal

from backend.models.enums import PaymentStatus, PaymentGateway
# from .subscription_schema import UserSubscriptionDisplay # Avoid direct import if circularity is an issue

# --- Payment Schemas ---
class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount paid")
    currency: str = Field("USD", max_length=10, description="Currency code")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="Status of the payment")
    payment_gateway: PaymentGateway = Field(..., description="Payment gateway used")

    # Optional fields, might be set based on context or gateway response
    user_id: Optional[int] = None # Usually set from current user or webhook context
    user_subscription_id: Optional[int] = Field(None, description="Associated user subscription ID, if applicable")

    transaction_id: Optional[str] = Field(None, max_length=255, description="Transaction ID from the payment gateway")
    payment_intent_id: Optional[str] = Field(None, max_length=255, description="Stripe Payment Intent ID (pi_xxxxxxxxxxxx)")
    invoice_url: Optional[HttpUrl] = Field(None, description="URL to the invoice (if provided by gateway). Use str if HttpUrl is too strict.")
    receipt_url: Optional[HttpUrl] = Field(None, description="URL to the receipt (if provided by gateway). Use str if HttpUrl is too strict.")
    error_message: Optional[str] = Field(None, description="Error message if payment failed")
    paid_at: Optional[datetime] = Field(None, description="Timestamp when payment was confirmed succeeded")


class PaymentCreate(PaymentBase): # Used by backend when a payment is initiated or recorded
    # Fields like user_id, user_subscription_id, amount, currency, payment_gateway are essential at creation.
    # Status typically defaults to PENDING.
    # transaction_id, payment_intent_id, etc., are often updated after gateway interaction.
    user_id: int # Must be known at creation
    payment_gateway: PaymentGateway
    pass # Most fields inherited from PaymentBase are fine for creation


class PaymentUpdate(BaseModel): # Used to update status and gateway info after payment processing
    status: Optional[PaymentStatus] = None
    transaction_id: Optional[str] = Field(None, max_length=255, nullable=True)
    payment_intent_id: Optional[str] = Field(None, max_length=255, nullable=True)
    invoice_url: Optional[HttpUrl] = Field(None, nullable=True)
    receipt_url: Optional[HttpUrl] = Field(None, nullable=True)
    error_message: Optional[str] = Field(None, nullable=True)
    paid_at: Optional[datetime] = Field(None, nullable=True)


class PaymentDisplay(PaymentBase):
    id: int
    # user: Optional[UserDisplay] # If User schema is simple enough to nest
    # user_subscription: Optional[UserSubscriptionDisplay] # If UserSubscription schema is simple enough
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Schemas for Payment Intent Creation & Webhooks ---

class PaymentIntentCreateRequest(BaseModel):
    plan_id: Optional[int] = Field(None, description="ID of the subscription plan to purchase/subscribe to.")
    # Could also include:
    # item_id: Optional[int] = Field(None, description="ID of a specific item for one-time purchase.")
    # amount: Optional[Decimal] = Field(None, description="Custom amount for payment, if not plan-based.")
    # currency: Optional[str] = Field("USD", description="Currency for custom amount.")
    payment_method_id: Optional[str] = Field(None, description="Stripe PaymentMethod ID (pm_xxxx), if already collected by client.")
    # coupon_code: Optional[str] = Field(None, description="Coupon code to apply.")


class PaymentIntentResponse(BaseModel):
    client_secret: Optional[str] = Field(None, description="The client secret for Stripe Payment Intents or Setup Intents.")
    # For other gateways, this might include a redirect_url or other necessary info.
    payment_intent_id: Optional[str] = Field(None, description="The ID of the Payment Intent created.")
    subscription_id: Optional[str] = Field(None, description="The ID of the Subscription created (if applicable).")
    status: str # Current status of the intent or subscription
    message: Optional[str] = "Payment intent created successfully."


# Basic structure for Stripe Webhook Event object (data.object part)
# This would need to be expanded based on the specific event types being handled.
class StripeObjectAttributes(BaseModel):
    id: Optional[str] = None
    customer: Optional[str] = None
    subscription: Optional[str] = None
    status: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    # For invoice events
    customer_email: Optional[str] = None
    amount_paid: Optional[int] = None # Stripe amounts are in cents
    amount_due: Optional[int] = None
    amount_remaining: Optional[int] = None
    charge: Optional[str] = None # Charge ID: ch_xxx
    payment_intent: Optional[str] = None # Payment Intent ID: pi_xxx
    hosted_invoice_url: Optional[HttpUrl] = None
    invoice_pdf: Optional[HttpUrl] = None
    # Add more fields as needed for specific event types like 'invoice.payment_succeeded', 'customer.subscription.updated', etc.

class StripeEventData(BaseModel):
    object: Dict[str, Any] # StripeObjectAttributes # Using Dict for flexibility, can be specific later

class StripeWebhookPayload(BaseModel):
    id: str = Field(..., description="Stripe Event ID (evt_xxxxxxxxxxxx)")
    type: str = Field(..., description="Stripe event type (e.g., invoice.payment_succeeded)")
    api_version: Optional[str] = None
    created: datetime
    data: StripeEventData
    livemode: bool
    pending_webhooks: Optional[int] = None
    request: Optional[Dict[str, Any]] = None

    class Config:
        # Pydantic v1 way for ORM mode, not strictly needed here but good practice
        # orm_mode = True
        # Pydantic v2 way
        from_attributes = True
