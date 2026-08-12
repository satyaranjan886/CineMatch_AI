from django.urls import path

from apps.analytics.views import AnalyticsDashboardView, AnalyticsRefreshView

urlpatterns = [
    path("analytics/dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    path("analytics/refresh/", AnalyticsRefreshView.as_view(), name="analytics-refresh"),
]
