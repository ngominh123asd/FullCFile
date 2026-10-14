"""
FileForge Backend - Guest User helper
For unauthenticated access, use a shared guest user
"""
from app.core.security import get_current_user as _get_current_user
from fastapi import Depends


async def get_guest_or_user(current_user: dict = Depends(_get_current_user)) -> dict:
    """Get current user or guest user"""
    if current_user:
        return current_user
    return {
        "user_id": "00000000-0000-0000-0000-000000000001",  # Guest user UUID
        "email": "guest@fileforge.local",
        "tier": "guest",
    }
