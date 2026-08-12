from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    label = "common"
    verbose_name = "Common"

    def ready(self) -> None:
        from apps.common.observability.celery_signals import connect_celery_signals
        from apps.common.observability.metrics import ensure_metrics

        ensure_metrics()
        connect_celery_signals()
