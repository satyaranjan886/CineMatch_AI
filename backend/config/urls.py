from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import LivenessView, MetricsView, ReadinessView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", LivenessView.as_view(), name="health-root"),
    path("ready/", ReadinessView.as_view(), name="ready-root"),
    path("metrics/", MetricsView.as_view(), name="metrics-root"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("config.api_urls")),
]
