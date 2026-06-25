"""
Фоновые задачи дашборда.

Тяжёлая XLSX-выгрузка статистики идёт в очередь `exports` (не в low_priority,
где бэклог массового опроса — пользователь не дождётся). Прогресс и строки
лога пишутся в Redis-ключ, фронт опрашивает его через statistics_export_status.
Готовый файл кладётся в cache (base64) и отдаётся один раз через
statistics_export_download.
"""

import logging
import time

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Ключи в Redis (db 0 = default cache).
STATS_EXPORT_PROGRESS_PREFIX = "dashboard:stats_export:progress:"
STATS_EXPORT_RESULT_PREFIX = "dashboard:stats_export:result:"
PROGRESS_TTL = 60 * 15  # 15 минут
RESULT_TTL = 60 * 15  # 15 минут на скачивание


def progress_key(task_id):
    return f"{STATS_EXPORT_PROGRESS_PREFIX}{task_id}"


def result_key(task_id):
    return f"{STATS_EXPORT_RESULT_PREFIX}{task_id}"


@shared_task(bind=True, queue="exports", time_limit=600, soft_time_limit=540)
def build_statistics_export_task(self, org_id=None, days=7, months=0):
    """Собирает полный XLSX-отчёт статистики в фоне.

    Возвращает {result_key, filename, size}; фронт скачивает через
    statistics_export_download по task_id.
    """
    from base64 import b64encode

    from dashboard.services_stats import build_statistics_workbook

    task_id = self.request.id
    pkey = progress_key(task_id)
    log_lines = []

    def push(percent, message):
        log_lines.append(f"{time.strftime('%H:%M:%S')} — {message}")
        state = {
            "percent": max(0, min(100, int(percent))),
            "message": message,
            "log": log_lines[-50:],  # последние 50 строк
            "done": False,
        }
        cache.set(pkey, state, PROGRESS_TTL)

    try:
        push(1, "Запуск выгрузки…")
        content, filename = build_statistics_workbook(org_id=org_id, days=days, months=months, progress=push)

        cache.set(
            result_key(task_id),
            {"content_b64": b64encode(content).decode("ascii"), "filename": filename},
            RESULT_TTL,
        )

        final = {
            "percent": 100,
            "message": "Готово",
            "log": log_lines[-50:],
            "done": True,
            "filename": filename,
            "size": len(content),
        }
        cache.set(pkey, final, PROGRESS_TTL)
        return {"result_key": result_key(task_id), "filename": filename, "size": len(content)}

    except Exception as e:
        logger.exception("build_statistics_export_task failed")
        log_lines.append(f"{time.strftime('%H:%M:%S')} — Ошибка: {e}")
        cache.set(
            pkey,
            {"percent": 100, "message": f"Ошибка: {e}", "log": log_lines[-50:], "done": True, "error": str(e)},
            PROGRESS_TTL,
        )
        raise
