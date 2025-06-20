import stripe # Stripe Python library
import os
import logging
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Tuple

from backend.models.user_model import User
from backend.models.subscription_model import SubscriptionPlan, UserSubscription
from backend.crud import user_crud, subscription_crud # To update user's stripe_customer_id or subscription details
from backend.schemas import payment_schema as payment_schemas # For type hinting if needed

logger = logging.getLogger(__name__)

# --- Stripe API Configuration ---
# Keys are loaded from environment variables
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET") # For verifying webhook signatures

if not STRIPE_API_KEY:
    logger.warning("STRIPE_API_KEY environment variable not set. Stripe functionality will be disabled.")
    # You might raise an error here or allow the app to run with Stripe disabled.
else:
    stripe.api_key = STRIPE_API_KEY
    # You can also set stripe.api_version if you need to pin to a specific version
    # stripe.api_version = "2020-08-27" # Example version

# --- Stripe Customer Management ---
def get_or_create_stripe_customer(db: Session, user: User) -> Optional[stripe.Customer]:
    """
    Retrieves an existing Stripe Customer object for the user, or creates a new one.
    Stores the stripe_customer_id on the User model.
    """
    if not STRIPE_API_KEY:
        logger.error("Stripe API key not configured. Cannot create Stripe customer.")
        return None

    if user.stripe_customer_id:
        try:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)
            logger.info(f"Retrieved Stripe customer {user.stripe_customer_id} for user {user.email}")
            return customer
        except stripe.error.StripeError as e:
            logger.warning(f"Error retrieving Stripe customer {user.stripe_customer_id} for user {user.email}: {e}. Will attempt to create a new one.")
            # Fall through to create if retrieval fails (e.g., customer deleted in Stripe)

    try:
        customer_params = {
            "email": user.email,
            "name": f"User {user.id}", # Or user.full_name if you have it
            "metadata": {"app_user_id": user.id, "firebase_uid": user.firebase_uid}
        }
        customer = stripe.Customer.create(**customer_params)
        logger.info(f"Created Stripe customer {customer.id} for user {user.email}")

        # Save the new stripe_customer_id to the user model
        user.stripe_customer_id = customer.id
        db.commit()
        db.refresh(user)
        logger.info(f"Saved stripe_customer_id {customer.id} to user {user.email} (ID: {user.id})")
        return customer
    except stripe.error.StripeError as e:
        logger.error(f"Error creating Stripe customer for user {user.email}: {e}", exc_info=True)
        return None
    except Exception as e: # Catch DB commit errors
        db.rollback()
        logger.error(f"DB Error saving stripe_customer_id for user {user.email} after Stripe creation: {e}", exc_info=True)
        # Potentially delete the customer in Stripe if DB save fails to avoid orphaned Stripe customers?
        # stripe.Customer.delete(customer.id) # Risky, consider implications
        return None

# --- Stripe Payment Intent Management ---
def create_stripe_payment_intent(
    amount_cents: int, # Amount in cents
    currency: str,
    customer_id: Optional[str] = None, # Stripe customer ID
    payment_method_id: Optional[str] = None, # pm_xxx, if already known
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    setup_future_usage: Optional[str] = None # e.g., 'off_session' or 'on_session'
) -> Optional[stripe.PaymentIntent]:
    """
    Creates a Stripe PaymentIntent.
    """
    if not STRIPE_API_KEY: return None
    try:
        params = {
            "amount": amount_cents,
            "currency": currency.lower(),
            "metadata": metadata or {},
            "description": description,
        }
        if customer_id:
            params["customer"] = customer_id
        if payment_method_id:
            params["payment_method"] = payment_method_id
            # If payment_method is provided, you might want to confirm it immediately
            # params["confirm"] = True # This attempts to charge immediately
            # params["confirmation_method"] = "manual" # if you confirm on client
        if setup_future_usage and not payment_method_id: # setup_future_usage typically used with new payment method
             params["setup_future_usage"] = setup_future_usage

        # If not confirming now, client will use client_secret to confirm with payment details.
        # If payment_method_id is provided and you want to save it for future use with a subscription,
        # it's better to attach it to a customer and then create a subscription.
        # For one-off payments, payment_method can be passed directly.

        payment_intent = stripe.PaymentIntent.create(**params)
        logger.info(f"Stripe PaymentIntent {payment_intent.id} created. Amount: {amount_cents} {currency.upper()}. Status: {payment_intent.status}")
        return payment_intent
    except stripe.error.StripeError as e:
        logger.error(f"Error creating Stripe PaymentIntent: {e}", exc_info=True)
        return None

# --- Stripe Subscription Management ---
def create_stripe_subscription(
    customer_id: str,
    stripe_price_id: str, # Price ID (price_xxxx) from your Stripe product setup
    coupon_id: Optional[str] = None,
    trial_period_days: Optional[int] = None,
    default_payment_method: Optional[str] = None, # pm_xxx
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[stripe.Subscription], Optional[stripe.PaymentIntent]]:
    """
    Creates a new Stripe subscription for a customer with a given price ID.
    Returns the Subscription object and, if the first invoice needs immediate payment,
    the associated PaymentIntent.
    """
    if not STRIPE_API_KEY: return None, None
    try:
        sub_params = {
            "customer": customer_id,
            "items": [{"price": stripe_price_id}],
            "metadata": metadata or {},
            "expand": ["latest_invoice.payment_intent"] # Crucial to get client_secret if needed
        }
        if coupon_id:
            sub_params["coupon"] = coupon_id
        if trial_period_days:
            sub_params["trial_period_days"] = trial_period_days
        if default_payment_method: # If a payment method is already collected and attached to customer
            sub_params["default_payment_method"] = default_payment_method
        else: # If no default PM, Stripe will attempt to charge the customer's default source or create an invoice that needs payment.
             # For new subscriptions, it's common to require payment upfront.
             sub_params["payment_behavior"] = "default_incomplete" # Creates PI if payment needed

        subscription = stripe.Subscription.create(**sub_params)
        logger.info(f"Stripe Subscription {subscription.id} created for customer {customer_id}, price {stripe_price_id}. Status: {subscription.status}")

        payment_intent = None
        if subscription.status == 'incomplete' and subscription.latest_invoice and subscription.latest_invoice.payment_intent:
            payment_intent = subscription.latest_invoice.payment_intent
            logger.info(f"Subscription requires payment. PaymentIntent ID: {payment_intent.id}, Status: {payment_intent.status}")
            if isinstance(payment_intent, str): # If only ID is returned, retrieve the full object
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent)

        return subscription, payment_intent
    except stripe.error.StripeError as e:
        logger.error(f"Error creating Stripe subscription: {e}", exc_info=True)
        return None, None

def cancel_stripe_subscription(stripe_subscription_id: str, at_period_end: bool = True) -> Optional[stripe.Subscription]:
    """
    Cancels a Stripe subscription.
    If `at_period_end` is True (default), it will cancel at the end of the current billing period.
    If False, it attempts to cancel immediately (prorations might apply or not, depending on Stripe settings).
    """
    if not STRIPE_API_KEY: return None
    try:
        if at_period_end:
            subscription = stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=True)
            logger.info(f"Stripe Subscription {stripe_subscription_id} scheduled for cancellation at period end.")
        else: # Immediate cancellation
            subscription = stripe.Subscription.delete(stripe_subscription_id)
            logger.info(f"Stripe Subscription {stripe_subscription_id} canceled immediately.")
        return subscription
    except stripe.error.StripeError as e:
        logger.error(f"Error canceling Stripe subscription {stripe_subscription_id}: {e}", exc_info=True)
        return None

# --- Stripe Webhook Handling ---
def construct_stripe_webhook_event(payload: bytes, sig_header: str) -> Optional[stripe.Event]:
    """
    Verifies and constructs a Stripe webhook event.
    `payload` is the raw request body.
    `sig_header` is the value of the 'Stripe-Signature' header.
    """
    if not STRIPE_API_KEY or not STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe API key or Webhook secret not configured. Cannot process webhook.")
        return None
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        logger.info(f"Stripe webhook event constructed: ID: {event.id}, Type: {event.type}")
        return event
    except ValueError as e: # Invalid payload
        logger.error(f"Invalid Stripe webhook payload: {e}", exc_info=True)
        return None
    except stripe.error.SignatureVerificationError as e: # Invalid signature
        logger.error(f"Stripe webhook signature verification failed: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error constructing Stripe webhook event: {e}", exc_info=True)
        return None

# --- Other Utility Functions (Examples) ---
def retrieve_stripe_invoice(invoice_id: str) -> Optional[stripe.Invoice]:
    if not STRIPE_API_KEY: return None
    try:
        invoice = stripe.Invoice.retrieve(invoice_id)
        return invoice
    except stripe.error.StripeError as e:
        logger.error(f"Error retrieving Stripe invoice {invoice_id}: {e}")
        return None

def list_stripe_subscription_items(subscription_id: str) -> List[stripe.SubscriptionItem]:
    if not STRIPE_API_KEY: return []
    try:
        items = stripe.SubscriptionItem.list(subscription=subscription_id)
        return items.data
    except stripe.error.StripeError as e:
        logger.error(f"Error listing items for Stripe subscription {subscription_id}: {e}")
        return []
