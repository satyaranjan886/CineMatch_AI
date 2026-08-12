from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.permissions import IsStaffUser
from apps.analytics.serializers import AnalyticsDashboardSerializer
from apps.analytics.services.aggregation import compute_daily_snapshot, get_dashboard_payload


class AnalyticsDashboardView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="days",
                description="Number of daily snapshot points for timeseries",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="refresh",
                description="If true, recompute today's snapshot before returning",
                required=False,
                type=bool,
            ),
        ],
        responses={200: AnalyticsDashboardSerializer},
    )
    def get(self, request):
        days = min(max(int(request.query_params.get("days", 14)), 1), 90)
        refresh = str(request.query_params.get("refresh", "")).lower() in {"1", "true", "yes"}
        if refresh:
            compute_daily_snapshot()
        payload = get_dashboard_payload(days=days)
        return Response(payload)


class AnalyticsRefreshView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: dict})
    def post(self, request):
        snapshot = compute_daily_snapshot()
        return Response(
            {
                "date": snapshot.date.isoformat(),
                "computed_at": snapshot.computed_at.isoformat(),
                "status": "ok",
            }
        )
