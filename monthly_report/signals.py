from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

from .integrations.inventory_hooks import on_inventory_snapshot_saved


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