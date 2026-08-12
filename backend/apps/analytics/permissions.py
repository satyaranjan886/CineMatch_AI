"""Staff-only access for analytics endpoints."""

from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Require an authenticated staff user. Unauthenticated callers get 401."""

    message = "Staff access required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_staff)
