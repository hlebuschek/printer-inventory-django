"""
Celery задачи для приложения contracts.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
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

        return {"success": True, "timestamp": timezone.now().isoformat(), **stats}

    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА В ЗАДАЧЕ СВЯЗЫВАНИЯ: {exc}", exc_info=True)
        logger.error("=" * 80)

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(f"Повторная попытка связывания, " f"attempt {self.request.retries + 1}")
            raise self.retry(exc=exc, countdown=300)  # Повтор через 5 минут

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
        }


@shared_task
def probe_autopoll_candidates_task(session_id):
    """
    Проверяет устройства сессии импорта в GLPI (см. contracts.services_autopoll).
    Вынесено в Celery: на каждый серийник уходит несколько запросов к API.
    """
    from contracts.models import ImportSession
    from contracts.services_autopoll import probe_session

    session = ImportSession.objects.get(pk=session_id)
    stats = probe_session(session)
    logger.info(f"Автоопрос: сессия {session_id} проверена в GLPI, {stats}")
    return stats


@shared_task
def verify_autopoll_candidate_task(candidate_id):
    """
    Пробный опрос кандидата по IP из GLPI (см. contracts.services_autopoll).
    Вынесено в Celery: netdiscovery молчащего адреса тянется до полутора минут.
    """
    from contracts.models import AutoPollCandidate
    from contracts.services_autopoll import verify_candidate

    candidate = AutoPollCandidate.objects.get(pk=candidate_id)
    verify_candidate(candidate)
    logger.info(f"Автоопрос: пробный опрос {candidate.serial_number} — {candidate.verify_message}")
    return {"candidate_id": candidate_id, "verify_ok": candidate.verify_ok, "message": candidate.verify_message}


SYNC_OKDESK_LOCK_KEY = "contracts:sync_okdesk_requests:lock"
# Дольше самого медленного мыслимого прогона: замок с TTL не зависнет навсегда,
# даже если воркер убили и finally не выполнился
SYNC_OKDESK_LOCK_TTL = 2 * 60 * 60


@shared_task
def sync_okdesk_requests():
    """
    Синхронизирует журнал заявок с Okdesk: новые обращения, комментарии,
    закрытия и сканы актов (см. contracts.services_okdesk_import).
    Только чтение из Okdesk — в него ничего не пишется.
    """
    from django.core.cache import cache

    from contracts.services_okdesk_import import sync_requests

    if not cache.add(SYNC_OKDESK_LOCK_KEY, timezone.now().isoformat(), timeout=SYNC_OKDESK_LOCK_TTL):
        logger.info("Синк заявок Okdesk уже выполняется — пропуск запуска")
        return {"skipped": "already_running"}

    try:
        stats = sync_requests()
    finally:
        cache.delete(SYNC_OKDESK_LOCK_KEY)

    logger.info(f"Синк заявок Okdesk: {stats}")
    return stats


REQUEST_EXPORT_CACHE_PREFIX = "contracts:request_export:"
# Файл скачивается сразу после готовности; ключ живёт ровно столько,
# чтобы пережить отвлёкшегося пользователя, и не копит xlsx в Redis
REQUEST_EXPORT_CACHE_TTL = 15 * 60


@shared_task(bind=True, queue="exports", time_limit=600, soft_time_limit=540)
def build_request_export_task(self, user_id, params):
    """Собирает выгрузку журнала в фоне и кладёт готовый xlsx в кэш.

    Выгружается весь журнал, а не только заявки заказчика выгрузки: право
    export_service_requests и есть разрешение видеть общую картину. Фильтр
    «только мои» по-прежнему работает — он приезжает в params.
    """
    from base64 import b64encode

    from django.core.cache import cache

    from contracts.api_views_requests import filter_requests
    from contracts.models import ServiceRequest
    from contracts.services_request_export import export_requests_excel

    user = get_user_model().objects.get(pk=user_id)
    content, filename = export_requests_excel(filter_requests(ServiceRequest.objects.all(), params, user))

    # Redis-бэкенд кэша хранит значения через pickle; base64 избавляет от
    # сюрпризов с сырыми bytes
    cache.set(
        f"{REQUEST_EXPORT_CACHE_PREFIX}{self.request.id}",
        {"content_b64": b64encode(content).decode("ascii"), "filename": filename, "user_id": user_id},
        timeout=REQUEST_EXPORT_CACHE_TTL,
    )
    logger.info(f"Выгрузка журнала {filename} готова, {len(content)} байт")
    return {"filename": filename, "size": len(content)}


@shared_task
def fetch_provider_messages():
    """
    Забирает ответы подрядчиков в переписку по заявкам (см. contracts.services_requests).
    Канал приёма определяется подрядчиком: сегодня это почта, у подрядчика с API
    здесь появятся комментарии его системы.
    """
    from contracts.services_requests import fetch_provider_messages as fetch

    stats = fetch()
    logger.info(f"Приём сообщений подрядчиков: {stats}")
    return stats
