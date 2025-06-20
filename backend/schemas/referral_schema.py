from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from backend.models.enums import ReferralCommissionStatus
# To avoid circular imports with user_schema, use ForwardRef if necessary,
# or ensure user_schema.UserDisplay is simple enough or defined first.
# For now, we'll use a simplified UserInReferralDisplay for nested user details.

# Simplified User Display for nesting within referral schemas to avoid circular dependencies
class UserInReferralDisplay(BaseModel):
    id: int
    email: EmailStr
    # Add other fields like name if available and needed

    class Config:
        from_attributes = True

# --- ReferralEarning Schemas ---
class ReferralEarningBase(BaseModel):
    commission_amount: Decimal = Field(..., description="Amount of commission earned")
    commission_rate: Decimal = Field(..., description="Commission rate applied (e.g., 0.10 for 10%)")
    referral_level: int = Field(..., ge=1, le=3, description="Level of referral (1, 2, or 3)")
    status: ReferralCommissionStatus = Field(default=ReferralCommissionStatus.PENDING, description="Status of the commission")
    notes: Optional[str] = Field(None, max_length=1000, description="Admin notes regarding this earning")

class ReferralEarningCreate(ReferralEarningBase):
    user_id: int # The user who earned this
    referred_user_id: int # The user whose action generated this
    source_payment_id: int # The payment that triggered this

class ReferralEarningUpdate(BaseModel): # For admin actions
    status: Optional[ReferralCommissionStatus] = None
    notes: Optional[str] = Field(None, max_length=1000, nullable=True) # Allow setting notes to null

class ReferralEarningDisplay(ReferralEarningBase):
    id: int
    user: UserInReferralDisplay = Field(..., description="User who earned the commission") # Earning User
    referred_user: Optional[UserInReferralDisplay] = Field(None, description="User whose purchase generated the commission") # Referred User (source)
    source_payment_id: Optional[int] = Field(None, description="ID of the payment that triggered this commission")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        # Example resolver if 'user' and 'referred_user' are from different fields in model
        # This requires that the model instance passed to this schema has 'earning_user' and 'referred_user_obj' attributes.
        # Pydantic v2 uses model_validator or field_validator. For from_attributes, direct mapping is assumed.
        # If your model has `earning_user` and `referred_user_obj` attributes that are User models:
        # This should work automatically if the relationship names match.
        # If not, you might need something like:
        # @validator('user', pre=True, always=True)
        # def set_user(cls, v, values): return values.get('earning_user')
        # @validator('referred_user', pre=True, always=True)
        # def set_referred_user(cls, v, values): return values.get('referred_user_obj')


# --- Downline Schemas ---
class DownlineUserNode(BaseModel):
    user_id: int
    email: EmailStr
    referral_code: Optional[str] = None
    level: int # Level relative to the user querying their downline (1, 2, 3)
    # children: List['DownlineUserNode'] = [] # For deeply nested tree (can be complex and performance heavy)
    # For simplicity, API might return a flat list with level indicators, or limited depth nesting.
    # For now, this schema represents a node, actual tree structure will be built by service/route if needed.

    # If direct upline info is useful on this node:
    upline_l1_email: Optional[EmailStr] = None # Email of their direct referrer

    class Config:
        from_attributes = True

# DownlineUserNode.update_forward_refs() # For Pydantic v1 if using string 'DownlineUserNode' in List

# --- Referral Stats Schema ---
class ReferralStats(BaseModel):
    total_direct_referrals: int = Field(0, description="Total number of users directly referred (L1)")
    total_l1_referrals: int = Field(0, description="Alias for total_direct_referrals")
    total_l2_referrals: int = Field(0, description="Total number of users referred by L1 downline")
    total_l3_referrals: int = Field(0, description="Total number of users referred by L2 downline")

    pending_commission_total: Decimal = Field(Decimal("0.00"), description="Total amount of pending commission")
    approved_commission_total: Decimal = Field(Decimal("0.00"), description="Total amount of approved (unpaid) commission")
    paid_commission_total: Decimal = Field(Decimal("0.00"), description="Total amount of commission already paid out")
    lifetime_commission_total: Decimal = Field(Decimal("0.00"), description="Total commission earned (pending + approved + paid)")

# For displaying user's own referral code and link
class MyReferralInfo(BaseModel):
    referral_code: str
    referral_link: HttpUrl # Example: "https://yourapp.com/register?ref=YOURCODE"
    # user_details: UserDisplay # Could include full UserDisplay if needed, but referral_code is often prime info.
    # For now, keep it simple. The route can return UserDisplay separately or combine.
