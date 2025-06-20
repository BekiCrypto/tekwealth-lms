from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, TIMESTAMP, DECIMAL,
    Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.enums import PaymentStatus, PaymentGateway

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True) # User might be deleted, but payment record kept

    # Link to a subscription if this payment is for one.
    # Nullable if it's a one-time purchase not tied to a recurring UserSubscription entry.
    user_subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)

    amount = Column(DECIMAL(10, 2), nullable=False) # e.g., 29.99
    currency = Column(String(10), nullable=False, default="USD")

    status = Column(SAEnum(PaymentStatus, name="payment_status_enum", values_callable=lambda obj: [e.value for e in obj]),
                    nullable=False, default=PaymentStatus.PENDING, index=True)

    payment_gateway = Column(SAEnum(PaymentGateway, name="payment_gateway_enum", values_callable=lambda obj: [e.value for e in obj]),
                             nullable=False, index=True)

    # Gateway specific identifiers
    transaction_id = Column(String(255), nullable=True, unique=True, index=True) # From payment gateway (e.g., Stripe charge ID: ch_xxxx)
    payment_intent_id = Column(String(255), nullable=True, unique=True, index=True) # For Stripe PaymentIntents: pi_xxxx
    # For Chapa: transaction_reference or tx_ref
    # For Telebirr: trade_out_no or similar

    invoice_url = Column(String(500), nullable=True) # Link to invoice PDF from gateway, if available
    receipt_url = Column(String(500), nullable=True) # Link to receipt from gateway, if available

    error_message = Column(Text, nullable=True) # If payment failed, store gateway error message

    paid_at = Column(TIMESTAMP(timezone=True), nullable=True) # Timestamp when payment was confirmed as succeeded

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="payments")
    user_subscription = relationship("UserSubscription", back_populates="payments") # The subscription this payment is for

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount} {self.currency}, status='{self.status}')>"
