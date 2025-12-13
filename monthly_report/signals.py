from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps

from .integrations.inventory_hooks import on_inventory_snapshot_saved
from .models import MonthlyReport, CounterChangeLog


@receiver(post_save, sender=None)
def page_counter_saved_handler(sender, instance, created, **kwargs):
    """
    Обработчик сигнала для модели PageCounter из inventory приложения
    """
    # Проверяем, что это именно модель PageCounter из inventory
    if (hasattr(instance, '_meta') and
            instance._meta.app_label == 'inventory' and
            instance._meta.model_name == 'pagecounter' and
            created):  # только для новых записей

        on_inventory_snapshot_saved(sender, instance, created, **kwargs)


def connect_signals():
    """
    Подключаем сигналы к моделям inventory
    """
    try:
        PageCounter = apps.get_model('inventory', 'PageCounter')
        post_save.connect(
            page_counter_saved_handler,
            sender=PageCounter,
            dispatch_uid='monthly_report_page_counter_sync'
        )
    except LookupError:
        # inventory приложение не найдено
        pass


# Инвалидация кэша метрик месяца при изменении данных
@receiver(post_save, sender=MonthlyReport)
@receiver(post_delete, sender=MonthlyReport)
def invalidate_metrics_on_report_change(sender, instance, **kwargs):
    """
    Инвалидирует кэш метрик месяца при изменении/удалении записи отчета
    """
    from .views import invalidate_month_metrics_cache
    if instance.month:
        invalidate_month_metrics_cache(instance.month)


@receiver(post_save, sender=CounterChangeLog)
@receiver(post_delete, sender=CounterChangeLog)
def invalidate_metrics_on_changelog(sender, instance, **kwargs):
    """
    Инвалидирует кэш метрик месяца при изменении истории изменений
    (влияет на количество уникальных пользователей)
    """
    from .views import invalidate_month_metrics_cache
    if instance.monthly_report and instance.monthly_report.month:
        invalidate_month_metrics_cache(instance.monthly_report.month)