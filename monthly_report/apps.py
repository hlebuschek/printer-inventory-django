# monthly_report/apps.py
from django.apps import AppConfig, apps
from django.db.models.signals import post_save

class MonthlyReportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monthly_report"
    verbose_name = "Ежемесячные отчёты"

    def ready(self):
        # 1) Подцепить локальные сигналы (если есть файл monthly_report/signals.py)
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass  # необязательно

        # 2) Подписаться на post_save снапшота из inventory (если модель существует)
        try:
            Snapshot = apps.get_model("inventory", "CounterSnapshot")  # поправь имя модели при необходимости
        except LookupError:
            Snapshot = None

        if Snapshot:
            from .integrations.inventory_hooks import on_inventory_snapshot_saved
            post_save.connect(
                on_inventory_snapshot_saved,
                sender=Snapshot,
                dispatch_uid="monthly_report_auto_sync_on_inventory_change",
            )
