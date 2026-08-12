from django.urls import path

from apps.common.views import LivenessView

urlpatterns = [
    path("", LivenessView.as_view(), name="health"),
]
