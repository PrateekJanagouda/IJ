from django.apps import AppConfig


class OutboxConfig(AppConfig):
    name = "apps.outbox"
    default_auto_field = "django.db.models.BigAutoField"
