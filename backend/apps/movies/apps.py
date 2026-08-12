from django.apps import AppConfig


class MoviesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.movies"
    label = "movies"
    verbose_name = "Movies"

    def ready(self) -> None:
        from apps.movies import signals  # noqa: F401
