from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import stripe # For type hints and potential errors from service
from datetime import datetime

from backend.core.database import get_db
from backend.core.dependencies import get_current_active_user, get_current_admin_user
from backend.core.payments import stripe_service # Stripe interactions
from backend.models.user_model import User
from backend.models.enums import SubscriptionStatus, PaymentStatus, PaymentGateway
from backend.schemas import (
    subscription_schema as sub_schemas,
    payment_schema as pay_schemas,
    referral_schema as ref_schemas, # For creating ReferralEarning
    course_schema as course_schemas # For course details in email
)
from backend.crud import (
    subscription_crud as sub_crud,
    payment_crud as pay_crud,
    user_crud,
    referral_crud as ref_crud,
    course_crud # To get course details for email
)
from backend.services import email_service # For sending emails
import os
from decimal import Decimal
from backend.models.enums import ReferralCommissionStatus # For commission creation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions & Payments"])

# --- Subscription Plan Endpoints (Admin) ---
@router.post("/admin/plans", response_model=sub_schemas.SubscriptionPlanDisplay, status_code=status.HTTP_201_CREATED)
def admin_create_subscription_plan(
    plan_in: sub_schemas.SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Create a new subscription plan.
    """
    logger.info(f"Admin {current_admin.email} creating subscription plan: {plan_in.name}")
    # Optionally, interact with Stripe here to create a corresponding plan/price if stripe_price_id is not provided,
    # or validate if one is provided. For simplicity, this is assumed to be handled manually in Stripe dashboard for now
    # and the stripe_price_id is provided in plan_in.
    return sub_crud.create_subscription_plan(db, plan_in)

@router.put("/admin/plans/{plan_id}", response_model=sub_schemas.SubscriptionPlanDisplay)
def admin_update_subscription_plan(
    plan_id: int,
    plan_in: sub_schemas.SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin: Update an existing subscription plan.
    """
    logger.info(f"Admin {current_admin.email} updating subscription plan ID: {plan_id}")
    updated_plan = sub_crud.update_subscription_plan(db, plan_id, plan_in)
    if not updated_plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")
    return updated_plan

# --- Public Subscription Plan Listing ---
@router.get("/plans", response_model=List[sub_schemas.SubscriptionPlanDisplay])
def list_active_subscription_plans(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Public: Get a list of active subscription plans available for purchase.
    """
    plans = sub_crud.get_active_subscription_plans(db, skip=skip, limit=limit)
    return plans

# --- User Subscription Management Endpoints ---
@router.post("/create-payment-intent", response_model=pay_schemas.PaymentIntentResponse)
async def create_payment_intent_for_subscription(
    request_data: pay_schemas.PaymentIntentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated: Creates a PaymentIntent for a new subscription or a one-time payment.
    If plan_id is provided, it attempts to create/manage a Stripe subscription.
    Returns a client_secret for the frontend to confirm the payment with Stripe.js.
    """
    logger.info(f"User {current_user.email} requesting payment intent for plan_id: {request_data.plan_id}")

    if not request_data.plan_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_id is required.")

    plan = sub_crud.get_subscription_plan(db, request_data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active subscription plan not found.")
    if not plan.stripe_price_id:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="This plan is not configured for Stripe payments.")

    stripe_customer = stripe_service.get_or_create_stripe_customer(db, current_user)
    if not stripe_customer:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get or create Stripe customer.")

    # Check for existing active subscription to prevent duplicates (optional, depends on business logic)
    # active_sub = sub_crud.get_active_user_subscription(db, current_user.id)
    # if active_sub and active_sub.plan_id == plan.id:
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has an active subscription to this plan.")

    try:
        # Create Stripe Subscription (which might return a PaymentIntent if payment is needed)
        stripe_subscription, payment_intent = stripe_service.create_stripe_subscription(
            customer_id=stripe_customer.id,
            stripe_price_id=plan.stripe_price_id,
            metadata={
                "app_user_id": current_user.id,
                "app_plan_id": plan.id,
                "app_plan_name": plan.name
            },
            default_payment_method=request_data.payment_method_id # Optional, if client provides it
        )

        if not stripe_subscription:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create Stripe subscription.")

        # Create UserSubscription record in our DB (status might be PENDING_PAYMENT or INCOMPLETE)
        # The status and details will be updated further by webhooks.
        user_sub_status = SubscriptionStatus.PENDING_PAYMENT
        if stripe_subscription.status == 'active': # e.g. trial without immediate payment
            user_sub_status = SubscriptionStatus.ACTIVE
        elif stripe_subscription.status == 'trialing':
             user_sub_status = SubscriptionStatus.ACTIVE # Or a specific 'trialing' status if you add one
        elif stripe_subscription.status == 'incomplete':
             user_sub_status = SubscriptionStatus.INCOMPLETE

        # Create or update local UserSubscription record
        # It's important that this doesn't fail silently if Stripe succeeds.
        # Consider handling cases where local DB write fails after Stripe action.
        db_user_sub = sub_crud.get_user_subscription_by_stripe_id(db, stripe_subscription.id)
        if not db_user_sub:
            db_user_sub = sub_crud.create_user_subscription(
                db=db,
                user_id=current_user.id,
                plan_id=plan.id,
                status=user_sub_status,
                stripe_subscription_id=stripe_subscription.id,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start) if stripe_subscription.current_period_start else None,
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end) if stripe_subscription.current_period_end else None,
                cancel_at_period_end=stripe_subscription.cancel_at_period_end
            )
        else: # Update existing if found (e.g. retrying a failed payment for an existing sub attempt)
            db_user_sub = sub_crud.update_user_subscription_status(
                db=db, subscription_id=db_user_sub.id, status=user_sub_status,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start) if stripe_subscription.current_period_start else None,
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end) if stripe_subscription.current_period_end else None,
                cancel_at_period_end=stripe_subscription.cancel_at_period_end
            )


        client_secret_to_return = None
        pi_id_to_return = None
        if payment_intent:
            client_secret_to_return = payment_intent.client_secret
            pi_id_to_return = payment_intent.id
            # Create a preliminary payment record in PENDING status
            pay_crud.create_payment_record(db, pay_schemas.PaymentCreate(
                user_id=current_user.id,
                user_subscription_id=db_user_sub.id if db_user_sub else None,
                amount=Decimal(payment_intent.amount / 100), # Stripe amount is in cents
                currency=payment_intent.currency.upper(),
                status=PaymentStatus.PENDING,
                payment_gateway=PaymentGateway.STRIPE,
                payment_intent_id=payment_intent.id,
                transaction_id=payment_intent.latest_charge # If available immediately
            ))

        return pay_schemas.PaymentIntentResponse(
            client_secret=client_secret_to_return,
            payment_intent_id=pi_id_to_return,
            subscription_id=stripe_subscription.id,
            status=stripe_subscription.status
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during payment intent creation for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during payment intent creation for user {current_user.email}: {e}", exc_info=True)
        # Rollback DB changes if any part failed after Stripe interaction but before full commit
        # This is tricky if Stripe call succeeded. Compensating transactions might be needed.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")


@router.get("/my-active", response_model=Optional[sub_schemas.UserSubscriptionDisplay])
def get_my_active_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated: Gets the current user's active subscription details.
    """
    logger.info(f"Fetching active subscription for user {current_user.email}")
    active_sub = sub_crud.get_active_user_subscription(db, current_user.id)
    if not active_sub:
        # No active subscription found, return 200 with null or 404. Consistent 200 with null is often better for "current" state.
        return None
    return active_sub

@router.post("/cancel", response_model=sub_schemas.UserSubscriptionDisplay)
async def cancel_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated: Marks the user's current active Stripe subscription to cancel at the period end.
    """
    logger.info(f"User {current_user.email} requesting to cancel their active subscription.")
    active_sub = sub_crud.get_active_user_subscription(db, current_user.id)
    if not active_sub or not active_sub.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Stripe subscription found to cancel.")

    try:
        # Call Stripe to set cancel_at_period_end = True
        updated_stripe_sub = stripe_service.cancel_stripe_subscription(
            active_sub.stripe_subscription_id,
            at_period_end=True
        )
        if not updated_stripe_sub or not updated_stripe_sub.cancel_at_period_end:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update subscription on Stripe to cancel at period end.")

        # Update local UserSubscription record
        # The status might remain 'active' until Stripe sends 'customer.subscription.updated' or 'deleted' webhook
        # at the actual period end. For now, reflect the cancel_at_period_end flag.
        db_sub_updated = sub_crud.update_user_subscription_status(
            db=db,
            subscription_id=active_sub.id,
            status=active_sub.status, # Keep current status (likely ACTIVE)
            cancel_at_period_end=True,
            current_period_end=datetime.fromtimestamp(updated_stripe_sub.current_period_end) if updated_stripe_sub.current_period_end else active_sub.current_period_end
        )
        if not db_sub_updated: # Should not happen if active_sub was found
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update local subscription record after Stripe cancellation.")

        logger.info(f"Subscription {active_sub.stripe_subscription_id} for user {current_user.email} scheduled to cancel at period end.")
        return db_sub_updated

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during subscription cancellation for user {current_user.email}, sub_id {active_sub.stripe_subscription_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during subscription cancellation for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred during cancellation.")


# --- Payment History ---
@router.get("/payments/history", response_model=List[pay_schemas.PaymentDisplay])
def get_my_payment_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 10
):
    """
    Authenticated: Get the current user's payment history.
    """
    logger.info(f"Fetching payment history for user {current_user.email}")
    payments = pay_crud.get_payments_for_user(db, current_user.id, skip=skip, limit=limit)
    return payments

# --- Stripe Webhook Endpoint ---
@router.post("/webhooks/stripe", include_in_schema=False) # Exclude from OpenAPI docs
async def webhook_stripe(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"), # Stripe sends 'Stripe-Signature'
    db: Session = Depends(get_db) # Get DB session for CRUD operations
):
    """
    Webhook endpoint to receive events from Stripe.
    This handles events like successful payments, subscription updates, etc.
    """
    if not stripe_signature:
        logger.warning("Missing Stripe-Signature header in webhook.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header.")

    payload_bytes = await request.body()

    try:
        event = stripe_service.construct_stripe_webhook_event(payload_bytes, stripe_signature)
    except HTTPException as e: # Re-raise if construct_event raises HTTPException (e.g. bad secret)
        logger.error(f"Webhook event construction failed: {e.detail}")
        raise e

    if not event: # Should be handled by construct_stripe_webhook_event raising error
        logger.error("Stripe event construction returned None unexpectedly.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook event construction failed.")

    logger.info(f"Received Stripe webhook event: ID: {event.id}, Type: {event.type}")
    event_data_object = event.data.object # This is the Stripe object (e.g., Charge, Subscription, Invoice)

    # Handle different event types
    # See Stripe docs for event types: https://stripe.com/docs/api/events/types

    if event.type == "checkout.session.completed":
        # This is often used for one-time payments or initial setup of subscriptions.
        # If you use Stripe Checkout, this is a key event.
        # session = event_data_object
        # client_reference_id = session.get("client_reference_id") # Your internal user ID / order ID
        # stripe_customer_id = session.get("customer")
        # stripe_subscription_id = session.get("subscription") # If it was a subscription checkout
        # ... update your DB ...
        logger.info(f"Checkout session completed: {event.id}. Data: {event_data_object}")
        pass


    elif event.type == "invoice.payment_succeeded":
        invoice = event_data_object
        stripe_subscription_id = invoice.get("subscription")
        stripe_customer_id = invoice.get("customer")
        payment_intent_id = invoice.get("payment_intent")
        charge_id = invoice.get("charge") # This is the transaction_id for the payment
        amount_paid = invoice.get("amount_paid") # In cents
        currency = invoice.get("currency")
        paid_at_ts = invoice.get("status_transitions", {}).get("paid_at") # Timestamp
        paid_at_dt = datetime.fromtimestamp(paid_at_ts) if paid_at_ts else datetime.utcnow()

        logger.info(f"Invoice payment succeeded for Stripe Sub ID: {stripe_subscription_id}, PI_ID: {payment_intent_id}, Charge: {charge_id}")

        # Find associated UserSubscription
        db_user_sub = None
        if stripe_subscription_id:
            db_user_sub = sub_crud.get_user_subscription_by_stripe_id(db, stripe_subscription_id)

        user_id_for_payment = None
        if db_user_sub:
            user_id_for_payment = db_user_sub.user_id
        elif stripe_customer_id: # Fallback to find user by stripe_customer_id
            user_q = db.query(User).filter(User.stripe_customer_id == stripe_customer_id).first()
            if user_q: user_id_for_payment = user_q.id

        if not user_id_for_payment:
            logger.error(f"Cannot determine user for successful payment: Stripe Sub {stripe_subscription_id}, Stripe Cust {stripe_customer_id}")
            # Potentially raise error or handle as anonymous/unmatched payment
        else:
            # --- Payment Record Update/Create ---
            # Ensure we have a local Payment record for this successful transaction
            db_payment = pay_crud.get_payment_by_transaction_id(db, charge_id) # Assuming charge_id is unique transaction_id from Stripe
            if not db_payment and payment_intent_id: # Fallback to PI ID if charge_id wasn't initially stored or if it's preferred
                db_payment = pay_crud.get_payment_by_payment_intent_id(db, payment_intent_id)

            if db_payment: # Update existing payment record
                pay_crud.update_payment_status(
                    db,
                    payment_id_internal=db_payment.id,
                    new_status=PaymentStatus.SUCCEEDED,
                    paid_at=paid_at_dt,
                    invoice_url=invoice.get("hosted_invoice_url"),
                    receipt_url=stripe.Charge.retrieve(charge_id).receipt_url if charge_id else None,
                    transaction_id=charge_id # Ensure transaction_id is set
                )
            else: # Create new payment record if none found (should ideally exist from PI creation)
                payment_create_data = pay_schemas.PaymentCreate(
                    user_id=user_id_for_payment,
                    user_subscription_id=db_user_sub.id if db_user_sub else None,
                    amount=Decimal(amount_paid / 100) if amount_paid is not None else Decimal(0),
                    currency=currency.upper() if currency else "USD",
                    status=PaymentStatus.SUCCEEDED, # Directly succeeded
                    payment_gateway=PaymentGateway.STRIPE,
                    transaction_id=charge_id,
                    payment_intent_id=payment_intent_id,
                    invoice_url=invoice.get("hosted_invoice_url"),
                    receipt_url=stripe.Charge.retrieve(charge_id).receipt_url if charge_id else None,
                    paid_at=paid_at_dt
                )
                db_payment = pay_crud.create_payment_record(db, payment_create_data)

            logger.info(f"Payment record {'updated' if db_payment else 'created'} (ID: {db_payment.id if db_payment else 'N/A'}) for user {user_id_for_payment}.")

            # --- Commission Calculation ---
            # Check if this payment should trigger commissions
            # This should typically be for first payments of a subscription, or specific product purchases.
            # For simplicity, let's assume any successful subscription-related payment triggers commission for now.
            # More complex logic would check if it's the first payment, type of plan, etc.

            paying_user = user_crud.get_user_by_id(db, user_id_for_payment)
            if paying_user and db_payment: # Ensure paying_user and payment record exist
                COMMISSION_RATE_L1 = Decimal(os.getenv("COMMISSION_RATE_L1", "0.10")) # 10%
                COMMISSION_RATE_L2 = Decimal(os.getenv("COMMISSION_RATE_L2", "0.05")) # 5%
                COMMISSION_RATE_L3 = Decimal(os.getenv("COMMISSION_RATE_L3", "0.02")) # 2%

                upline_users_and_rates = [
                    (paying_user.upline_l1_id, COMMISSION_RATE_L1, 1),
                    (paying_user.upline_l2_id, COMMISSION_RATE_L2, 2),
                    (paying_user.upline_l3_id, COMMISSION_RATE_L3, 3),
                ]

                for upline_user_id, rate, level in upline_users_and_rates:
                    if upline_user_id:
                        commission_amount = db_payment.amount * rate
                        earning_create_data = ref_schemas.ReferralEarningCreate(
                            user_id=upline_user_id, # The user earning the commission
                            referred_user_id=paying_user.id, # The user whose payment generated it
                            source_payment_id=db_payment.id,
                            commission_amount=commission_amount,
                            commission_rate=rate,
                            referral_level=level,
                            status=ReferralCommissionStatus.PENDING # Default status
                        )
                        ref_crud.create_referral_earning(db, earning_create_data)
                        logger.info(f"Created PENDING referral earning of {commission_amount} for user {upline_user_id} (L{level}) from payment {db_payment.id}")
            else:
                logger.warning(f"Could not process commissions: Paying user (ID {user_id_for_payment}) or payment record not found/created.")


            # Update or create Payment record (Original position of this block)
            # payment_create_data = pay_schemas.PaymentCreate(
            #     user_id=user_id_for_payment,
            #     user_subscription_id=db_user_sub.id if db_user_sub else None,
                amount=Decimal(amount_paid / 100) if amount_paid is not None else Decimal(0),
                # currency=currency.upper() if currency else "USD",
                # status=PaymentStatus.SUCCEEDED,
                # payment_gateway=PaymentGateway.STRIPE,
                # transaction_id=charge_id,
                # payment_intent_id=payment_intent_id,
                # invoice_url=invoice.get("hosted_invoice_url"),
                # paid_at=paid_at_dt
            #)
            #pay_crud.update_payment_status(
                #db,
                #payment_intent_id_stripe=payment_intent_id, # Primary key for update
                #transaction_id_gateway=charge_id, # Secondary key
                #new_status=PaymentStatus.SUCCEEDED,
                #paid_at=paid_at_dt,
                #invoice_url=invoice.get("hosted_invoice_url"),
                #receipt_url=stripe.Charge.retrieve(charge_id).receipt_url if charge_id else None, # Example to get receipt_url
                #create_if_not_exists=True,
                #payment_data_for_create=payment_create_data
            #)

        # If it's for a subscription, ensure the subscription is marked active and period updated
        if db_user_sub and stripe_subscription_id: # Ensure db_user_sub is not None
            # Stripe sends 'customer.subscription.updated' for period changes.
            # However, confirming active status here is also good.
            sub_crud.update_user_subscription_status(
                db,
                subscription_id=db_user_sub.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=datetime.fromtimestamp(invoice.period_start) if invoice.period_start else None,
                current_period_end=datetime.fromtimestamp(invoice.period_end) if invoice.period_end else None,
                cancel_at_period_end=db_user_sub.cancel_at_period_end # Keep existing flag
            )
            logger.info(f"UserSubscription ID {db_user_sub.id} confirmed active due to invoice payment.")

            # Send email for subscription activation/course unlocked
            if paying_user and db_user_sub and db_user_sub.plan:
                # Determine if this is a new activation or a renewal.
                # This logic could be more sophisticated. For now, send on any payment success for a subscription.
                email_context = {
                    "user_name": paying_user.email, # Or a display name
                    "plan_name": db_user_sub.plan.name,
                    # If the plan unlocks specific courses or all courses, that logic would be here.
                    # For now, a generic "access to your plan benefits"
                    # "course_title": "All Courses" # Example if plan gives access to everything
                }
                email_service.send_templated_email(
                    to_email=paying_user.email,
                    subject=f"Your {db_user_sub.plan.name} Subscription is Active!",
                    html_template_name="new_course_unlocked.html", # Reusing this template for "subscription active"
                    context=email_context
                )
                logger.info(f"Subscription active email sent to {paying_user.email} for plan {db_user_sub.plan.name}")


    elif event.type == "invoice.payment_failed":
        invoice = event_data_object
        stripe_subscription_id = invoice.get("subscription")
        payment_intent_id = invoice.get("payment_intent")
        charge_id = invoice.get("charge")
        error_msg = invoice.get("last_payment_error", {}).get("message") if invoice.get("last_payment_error") else "Payment failed"

        logger.warning(f"Invoice payment failed for Stripe Sub ID: {stripe_subscription_id}, PI_ID: {payment_intent_id}. Error: {error_msg}")

        # Update Payment record to FAILED
        pay_crud.update_payment_status(
            db,
            payment_intent_id_stripe=payment_intent_id,
            transaction_id_gateway=charge_id,
            new_status=PaymentStatus.FAILED,
            error_message=error_msg
        )

        # Update UserSubscription status (e.g., to PENDING_PAYMENT or EXPIRED if grace period ends)
        if stripe_subscription_id:
            db_user_sub = sub_crud.get_user_subscription_by_stripe_id(db, stripe_subscription_id)
            if db_user_sub:
                sub_crud.update_user_subscription_status(db, db_user_sub.id, SubscriptionStatus.PENDING_PAYMENT) # Or specific status based on Stripe's dunning
                logger.info(f"UserSubscription ID {db_user_sub.id} status updated due to payment failure.")


    elif event.type == "customer.subscription.updated":
        stripe_sub_obj = event_data_object # This is a Stripe Subscription object
        db_user_sub = sub_crud.get_user_subscription_by_stripe_id(db, stripe_sub_obj.id)
        if not db_user_sub:
            logger.warning(f"Received customer.subscription.updated for unknown Stripe Sub ID {stripe_sub_obj.id}. Ignoring or create new local sub?")
            # Potentially create if it's a new subscription not caught by PI flow:
            # plan = sub_crud.get_subscription_plan_by_stripe_id(db, stripe_sub_obj.items.data[0].price.id)
            # user = user_crud.get_user_by_stripe_customer_id(db, stripe_sub_obj.customer)
            # ... then create UserSubscription ...
        else:
            new_local_status = SubscriptionStatus.ACTIVE # Default
            if stripe_sub_obj.status == 'active': new_local_status = SubscriptionStatus.ACTIVE
            elif stripe_sub_obj.status == 'trialing': new_local_status = SubscriptionStatus.ACTIVE # Or specific 'trialing'
            elif stripe_sub_obj.status == 'past_due': new_local_status = SubscriptionStatus.PENDING_PAYMENT
            elif stripe_sub_obj.status == 'canceled': new_local_status = SubscriptionStatus.CANCELED
            elif stripe_sub_obj.status == 'unpaid': new_local_status = SubscriptionStatus.PENDING_PAYMENT # Or EXPIRED
            elif stripe_sub_obj.status == 'incomplete': new_local_status = SubscriptionStatus.INCOMPLETE
            elif stripe_sub_obj.status == 'incomplete_expired': new_local_status = SubscriptionStatus.EXPIRED

            logger.info(f"Updating local UserSubscription {db_user_sub.id} based on Stripe sub {stripe_sub_obj.id} status {stripe_sub_obj.status} (local: {new_local_status})")
            sub_crud.update_user_subscription_status(
                db,
                subscription_id=db_user_sub.id,
                status=new_local_status,
                current_period_start=datetime.fromtimestamp(stripe_sub_obj.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_sub_obj.current_period_end),
                cancel_at_period_end=stripe_sub_obj.cancel_at_period_end
            )

    elif event.type == "customer.subscription.deleted": # Different from 'canceled' at period end
        stripe_sub_obj = event_data_object
        logger.info(f"Stripe Subscription {stripe_sub_obj.id} deleted (usually means fully ended/expired or immediate cancel).")
        # Update local subscription to CANCELED or EXPIRED
        db_sub = sub_crud.get_user_subscription_by_stripe_id(db, stripe_sub_obj.id)
        if db_sub:
            sub_crud.update_user_subscription_status(db, db_sub.id, SubscriptionStatus.EXPIRED, end_date=datetime.utcnow())
            logger.info(f"Local UserSubscription {db_sub.id} marked as EXPIRED due to Stripe deletion.")

    # Add more event handlers as needed:
    # - charge.refunded -> update Payment status
    # - customer.subscription.trial_will_end -> send reminder email
    # - etc.

    else:
        logger.info(f"Unhandled Stripe event type: {event.type}")

    return {"status": "success", "event_id": event.id, "event_type": event.type}
