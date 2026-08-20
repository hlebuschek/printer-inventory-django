"""Закрытие заявки: отметка восстановления и приём технического акта.

Восстановление и выполнение — два разных события, и разводить их обязательно:
момент восстановления останавливает простой D в показателе K1, а по п. 6.6.4 ТЗ
запрос считается выполненным только после получения скана технического акта.
Между ними могут пройти дни, и закрытие по акту задним числом не должно
удлинять простой.

Данные подрядчика (п. 6.5.2 ТЗ фактическое время фиксирует Исполнитель)
записываются рядом со своими, а не вместо них — расхождение нужно видеть.
"""

import logging
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from access.services.change_log_service import ChangeLogService

from .models import ServiceRequest

logger = logging.getLogger(__name__)

MAX_ACT_SIZE = 10 * 1024 * 1024
ALLOWED_ACT_EXTENSIONS = ("pdf", "jpg", "jpeg", "png", "tif", "tiff", "heic", "heif")

# Формальное письмо по п. 6.6.4 ТЗ — «работоспособность Оборудования восстановлена».
# Сверяем по основам слов: тема приходит с «Re:», в другом падеже и с чужими добавками.
CLOSING_SUBJECT_STEMS = ("работоспособн", "восстановлен")


def _local(moment):
    """Время в сообщениях — местное: в UTC оно не совпадёт с тем, что человек видит в журнале."""
    return f"{timezone.localtime(moment):%d.%m.%Y %H:%M}"


def _validate_moment(service_request, moment, label):
    if moment is None:
        raise ValidationError(f"{label} не указано.")
    if moment < service_request.registered_at:
        raise ValidationError(f"{label} раньше регистрации заявки ({_local(service_request.registered_at)}).")
    if moment > timezone.now():
        raise ValidationError(f"{label} в будущем.")


def _validate_act_file(uploaded):
    if uploaded.size > MAX_ACT_SIZE:
        raise ValidationError(f"Файл больше {MAX_ACT_SIZE // 1024 // 1024} МБ.")
    suffix = PurePosixPath(uploaded.name.replace("\\", "/")).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_ACT_EXTENSIONS:
        raise ValidationError(f"Скан акта принимается в форматах: {', '.join(ALLOWED_ACT_EXTENSIONS)}.")


@transaction.atomic
def mark_restored(
    service_request,
    restored_at,
    *,
    user=None,
    request=None,
    provider_restored_at=None,
    provider_downtime_hours=None,
):
    """Отмечает восстановление работоспособности — с этого момента простой не идёт."""
    if service_request.status == ServiceRequest.REJECTED:
        raise ValidationError("Заявка отклонена — отметить восстановление нельзя.")

    _validate_moment(service_request, restored_at, "Время восстановления")
    if provider_restored_at is not None:
        _validate_moment(service_request, provider_restored_at, "Время восстановления по данным подрядчика")

    old_data = ChangeLogService.get_model_data(service_request)
    service_request.restored_at = restored_at
    service_request.provider_restored_at = provider_restored_at
    service_request.provider_downtime_hours = provider_downtime_hours
    service_request.save(
        update_fields=["restored_at", "provider_restored_at", "provider_downtime_hours", "status", "updated_at"]
    )
    ChangeLogService.log_update(service_request, user=user, request=request, old_data=old_data)

    logger.info("Заявка %s: восстановление отмечено на %s", service_request.number, restored_at)
    return service_request


@transaction.atomic
def close_by_act(service_request, *, act_file=None, act_number="", closed_at=None, user=None, request=None):
    """Принимает технический акт и закрывает заявку.

    Скан обязателен при первом закрытии: без него запрос по ТЗ не выполнен.
    Повторный вызов заменяет файл или реквизиты у уже закрытой заявки.
    """
    if service_request.status == ServiceRequest.REJECTED:
        raise ValidationError("Заявка отклонена — закрывать по акту нечего.")
    if not service_request.restored_at:
        raise ValidationError("Сначала отметьте восстановление работоспособности.")
    if act_file is None and not service_request.act_scan:
        raise ValidationError("Без скана технического акта заявка не считается выполненной (п. 6.6.4 ТЗ).")

    closed_at = closed_at or timezone.now()
    _validate_moment(service_request, closed_at, "Дата акта")
    if closed_at < service_request.restored_at:
        raise ValidationError(f"Дата акта раньше восстановления ({_local(service_request.restored_at)}).")

    if act_file is not None:
        _validate_act_file(act_file)

    old_data = ChangeLogService.get_model_data(service_request)
    if act_file is not None:
        service_request.act_scan.save(act_file.name, act_file, save=False)
    service_request.act_number = act_number
    service_request.closed_at = closed_at
    service_request.save(update_fields=["act_scan", "act_number", "closed_at", "status", "updated_at"])
    ChangeLogService.log_update(service_request, user=user, request=request, old_data=old_data)

    logger.info("Заявка %s закрыта по акту %s", service_request.number, act_number or "б/н")
    return service_request


def looks_like_closing_letter(subject):
    return all(stem in (subject or "").lower() for stem in CLOSING_SUBJECT_STEMS)


def act_attachment(message):
    """Первое вложение, годное как скан акта. Содержимое файла не разбираем.

    Вложения Okdesk без скачанного файла пропускаем: актом становится сам файл,
    одного имени для этого мало.
    """
    for attachment in message.attachments.all():
        if not attachment.file:
            continue
        suffix = PurePosixPath(attachment.filename.replace("\\", "/")).suffix.lower().lstrip(".")
        if suffix in ALLOWED_ACT_EXTENSIONS:
            return attachment
    return None


def _close_with_message(service_request, message, attachment, *, user=None, request=None):
    """Общий низ закрытия письмом: вложение становится сканом акта, письмо — основанием."""
    restored_at = service_request.restored_at or message.sent_at
    _validate_moment(service_request, restored_at, "Время восстановления")
    _validate_moment(service_request, message.sent_at, "Дата письма")

    old_data = ChangeLogService.get_model_data(service_request)
    with attachment.file.open("rb") as source:
        service_request.act_scan.save(attachment.filename, File(source), save=False)
    service_request.restored_at = restored_at
    # Письмо не может быть выпущено раньше восстановления, отмеченного человеком
    service_request.closed_at = max(message.sent_at, restored_at)
    service_request.closing_message = message
    service_request.save(
        update_fields=["act_scan", "restored_at", "closed_at", "closing_message", "status", "updated_at"]
    )
    ChangeLogService.log_update(service_request, user=user, request=request, old_data=old_data)


@transaction.atomic
def close_by_letter(service_request, message):
    """Закрывает заявку по формальному письму подрядчика со сканом акта.

    Срабатывает только связка «тема по п. 6.6.4 ТЗ + вложение»: смысл текста
    не разбирается, а письмо без акта запрос выполненным не делает. Время
    восстановления берётся из даты письма и остаётся правимым — подрядчик
    пишет позже, чем чинит, а уже отмеченное человеком время не трогаем.
    """
    if service_request.status in (ServiceRequest.REJECTED, ServiceRequest.CLOSED):
        return False
    if not looks_like_closing_letter(message.subject):
        return False

    attachment = act_attachment(message)
    if attachment is None:
        return False

    try:
        _close_with_message(service_request, message, attachment)
    except ValidationError as exc:
        logger.warning("Заявка %s: письмо не закрывает заявку — %s", service_request.number, "; ".join(exc.messages))
        return False

    logger.info("Заявка %s закрыта письмом %s подрядчика", service_request.number, message.pk)
    return True


@transaction.atomic
def close_by_message(service_request, message, *, user=None, request=None):
    """Закрывает заявку выбранным письмом по решению человека.

    Страховка на главный сбой автозакрытия: подрядчик прислал акт, но тему
    написал свою — формального письма не случилось. Проверки темы здесь нет,
    остальное как у close_by_letter, но с ошибками вместо тихого отказа.
    """
    if service_request.status == ServiceRequest.REJECTED:
        raise ValidationError("Заявка отклонена — закрывать нечего.")
    if service_request.status == ServiceRequest.CLOSED:
        raise ValidationError("Заявка уже закрыта.")
    if message.direction != message.INCOMING:
        raise ValidationError("Закрыть заявку можно только письмом подрядчика, не своим.")

    attachment = act_attachment(message)
    if attachment is None:
        raise ValidationError(f"В письме нет вложения, годного как скан акта ({', '.join(ALLOWED_ACT_EXTENSIONS)}).")

    _close_with_message(service_request, message, attachment, user=user, request=request)

    logger.info("Заявка %s закрыта письмом %s вручную (%s)", service_request.number, message.pk, user)
    return service_request
