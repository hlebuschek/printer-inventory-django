from django.apps import AppConfig


class MonthlyReportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monthly_report'
    verbose_name = 'Ежемесячные отчеты'

    def ready(self):
        # Регистрируем сигналы при инициализации приложения
        try:
            from . import signals
            signals.connect_signals()
        except ImportError:
            pass
