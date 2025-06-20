from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, TIMESTAMP, DECIMAL,
    Enum as SAEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.enums import ReferralCommissionStatus # Import the new enum

class ReferralEarning(Base):
    __tablename__ = "referral_earnings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True) # The user who earned the commission
    referred_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True) # The user whose action generated the commission (e.g., their first payment)
                                                                                                    # SET NULL if the referred user is deleted, but earning record is kept.
    source_payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True) # The payment that triggered this commission. SET NULL if payment deleted.

    commission_amount = Column(DECIMAL(10, 2), nullable=False) # e.g., 2.99
    commission_rate = Column(DECIMAL(5, 4), nullable=False)   # e.g., 0.1000 for 10.00%
    referral_level = Column(Integer, nullable=False, index=True) # 1, 2, or 3, indicating the level of referral

    status = Column(SAEnum(ReferralCommissionStatus, name="referral_commission_status_enum", values_callable=lambda obj: [e.value for e in obj]),
                    nullable=False, default=ReferralCommissionStatus.PENDING, index=True)

    notes = Column(Text, nullable=True) # For admin notes, e.g., reason for rejection or manual adjustment

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    earning_user = relationship("User", foreign_keys=[user_id], back_populates="referral_earnings")
    # The user object who was referred and triggered this commission
    referred_user_obj = relationship("User", foreign_keys=[referred_user_id])
    # The payment object that was the source of this commission
    source_payment_obj = relationship("Payment", foreign_keys=[source_payment_id])

    __table_args__ = (
        Index("idx_user_level_status", "user_id", "referral_level", "status"),
    )

    def __repr__(self):
        return (f"<ReferralEarning(id={self.id}, user_id={self.user_id}, referred_user_id={self.referred_user_id}, "
                f"amount={self.commission_amount}, level={self.referral_level}, status='{self.status}')>")
