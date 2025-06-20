from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# Schema for data received when a user registers (client-side with Firebase)
# The backend receives an ID token, but these are the core fields.
class UserBase(BaseModel):
    email: EmailStr
    role: Optional[str] = 'Subscriber'

# Schema for creating a user in our database AFTER Firebase authentication
# It will use firebase_uid obtained from the Firebase ID token.
class UserCreateInternal(UserBase):
    firebase_uid: str
    referral_code: Optional[str] = None
    referred_by_id: Optional[int] = None

# Schema for displaying user information (sending data back to client)
class UserDisplay(UserBase):
    id: int
    firebase_uid: str
    referral_code: Optional[str] = Field(None, description="User's unique referral code")
    # For admin/debug purposes, not typically for general user display unless privacy allows:
    referred_by_id: Optional[int] = Field(None, description="ID of the user who referred this user")
    upline_l1_id: Optional[int] = Field(None, description="ID of the L1 upline (direct referrer)")
    upline_l2_id: Optional[int] = Field(None, description="ID of the L2 upline")
    upline_l3_id: Optional[int] = Field(None, description="ID of the L3 upline")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe Customer ID for payments") # Added for completeness
    created_at: datetime
    updated_at: datetime

    class Config:
        # orm_mode = True # Pydantic V1 way
        from_attributes = True # Pydantic V2 way

# Schema representing the data decoded from a Firebase ID token
class TokenData(BaseModel):
    firebase_uid: str # Typically 'sub' or 'user_id' field in Firebase token payload
    email: EmailStr
    # You might get other claims like 'email_verified', 'name', etc.
    # Add them here if needed for your application logic.
    # For now, role is managed by our DB, not directly from Firebase token claims by default.


# Schema for the request body the client sends to our /register endpoint
# It contains the Firebase ID token.
class UserRegisterRequest(BaseModel):
    firebase_id_token: str
    referral_code_used: Optional[str] = None # Optional: if the user signed up using a referral code


# Schema for the request body the client sends to our /login endpoint
# It also contains the Firebase ID token.
class UserLoginRequest(BaseModel):
    firebase_id_token: str

# Schema for what the /register and /login endpoints might return (besides UserDisplay)
class AuthResponse(BaseModel):
    message: str
    user: Optional[UserDisplay] = None
    # access_token: Optional[str] = None # If generating an additional backend token
    # token_type: Optional[str] = "bearer" # If generating an additional backend token

# Schema for user profile updates (example, can be expanded)
class UserUpdate(BaseModel):
    # Add fields that a user can update, e.g., display name, profile picture URL
    # For now, keeping it simple. Role changes would typically be admin functionality.
    pass


# --- Admin Specific Schemas ---
class AdminUserUpdate(BaseModel):
    """Schema for data an Admin can update on a user."""
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, description="Update user role (e.g., Subscriber, Admin, MLM Partner)")
    # is_active: Optional[bool] = None # If you add an is_active field to User model
    # Add other fields an admin might change, e.g., lock account, verify email manually
    # Be cautious about allowing admins to change firebase_uid or referral codes directly.
    # stripe_customer_id might be updatable if there's a specific admin workflow for it.


# To avoid circular dependencies with other schemas, import them carefully or use ForwardRefs
# For UserDetailAdminDisplay, we need schemas from other modules.
from typing import List, TYPE_CHECKING
if TYPE_CHECKING:
    from .subscription_schema import UserSubscriptionDisplay
    from .payment_schema import PaymentDisplay
    from .referral_schema import ReferralStats
    from .user_progress_schema import UserProgressDisplay # Or a summary schema

class UserCourseProgressSummary(BaseModel): # A simplified summary for admin display
    course_id: int
    course_title: str
    completion_percentage: float
    # last_accessed_at: Optional[datetime] # Could be too much detail for admin list

class UserDetailAdminDisplay(UserDisplay):
    """Detailed user display for Admin panel."""
    # Inherits all fields from UserDisplay

    active_subscription: Optional['UserSubscriptionDisplay'] = Field(None, description="User's current active subscription")
    payment_history_summary: Optional[List['PaymentDisplay']] = Field(None, description="Summary of recent payments (e.g., last 5)") # Can be paginated via separate endpoint
    referral_stats: Optional['ReferralStats'] = Field(None, description="User's referral statistics")
    course_progress_summary: Optional[List[UserCourseProgressSummary]] = Field(None, description="Summary of user's progress in enrolled courses")
    # Add other detailed fields as needed by Admin

    # This is for Pydantic v1 style forward ref resolution if UserSubscriptionDisplay etc. are strings
    # class Config:
    #     # This is already in UserDisplay from which this inherits
    #     # from_attributes = True
    #     pass

# Pydantic v2 handles ForwardRefs more automatically if the type hints are strings
# and the actual types are available in the scope when models are fully defined/used.
# If direct imports are used above (guarded by TYPE_CHECKING), Pydantic v2 should resolve them.
# For Pydantic v1, you might need:
# UserDetailAdminDisplay.update_forward_refs() # Call this after all schemas are defined (e.g. in schemas/__init__.py)
