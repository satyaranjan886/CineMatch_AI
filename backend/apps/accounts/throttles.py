from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRegisterThrottle(AnonRateThrottle):
    scope = "auth_register"


class AuthLoginThrottle(AnonRateThrottle):
    scope = "auth_login"


class AuthRefreshThrottle(AnonRateThrottle):
    scope = "auth_refresh"


class ProfileUpdateThrottle(UserRateThrottle):
    scope = "profile_update"


class SearchThrottle(AnonRateThrottle):
    scope = "search"


class InteractionThrottle(UserRateThrottle):
    scope = "interactions"
