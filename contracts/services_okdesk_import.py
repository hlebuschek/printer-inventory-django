"""Разовый импорт открытых заявок Okdesk в журнал заявок.

Только чтение из Okdesk (GET): заявки, комментарии и файлы забираются как есть,
ничего в Okdesk не создаётся и не меняется. Ссылка на файл из API живёт ~30 секунд,
поэтому вложение скачивается сразу же, а не сохраняется ссылкой.

Направление сообщения — по типу автора комментария: employee (сотрудник подрядчика)
пишет нам, contact (наш сотрудник) — от нас.
"""

from __future__ import annotations

import html
import logging
import mimetypes
import re

import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.core.files import File
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from integrations.models import OkdeskIssue
from integrations.okdesk_secrets import mask_api_token

from .models import ServiceProvider, ServiceRequest, ServiceRequestAttachment, ServiceRequestMessage
from .services_request_closing import ALLOWED_ACT_EXTENSIONS, act_attachment

logger = logging.getLogger(__name__)

FINAL_STATUS_CODES = {"completed", "closed"}
CLOSED_STATUS_NAMES = ["Закрыта", "Решена"]


def _get(path, **params):
    params["api_token"] = settings.OKDESK_API_TOKEN
    response = requests.get(
        f"{settings.OKDESK_API_URL}{path}",
        params=params,
        verify=settings.OKDESK_VERIFY_SSL,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _clean(raw):
    # strip_tags не трогает сущности, а Okdesk щедр на &nbsp;
    return html.unescape(strip_tags(raw or "")).replace("\xa0", " ").strip()


_TABLE_RE = re.compile(r"<table.*?</table>", re.S | re.I)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def _clean_description(raw):
    """Описание заявки, поданной через сайт, — HTML-таблица: шапка и строка значений.

    strip_tags расплющил бы её в столбик «все заголовки, потом все значения»,
    поэтому таблицу разворачиваем в «Ключ: значение», текст после неё — ниже.
    """
    raw = raw or ""
    match = _TABLE_RE.search(raw)
    if match is None:
        return _clean(raw)

    rows = [[_clean(cell) for cell in _CELL_RE.findall(tr)] for tr in _TR_RE.findall(match.group(0))]
    if len(rows) == 2 and len(rows[0]) == len(rows[1]):
        lines = [f"{name}: {value}" for name, value in zip(rows[0], rows[1]) if value]
    else:
        lines = [" | ".join(filter(None, cells)) for cells in rows if any(cells)]

    rest = _clean(_TABLE_RE.sub(" ", raw))
    return "\n".join(lines + ([rest] if rest else []))


def resolve_initiator(author_name):
    """Ищет пользователя по автору заявки в Okdesk. None — если сопоставить не удалось.

    Почты автора Okdesk не отдаёт, поэтому сравниваем по ФИО. Формат «Фамилия Имя» —
    тот же, которым мы сами подписываем заявки при отправке (см. build_description).
    Отчество может прийти с любой стороны: Okdesk пишет его не всегда, а из Keycloak
    оно попадает в first_name, — поэтому сверяем только фамилию и первое имя.
    При неоднозначности возвращаем None: пустой инициатор лучше заявки,
    приписанной не тому человеку.
    """
    parts = (author_name or "").split()
    if len(parts) < 2 or any("@" in part for part in parts):
        return None

    last_name, first_name = _fold(parts[0]), _fold(parts[1])
    # Сверяем в Python, а не запросом: базы с LC_COLLATE=C не приводят кириллицу к регистру,
    # поэтому iexact там молча превращается в точное сравнение
    matches = [
        user
        for user in get_user_model().objects.filter(is_active=True).exclude(last_name="").exclude(first_name="")
        if _fold(user.last_name) == last_name and _first_name(user) == first_name
    ]
    return matches[0] if len(matches) == 1 else None


def _first_name(user):
    parts = user.first_name.split()
    return _fold(parts[0]) if parts else ""


def _fold(value):
    # Okdesk и наш справочник расходятся в «ё»: «Нефедов» против «Нефёдов»
    return value.lower().replace("ё", "е")


def _fetch_attachment(issue_id, attachment_id, filename=""):
    """Скачивает файл вложения, возвращает (имя, содержимое) или None.

    Метаданные отдаёт сам Okdesk, а файл — стороннее хранилище, поэтому запрос может
    упереться в сеть даже при живом API. Таймаут раздельный: если хранилище недоступно,
    отваливаемся на connect, а не ждём полную минуту на каждом вложении.
    """
    meta = _get(f"/issues/{issue_id}/attachments/{attachment_id}")
    url = meta.get("attachment_url")
    if not url:
        return None

    file_response = requests.get(url, verify=settings.OKDESK_VERIFY_SSL, timeout=(5, 30))
    file_response.raise_for_status()
    return (filename or meta.get("attachment_file_name") or f"attachment-{attachment_id}"), file_response.content


def download_attachment_file(stored):
    """Докачивает файл к сохранённым метаданным. True — файл на месте."""
    if stored.file:
        return True
    if not (stored.okdesk_issue_id and stored.okdesk_attachment_id):
        return False

    fetched = _fetch_attachment(stored.okdesk_issue_id, stored.okdesk_attachment_id, stored.filename)
    if fetched is None:
        return False

    filename, content = fetched
    stored.size = len(content)
    stored.file.save(filename, ContentFile(content), save=True)
    return True


def _store_attachment(message, issue_id, attachment):
    """Вложение письма: метаданные сохраняем всегда, файл — если хранилище доступно.

    Без файла запись всё равно нужна: в ленте видно, что подрядчик что-то приложил,
    а `download_attachment_file` докачает содержимое, когда до хранилища появится доступ.
    """
    filename = attachment.get("attachment_file_name") or f"attachment-{attachment['id']}"
    stored = ServiceRequestAttachment.objects.create(
        message=message,
        filename=filename,
        content_type=mimetypes.guess_type(filename)[0] or "",
        size=int(attachment.get("attachment_file_size") or 0),
        okdesk_issue_id=issue_id,
        okdesk_attachment_id=attachment["id"],
    )

    if not settings.OKDESK_FETCH_ATTACHMENT_FILES:
        return stored

    try:
        download_attachment_file(stored)
    except requests.RequestException as exc:
        logger.warning("Заявка %s: не скачано вложение %s: %s", issue_id, attachment.get("id"), mask_api_token(exc))
    return stored


def _ensure_description_message(service_request, row, detail):
    """Тело заявки Okdesk — первое сообщение треда, как письмо-заявка в email-канале."""
    external_id = f"issue-{row.issue_id}"
    if ServiceRequestMessage.objects.filter(channel=ServiceProvider.OKDESK, external_id=external_id).exists():
        return 0

    author = (detail.get("author") or {}).get("name") or row.author_name
    ServiceRequestMessage.objects.create(
        service_request=service_request,
        channel=ServiceProvider.OKDESK,
        direction=ServiceRequestMessage.OUTGOING,
        external_id=external_id,
        from_email=author or "",
        subject=detail.get("title") or row.title or "",
        body_text=_clean_description(detail.get("description")),
        sent_at=parse_datetime(detail.get("created_at") or "") or row.created_at,
    )
    return 1


def _import_comments(service_request, issue_id):
    created = 0
    for comment in _get(f"/issues/{issue_id}/comments"):
        external_id = str(comment["id"])
        if ServiceRequestMessage.objects.filter(channel=ServiceProvider.OKDESK, external_id=external_id).exists():
            continue

        author = comment.get("author") or {}
        message = ServiceRequestMessage.objects.create(
            service_request=service_request,
            channel=ServiceProvider.OKDESK,
            direction=(
                ServiceRequestMessage.INCOMING if author.get("type") == "employee" else ServiceRequestMessage.OUTGOING
            ),
            external_id=external_id,
            from_email=author.get("name") or "",
            body_text=_clean(comment.get("content")),
            sent_at=parse_datetime(comment.get("published_at") or "") or None,
        )
        created += 1

        for attachment in comment.get("attachments") or []:
            _store_attachment(message, issue_id, attachment)
    return created


def _attach_act_scan(service_request, issue_id, detail):
    """Переносит скан акта в act_scan: из закрывающего комментария подрядчика,
    иначе — из вложений самой заявки (АМБ часто цепляет акт к заявке, а не к комментарию)."""
    if not service_request.closed_at or service_request.act_scan:
        return False

    messages = (
        service_request.messages.filter(channel=ServiceProvider.OKDESK, direction=ServiceRequestMessage.INCOMING)
        .order_by("-sent_at")
        .prefetch_related("attachments")
    )
    for message in messages:
        attachment = act_attachment(message)
        if attachment is None:
            continue
        with attachment.file.open("rb") as source:
            service_request.act_scan.save(attachment.filename, File(source), save=False)
        service_request.closing_message = message
        service_request.save(update_fields=["act_scan", "closing_message", "updated_at"])
        return True

    if not settings.OKDESK_FETCH_ATTACHMENT_FILES:
        return False

    for attachment in detail.get("attachments") or []:
        filename = attachment.get("attachment_file_name") or ""
        if filename.rsplit(".", 1)[-1].lower() not in ALLOWED_ACT_EXTENSIONS:
            continue
        try:
            fetched = _fetch_attachment(issue_id, attachment["id"], filename)
        except requests.RequestException as exc:
            # Недоступное хранилище файлов не повод терять уже импортированную заявку
            logger.warning("Заявка %s: не скачан скан акта: %s", issue_id, mask_api_token(exc))
            return False
        if fetched is None:
            continue
        filename, content = fetched
        service_request.act_scan.save(filename, ContentFile(content), save=False)
        service_request.save(update_fields=["act_scan", "updated_at"])
        return True

    return False


def _import_issue(row, provider, stats, device=None):
    detail = _get(f"/issues/{row.issue_id}")
    if not isinstance(detail, dict) or detail.get("id") != row.issue_id:
        # Okdesk на несуществующий номер отвечает 200 без заявки — не плодить пустышки
        raise requests.HTTPError(f"Okdesk вернул не заявку по номеру {row.issue_id}")
    is_final = (detail.get("status") or {}).get("code") in FINAL_STATUS_CODES
    completed_at = parse_datetime(detail.get("completed_at") or "") if is_final else None

    service_request = ServiceRequest.objects.filter(external_number=str(row.issue_id)).first()
    if service_request is None:
        description = _clean_description(detail.get("description")) or detail.get("title") or row.title
        service_request = ServiceRequest.objects.create(
            device=device or row.contract_device,
            service_provider=provider,
            external_number=str(row.issue_id),
            description=description,
            registered_at=parse_datetime(detail.get("created_at") or "") or row.created_at,
            restored_at=completed_at,
            closed_at=completed_at,
            initiator=resolve_initiator(row.author_name),
        )
        stats["closed" if is_final else "open"] += 1
    else:
        if service_request.initiator_id is None:
            # Заявка могла попасть в журнал до появления сопоставления авторов
            initiator = resolve_initiator(row.author_name)
            if initiator is not None:
                service_request.initiator = initiator
                service_request.save(update_fields=["initiator", "updated_at"])

        if is_final and service_request.closed_at is None and service_request.status != ServiceRequest.REJECTED:
            service_request.restored_at = service_request.restored_at or completed_at
            service_request.closed_at = completed_at
            service_request.save()
            stats["completed"] += 1

    stats["comments"] += _ensure_description_message(service_request, row, detail)
    stats["comments"] += _import_comments(service_request, row.issue_id)

    if is_final and _attach_act_scan(service_request, row.issue_id, detail):
        stats["acts"] += 1


def import_issue_with_device(issue_id, device):
    """Ручной ввод заявки Okdesk в журнал с явно выбранным устройством.

    Для заявок, где серийника нет или он не совпал с договором: привязку в зеркале
    `OkdeskIssue` синхронизация перетёрла бы, поэтому связь живёт в самом журнале
    (`external_number`), а зеркало остаётся как есть. Дальше комментарии и закрытие
    подтягивает обычный синк — он ищет заявку по номеру, устройство ему не нужно.
    """
    existing = ServiceRequest.objects.filter(external_number=str(issue_id)).first()
    if existing is not None:
        return existing

    row = OkdeskIssue.objects.filter(issue_id=issue_id).order_by("pk").first()
    if row is None:
        raise OkdeskIssue.DoesNotExist(f"Заявка Okdesk {issue_id} не найдена в зеркале")

    provider = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK, is_active=True).first()
    stats = _new_stats()
    # Атомарно: если Okdesk отвалился на комментариях, полузаведённая заявка откатывается
    with transaction.atomic():
        _import_issue(row, provider, stats, device=device)
    return ServiceRequest.objects.get(external_number=str(issue_id))


def _linked_issues():
    return OkdeskIssue.objects.filter(contract_device__isnull=False, journal_excluded=False).select_related(
        "contract_device__city", "contract_device__organization"
    )


def _new_stats():
    return {"open": 0, "closed": 0, "completed": 0, "comments": 0, "acts": 0, "errors": 0}


def _import_rows(rows, provider, stats):
    for row in rows:
        try:
            _import_issue(row, provider, stats)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                # Доступ к заявке ограничен и сам не появится — исключаем,
                # чтобы не ловить один и тот же 403 каждый прогон
                OkdeskIssue.objects.filter(issue_id=row.issue_id).update(journal_excluded=True)
                logger.info("Заявка Okdesk %s недоступна (403) — исключена из синка журнала", row.issue_id)
            else:
                stats["errors"] += 1
                logger.warning("Заявка Okdesk %s не импортирована: %s", row.issue_id, mask_api_token(exc))
        except Exception as exc:
            stats["errors"] += 1
            logger.warning("Заявка Okdesk %s не импортирована: %s", row.issue_id, mask_api_token(exc))
    return stats


def import_issues(limit=None, closed_limit=0):
    """Создаёт заявки журнала по OkdeskIssue с привязанным устройством.

    Берёт все локально открытые обращения (закрытые в живом Okdesk импортируются
    как выполненные — у них restored/closed из completed_at) и, по желанию,
    `closed_limit` последних закрытых. Повторный запуск безопасен: заявки ищутся
    по external_number, комментарии — по (channel, external_id).
    """
    provider = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK, is_active=True).first()
    base = _linked_issues()
    rows = list(base.exclude(status_name__in=CLOSED_STATUS_NAMES).order_by("issue_id")[: limit or None])
    if closed_limit:
        rows += list(base.filter(status_name__in=CLOSED_STATUS_NAMES).order_by("-created_at")[:closed_limit])

    return _import_rows(rows, provider, _new_stats())


def sync_requests():
    """Периодический синк журнала с Okdesk (только GET).

    Открытые в Okdesk обращения с привязанным устройством попадают в журнал,
    по ним подтягиваются новые комментарии. Наши открытые заявки с external_number
    проверяются по живому статусу — Okdesk закрыл, значит закрываем и мы
    (restored/closed из completed_at) и забираем скан акта.
    """
    stats = _new_stats()
    provider = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK, is_active=True).first()
    if provider is None:
        return stats

    open_ids = [
        int(number)
        for number in ServiceRequest.objects.filter(
            closed_at__isnull=True,
            service_provider__issue_tracker=ServiceProvider.OKDESK,
            external_number__isnull=False,
        )
        .exclude(external_number="")
        .values_list("external_number", flat=True)
        if number.isdigit()
    ]
    # Наши открытые заявки синкаются и при непривязанном зеркале: связь по external_number,
    # а строка OkdeskIssue могла остаться без устройства (ручной ввод в журнал)
    rows = (
        OkdeskIssue.objects.filter(journal_excluded=False)
        .filter(Q(issue_id__in=open_ids) | (Q(contract_device__isnull=False) & ~Q(status_name__in=CLOSED_STATUS_NAMES)))
        .select_related("contract_device__city", "contract_device__organization")
        .order_by("issue_id")
        .distinct()
    )
    return _import_rows(rows, provider, stats)
