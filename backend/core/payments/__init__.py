# This package will contain payment gateway specific services.

from . import stripe_service

__all__ = [
    "stripe_service",
]
