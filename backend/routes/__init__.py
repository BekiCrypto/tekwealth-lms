# This file makes the 'routes' directory a Python package.

from fastapi import APIRouter

from .auth_routes import router as auth_router
from .course_routes import router as course_router
from .learning_routes import router as learning_router
from .subscription_routes import router as subscription_router
from .referral_routes import router as referral_router
from .ai_routes import router as ai_router
from .admin_routes import router as admin_router # Added admin_router

# You can create a main API router that includes all other routers
# This is useful for organizing your API, e.g., under a /api/v1 prefix

api_router_v1 = APIRouter(prefix="/api/v1")

# User-facing routes
api_router_v1.include_router(auth_router)
api_router_v1.include_router(course_router)
api_router_v1.include_router(learning_router)
api_router_v1.include_router(subscription_router)
api_router_v1.include_router(referral_router)
api_router_v1.include_router(ai_router)

# Admin routes - these are already prefixed with /admin in admin_routes.py
# So, if api_router_v1 is /api/v1, admin routes will be /api/v1/admin/...
api_router_v1.include_router(admin_router)


# api_router_v1.include_router(payment_router) # If you create a separate payment_router for non-subscription payments

__all__ = [
    "api_router_v1" # Export the main router
]
