from django.apps import AppConfig

class MonthlyReportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monthly_report'

    def ready(self):
        # noqa: F401 — важно просто импортировать, чтобы зарегистрировать ресиверы
        from . import signals  # pylint: disable=unused-import

