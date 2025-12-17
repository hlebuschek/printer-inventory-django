"""
Celery задачи для приложения contracts.
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_link_devices_task(self):
    """
    Автоматическое связывание устройств contracts с принтерами inventory по серийным номерам.

    Запускается периодически (раз в день) для синхронизации данных между приложениями.
    Обрабатывает только несвязанные устройства.
    """
    from contracts.services_linking import link_all_unlinked_devices

    logger.info("=" * 80)
    logger.info("ЗАПУСК АВТОМАТИЧЕСКОГО СВЯЗЫВАНИЯ УСТРОЙСТВ")
    logger.info(f"Task ID: {self.request.id}")
    logger.info(f"Timestamp: {timezone.now()}")
    logger.info("=" * 80)

    try:
        # Связываем все несвязанные устройства
        stats = link_all_unlinked_devices()

        logger.info("=" * 80)
        logger.info("АВТОМАТИЧЕСКОЕ СВЯЗЫВАНИЕ ЗАВЕРШЕНО")
        logger.info(f"Всего обработано: {stats['total_devices']}")
        logger.info(f"Успешно связано: {stats['linked']}")
        logger.info(f"Принтер не найден: {stats['not_found']}")
        logger.info(f"Найдено несколько принтеров: {stats['multiple_found']}")
        logger.info(f"Конфликты: {stats['conflicts']}")
        logger.info(f"Ошибки: {stats['errors']}")
        logger.info("=" * 80)

        return {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            **stats
        }

    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА В ЗАДАЧЕ СВЯЗЫВАНИЯ: {exc}", exc_info=True)
        logger.error("=" * 80)

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(
                f"Повторная попытка связывания, "
                f"attempt {self.request.retries + 1}"
            )
            raise self.retry(exc=exc, countdown=300)  # Повтор через 5 минут

        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat(),
        }
