from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.cookies import (
    clear_refresh_cookie,
    get_refresh_token_from_request,
    set_refresh_cookie,
)
from apps.accounts.serializers import (
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    MeSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserPreferenceSerializer,
    build_token_response,
)
from apps.accounts.throttles import (
    AuthLoginThrottle,
    AuthRefreshThrottle,
    AuthRegisterThrottle,
    ProfileUpdateThrottle,
)


def _attach_refresh_cookie(response: Response, refresh: str | None) -> Response:
    if refresh:
        set_refresh_cookie(response, refresh)
    return response


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRegisterThrottle]

    @extend_schema(request=RegisterSerializer, responses={201: dict})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        payload, refresh = build_token_response(user)
        response = Response(payload, status=status.HTTP_201_CREATED)
        return _attach_refresh_cookie(response, refresh)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]
    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh = response.data.pop("refresh", None)
            _attach_refresh_cookie(response, refresh)
        return response


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRefreshThrottle]

    def post(self, request, *args, **kwargs):
        refresh = get_refresh_token_from_request(request)
        if not refresh:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        data = dict(serializer.validated_data)
        new_refresh = data.pop("refresh", None) or refresh
        response = Response(data, status=status.HTTP_200_OK)
        return _attach_refresh_cookie(response, new_refresh)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProfileUpdateThrottle]

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request):
        refresh = get_refresh_token_from_request(request)
        serializer = LogoutSerializer(data={"refresh": refresh} if refresh else {})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except (TokenError, InvalidToken):
            response = Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
            clear_refresh_cookie(response)
            return response
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProfileUpdateThrottle]

    @extend_schema(responses={200: ProfileSerializer})
    def get(self, request):
        profile = request.user.get_primary_profile()
        if profile is None:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfileSerializer(profile).data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: ProfileUpdateSerializer})
    def patch(self, request):
        profile = request.user.get_primary_profile()
        if profile is None:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(profile).data)


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProfileUpdateThrottle]

    def _get_preferences(self, user):
        preferences = getattr(user, "preferences", None)
        if preferences is None:
            return None
        return preferences

    @extend_schema(responses={200: UserPreferenceSerializer})
    def get(self, request):
        preferences = self._get_preferences(request.user)
        if preferences is None:
            return Response({"detail": "Preferences not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserPreferenceSerializer(preferences).data)

    @extend_schema(request=UserPreferenceSerializer, responses={200: UserPreferenceSerializer})
    def patch(self, request):
        preferences = self._get_preferences(request.user)
        if preferences is None:
            return Response({"detail": "Preferences not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPreferenceSerializer(preferences).data)
