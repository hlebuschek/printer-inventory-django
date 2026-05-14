"""Celery-задачи для автоотправки писем по расписанию.

ВАЖНО: на проде SMTP должен быть настроен (EMAIL_HOST/PORT/USER/PASSWORD/USE_TLS
в env). В dev по умолчанию используется console-backend Django — письма выводятся
в лог воркера, никуда не уходят.

Beat-расписание включается переменной SUPPLIES_REPORT_AUTOSEND_ENABLED=True
в окружении (см. printer_inventory/settings.py). Сам флаг
ReportGroup.auto_send_enabled управляет конкретной группой.
"""

from __future__ import annotations

import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import ReportGroup
from .services import build_email_bodies, build_report_data, split_emails

logger = logging.getLogger(__name__)

# Окно вокруг auto_send_time, в которое считаем задачу «пора отправлять».
# Beat запускает dispatch каждую минуту, окно ±1 минута — на случай дрейфа.
DISPATCH_WINDOW_MINUTES = 1


@shared_task(bind=True, queue="low_priority", max_retries=2, default_retry_delay=300)
def send_supplies_report_task(self, group_id: int) -> dict:
    """Сформировать и отправить письмо по группе через SMTP.

    Возвращает dict со статусом — для логов/админки.
    Поднимает retry при сетевых ошибках SMTP (ConnectionError etc).
    """
    try:
        group = ReportGroup.objects.get(pk=group_id)
    except ReportGroup.DoesNotExist:
        logger.error("send_supplies_report_task: group %s не найдена", group_id)
        return {"ok": False, "error": "group not found"}

    if not group.is_active:
        logger.info("send_supplies_report_task: группа %s неактивна — пропуск", group.name)
        return {"ok": False, "error": "group inactive"}

    to_list = split_emails(group.to_emails)
    cc_list = split_emails(group.cc_emails)
    if not to_list:
        msg = "Не задано ни одного To-адреса"
        group.last_send_error = msg
        group.save(update_fields=["last_send_error"])
        logger.warning("send_supplies_report_task: %s (group=%s)", msg, group.name)
        return {"ok": False, "error": msg}

    rows = build_report_data(group)
    bodies = build_email_bodies(group, rows=rows)

    from_email = group.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost")

    email = EmailMultiAlternatives(
        subject=bodies.subject,
        body=bodies.text_body,
        from_email=from_email,
        to=to_list,
        cc=cc_list or None,
    )
    email.attach_alternative(bodies.html_body, "text/html")

    try:
        email.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — SMTP-ошибки бывают разные
        err_text = f"{type(exc).__name__}: {exc}"
        group.last_send_error = err_text
        group.save(update_fields=["last_send_error"])
        logger.exception("send_supplies_report_task: ошибка SMTP для group=%s", group.name)
        # Сетевые сбои — ретраим. Прочее (например, неправильный адрес) — не зацикливаемся.
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                pass
        return {"ok": False, "error": err_text}

    group.last_sent_at = timezone.now()
    group.last_send_error = ""
    group.save(update_fields=["last_sent_at", "last_send_error"])
    logger.info(
        "send_supplies_report_task: отправлено group=%s to=%s cc=%s",
        group.name,
        ", ".join(to_list),
        ", ".join(cc_list) if cc_list else "—",
    )
    return {"ok": True, "to": to_list, "cc": cc_list, "rows": len(rows)}


def _is_due(group: ReportGroup, now: datetime) -> bool:
    """Проверить, должна ли группа быть отправлена прямо сейчас."""
    if not group.auto_send_enabled or not group.is_active:
        return False
    if group.auto_send_time is None:
        return False

    # Сравниваем по локальному времени (Asia/Irkutsk) — beat работает в CELERY_TIMEZONE.
    local_now = timezone.localtime(now)
    target = group.auto_send_time
    target_minutes = target.hour * 60 + target.minute
    cur_minutes = local_now.hour * 60 + local_now.minute
    if abs(cur_minutes - target_minutes) > DISPATCH_WINDOW_MINUTES:
        return False

    # Дни недели: 1=Пн..7=Вс (как ISO). Python's isoweekday() даёт это.
    weekday = local_now.isoweekday()
    allowed = {int(d.strip()) for d in (group.auto_send_weekdays or "").split(",") if d.strip().isdigit()}
    if allowed and weekday not in allowed:
        return False

    # Отчёт ежедневный — если в эту дату уже отправляли, повторно не запускаем.
    # Защищает от двойного дispatch'а внутри beat-окна (±DISPATCH_WINDOW_MINUTES),
    # пока send-задача ещё не завершилась и last_sent_at не обновился.
    if group.last_sent_at:
        last_local = timezone.localtime(group.last_sent_at)
        if last_local.date() == local_now.date():
            return False

    return True


@shared_task(queue="low_priority")
def dispatch_due_supplies_reports() -> dict:
    """Beat-задача: каждую минуту проверяет, какие группы пора отправлять.

    Не отправляет сама — диспатчит send_supplies_report_task для каждой подходящей.
    """
    now = timezone.now()
    dispatched: list[int] = []
    for group in ReportGroup.objects.filter(is_active=True, auto_send_enabled=True):
        if _is_due(group, now):
            send_supplies_report_task.delay(group.id)
            dispatched.append(group.id)
    if dispatched:
        logger.info("dispatch_due_supplies_reports: запущено %d групп: %s", len(dispatched), dispatched)
    return {"dispatched": dispatched, "checked_at": now.isoformat()}
