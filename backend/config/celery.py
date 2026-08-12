import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("cinematch")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(name="cinematch.ping")
def ping() -> str:
    """Lightweight task used to verify the Celery app is wired correctly."""
    return "pong"
