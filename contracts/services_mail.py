"""Приём ответных писем подрядчика в переписку по заявке.

Разбирается только конверт письма — тема, заголовки треда, дата, вложения.
Смысл текста не анализируется: переписка ведётся живой речью, и вывести из неё
статус заявки нельзя. Обычное письмо просто попадает в ленту; статус меняет
человек или формальное письмо по п. 6.6.4 ТЗ (см. `services_request_closing`).

Заявка узнаётся по нашему же номеру в теме («Заявка № 2026-00001»), который
сохраняется в ответе как «Re: …». Запасной путь — заголовки треда: подрядчик может
ответить со своей темой, но почтовый клиент проставит In-Reply-To на наше письмо.
"""

import imaplib
import logging
import re
from email import message_from_bytes, policy

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import ServiceProvider, ServiceRequest, ServiceRequestAttachment, ServiceRequestMessage
from .services_request_closing import close_by_letter
from .services_request_notifications import notify_subscribers

logger = logging.getLogger(__name__)

# Формат из ServiceRequest.number: год и id заявки
NUMBER_RE = re.compile(r"Заявка\s*№\s*(\d{4})-(\d+)", re.IGNORECASE)

MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024
MAX_BODY_LENGTH = 100_000

# Порог тревоги по квоте ящика: письма после обработки остаются в ящике
# (мы их только помечаем прочитанными), так что место кончается неизбежно.
QUOTA_ALERT_RATIO = 0.8
# RFC 2087: STORAGE в единицах по 1024 байта
QUOTA_STORAGE_RE = re.compile(rb"STORAGE\s+(\d+)\s+(\d+)")


def _header(message, name):
    """Значение заголовка строкой. Битые заголовки встречаются и не должны ронять приём."""
    try:
        value = message[name]
    except Exception:  # noqa: BLE001 — email кидает разные исключения на кривых заголовках
        logger.warning("Не удалось прочитать заголовок %s", name)
        return ""
    return str(value).strip() if value else ""


def _sent_at(message):
    """Дата письма — время события для ленты. Без заголовка берём момент приёма."""
    try:
        moment = message["Date"].datetime if message["Date"] else None
    except Exception:  # noqa: BLE001
        moment = None
    if moment is None:
        return timezone.now()
    return moment if timezone.is_aware(moment) else timezone.make_aware(moment)


def _body_text(message):
    """Текст письма: plain как есть, html — без разметки."""
    try:
        part = message.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        content = part.get_content()
    except Exception:  # noqa: BLE001
        logger.warning("Не удалось разобрать тело письма")
        return ""

    if part.get_content_type() == "text/html":
        content = strip_tags(content)
    return content.strip()[:MAX_BODY_LENGTH]


def _request_by_number(subject):
    match = NUMBER_RE.search(subject or "")
    if not match:
        return None

    year, pk = match.groups()
    service_request = ServiceRequest.objects.filter(pk=int(pk)).first()
    # Год сверяем по самому номеру, а не фильтром по БД: `number` форматирует
    # registered_at как есть, а `__year` пересчитывает его в TIME_ZONE.
    if service_request is None or not service_request.number.startswith(f"{year}-"):
        return None
    return service_request


def _request_by_thread(in_reply_to, references):
    """Заявка по нашему исходящему письму, на которое отвечают."""
    ids = [value for value in [in_reply_to, *(references or "").split()] if value]
    if not ids:
        return None

    origin = (
        ServiceRequestMessage.objects.filter(
            channel=ServiceProvider.EMAIL, external_id__in=ids, service_request__isnull=False
        )
        .select_related("service_request")
        .first()
    )
    return origin.service_request if origin else None


def _save_attachments(message, email_message):
    saved = 0
    for part in email_message.iter_attachments():
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > MAX_ATTACHMENT_SIZE:
            logger.warning(
                "Вложение %s письма %s больше %s МБ — пропущено",
                part.get_filename(),
                message.pk,
                MAX_ATTACHMENT_SIZE // 1024 // 1024,
            )
            continue

        filename = (part.get_filename() or "attachment")[:255]
        attachment = ServiceRequestAttachment(
            message=message,
            filename=filename,
            content_type=part.get_content_type()[:100],
            size=len(payload),
        )
        attachment.file.save(filename, ContentFile(payload), save=False)
        attachment.save()
        saved += 1
    return saved


@transaction.atomic
def ingest_email(raw):
    """Раскладывает письмо в переписку. Возвращает запись или None, если письмо уже принято."""
    email_message = message_from_bytes(raw, policy=policy.default)

    message_id = _header(email_message, "Message-ID")[:255]
    # Свои же исходящие копии (ящик стоит в копии письма) отсекаются тем же условием:
    # Message-ID у них наш, запись уже есть.
    if (
        message_id
        and ServiceRequestMessage.objects.filter(channel=ServiceProvider.EMAIL, external_id=message_id).exists()
    ):
        return None

    subject = _header(email_message, "Subject")[:500]
    in_reply_to = _header(email_message, "In-Reply-To")[:255]
    references = _header(email_message, "References")

    service_request = _request_by_number(subject) or _request_by_thread(in_reply_to, references)

    message = ServiceRequestMessage.objects.create(
        service_request=service_request,
        channel=ServiceProvider.EMAIL,
        direction=ServiceRequestMessage.INCOMING,
        external_id=message_id,
        in_reply_to=in_reply_to,
        subject=subject,
        from_email=_header(email_message, "From")[:320],
        to_emails=_header(email_message, "To")[:1000],
        body_text=_body_text(email_message),
        sent_at=_sent_at(email_message),
    )
    attachments = _save_attachments(message, email_message)

    if service_request is None:
        logger.warning("Письмо «%s» не привязано к заявке — нужна ручная привязка", subject)
    else:
        logger.info("Заявка %s: получено письмо, вложений %s", service_request.number, attachments)
        close_by_letter(service_request, message)
        notify_subscribers(message)
    return message


def _connect():
    imap_class = imaplib.IMAP4_SSL if settings.SERVICE_DESK_IMAP_SSL else imaplib.IMAP4
    connection = imap_class(settings.SERVICE_DESK_IMAP_HOST, settings.SERVICE_DESK_IMAP_PORT)
    connection.login(settings.SERVICE_DESK_IMAP_USER, settings.SERVICE_DESK_IMAP_PASSWORD)
    connection.select(settings.SERVICE_DESK_IMAP_FOLDER)
    return connection


def check_mailbox_quota(connection):
    """Сверяет заполнение ящика с квотой и предупреждает администраторов.

    Не каждый сервер поддерживает QUOTA (RFC 2087) — тогда молча выходим.
    Повтор в тот же день гасится event_key, так что тревога приходит раз в сутки.
    """
    try:
        status, data = connection.getquotaroot(settings.SERVICE_DESK_IMAP_FOLDER)
    except (imaplib.IMAP4.error, OSError):
        return None
    if status != "OK":
        return None

    flat = b" ".join(part for chunk in data for part in (chunk if isinstance(chunk, list) else [chunk]) if part)
    match = QUOTA_STORAGE_RE.search(flat)
    if not match:
        return None

    used_kb, limit_kb = int(match.group(1)), int(match.group(2))
    if not limit_kb:
        return None
    ratio = used_kb / limit_kb
    if ratio < QUOTA_ALERT_RATIO:
        return ratio

    from django.contrib.auth import get_user_model

    from access.models import Notification
    from access.services.notifications import notify

    admins = get_user_model().objects.filter(is_superuser=True, is_active=True)
    today = timezone.localdate()
    notify(
        list(admins),
        kind=Notification.MAILBOX_QUOTA,
        title=f"Ящик сервис-деска заполнен на {ratio:.0%}",
        subtitle=(
            f"{settings.SERVICE_DESK_IMAP_USER}: занято {used_kb // 1024} из {limit_kb // 1024} МБ. "
            "Освободите место, иначе письма подрядчика начнут теряться."
        ),
        target_key="contracts.mailbox_quota",
        event_key=f"contracts.mailbox_quota:{today:%Y-%m-%d}",
    )
    logger.warning("Ящик сервис-деска заполнен на %.0f%% (%s/%s КБ)", ratio * 100, used_kb, limit_kb)
    return ratio


def fetch_service_desk_mail():
    """Забирает непрочитанные письма из ящика сервис-деска."""
    if not settings.SERVICE_DESK_IMAP_HOST:
        logger.info("IMAP сервис-деска не настроен — приём писем пропущен")
        return {"fetched": 0, "ingested": 0, "unmatched": 0, "errors": 0}

    stats = {"fetched": 0, "ingested": 0, "unmatched": 0, "errors": 0}
    connection = _connect()
    try:
        check_mailbox_quota(connection)
        _, data = connection.search(None, "UNSEEN")
        for num in data[0].split():
            stats["fetched"] += 1
            try:
                _, payload = connection.fetch(num, "(RFC822)")
                message = ingest_email(payload[0][1])
            except Exception:  # noqa: BLE001 — одно кривое письмо не должно останавливать разбор
                # Флаг \Seen не ставим: письмо вернётся в следующий заход.
                stats["errors"] += 1
                logger.exception("Не удалось принять письмо из ящика сервис-деска")
                continue

            connection.store(num, "+FLAGS", "\\Seen")
            if message is not None:
                stats["ingested"] += 1
                if message.service_request_id is None:
                    stats["unmatched"] += 1
    finally:
        try:
            connection.close()
        finally:
            connection.logout()

    logger.info("Почта сервис-деска: %s", stats)
    return stats
