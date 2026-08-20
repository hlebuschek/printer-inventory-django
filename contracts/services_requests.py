"""Подача заявок подрядчику через разные каналы.

Тело заявки одинаково для всех подрядчиков — различается только доставка,
поэтому состав по п.6.6.2 ТЗ собирается один раз, а канал выбирается
по `ServiceProvider.issue_tracker`. Новый подрядчик со своим API добавляется
классом-каналом и значением в `ISSUE_TRACKER_CHOICES`, без правок вызывающего кода.

Заявка сначала пишется в наш журнал (`ServiceRequest`), и только потом уходит
подрядчику: номер и нормативный срок должна присвоить наша система, иначе
показатели K1/K2 будут считаться по чужим данным.
"""

import logging
from dataclasses import dataclass, field
from email.utils import make_msgid, parseaddr

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from integrations.okdesk_secrets import mask_api_token

from .models import (
    ContractDevice,
    ServiceProvider,
    ServiceRequest,
    ServiceRequestAttachment,
    ServiceRequestMessage,
    ServiceRequestSubscription,
)

logger = logging.getLogger(__name__)

OKDESK_API_URL = getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")


class SubmissionError(RuntimeError):
    """Заявку не удалось передать подрядчику.

    HTTP-статус хранится здесь, чтобы view оставался тонким: у каналов
    принципиально разные причины отказа, и разбирать их в каждом view — дублирование.
    """

    def __init__(self, message, *, status=502, retry=False):
        super().__init__(message)
        self.status = status
        self.retry = retry


@dataclass
class SubmissionContext:
    """Данные формы, которых нет в журнале заявок."""

    user: object
    phone: str = ""
    cartridge: str = ""
    service_type: str = "Обслуживание"
    extra_rows: dict = field(default_factory=dict)

    @property
    def initiator_fio(self):
        fio = f"{self.user.last_name} {self.user.first_name}".strip()
        return fio or self.user.username


# ─── Общее тело заявки ────────────────────────────────────────────────────────

# Состав по п.6.6.2 ТЗ: адрес объекта, наименование оборудования, серийный номер,
# описание, ФИО и контакты инициатора и контактного лица на объекте.
_COLUMNS = [
    "№ заявки",
    "Организация",
    "Город",
    "Адрес",
    "Кабинет",
    "Производитель",
    "Модель",
    "Серийный номер",
    "Картридж",
    "Ремонт/обслуживание",
    "Срочность",
    "Комментарии",
]


def _row_values(service_request, context):
    device = service_request.device
    return [
        service_request.number,
        device.organization.name if device.organization_id else "",
        device.city.name if device.city_id else "",
        device.address or "",
        device.room_number or "",
        device.model.manufacturer.name if device.model_id else "",
        device.model.name if device.model_id else "",
        device.serial_number or "",
        context.cartridge,
        context.service_type,
        service_request.urgency_label if collects_urgency(device) else "",
        service_request.description,
    ]


def build_description(service_request, context):
    """Собирает тело заявки: HTML для систем подрядчика и текстовую версию для писем."""
    values = _row_values(service_request, context)

    signature = [f"С уважением, {context.initiator_fio}"]
    if context.phone:
        signature.append(context.phone)
    if service_request.initiator_contacts:
        signature.append(service_request.initiator_contacts)

    # escape() обязателен: тело уходит в стороннюю систему и рендерится там как HTML
    head = "".join(f"<th>{escape(name)}</th>" for name in _COLUMNS)
    body = "".join(f"<td>{escape(str(value))}</td>" for value in values)
    signature_html = "<br>".join(escape(line) for line in signature)

    html = (
        '<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody><tr>{body}</tr></tbody>"
        "</table>"
        f"<br><p>{signature_html}</p>"
    )

    lines = [f"{name}: {value}" for name, value in zip(_COLUMNS, values) if value]
    text = "\n".join(lines + [""] + signature)

    return html, text


def build_title(service_request, context):
    device = service_request.device
    city = device.city.name if device.city_id else ""
    return f"Заявка № {service_request.number}. {context.service_type}. {city}. {device.serial_number or ''}".strip()


# ─── Каналы доставки ──────────────────────────────────────────────────────────


class SubmissionChannel:
    code = ""
    # Срочность — договорённость с подрядчиком: он по ней обещает норматив.
    # Канал, который подрядчику ничего не передаёт, её не спрашивает.
    collects_urgency = True

    def send(self, service_request, context):
        """Передаёт заявку подрядчику и возвращает его номер обращения (или пустую строку)."""
        raise NotImplementedError

    def fetch(self):
        """Забирает новые сообщения подрядчика в переписку. Канал без приёма ничего не делает."""
        return {}

    def reply(self, service_request, text, attachments=(), *, user=None, to_email="", cc=()):
        """Отправляет ответ подрядчику в ту же переписку и записывает его в ленту."""
        raise SubmissionError(
            "По этому каналу ответить из журнала нельзя — напишите подрядчику его обычным способом.", status=409
        )


class OkdeskChannel(SubmissionChannel):
    code = ServiceProvider.OKDESK

    def send(self, service_request, context):
        # Локальные импорты: integrations и access сами зависят от contracts
        from access.models import UserOkdeskToken
        from integrations.models import OkdeskIssue

        try:
            token = UserOkdeskToken.objects.get(user=context.user).get_token()
        except UserOkdeskToken.DoesNotExist:
            raise SubmissionError(
                "API-токен Okdesk не настроен. Добавьте его в меню пользователя → Токен Okdesk.", status=403
            )

        html, _ = build_description(service_request, context)
        title = build_title(service_request, context)

        try:
            response = requests.post(
                f"{OKDESK_API_URL}/issues/",
                params={"api_token": token},
                json={"issue": {"title": title, "description": html}},
                verify=settings.OKDESK_VERIFY_SSL,
                timeout=15,
            )
            if response.status_code == 401:
                raise SubmissionError("Неверный API-токен Okdesk. Обновите токен в меню пользователя.", status=403)
            response.raise_for_status()
            issue_id = response.json().get("id")
        except requests.Timeout:
            raise SubmissionError(
                "Сервер Okdesk не отвечает. Попробуйте повторить через несколько минут.", status=504, retry=True
            )
        except requests.ConnectionError:
            raise SubmissionError("Нет соединения с сервером Okdesk. Проверьте сеть и попробуйте позже.", retry=True)
        except requests.RequestException as exc:
            # В сообщении requests лежит полный URL с личным токеном пользователя,
            # а лог общий на всех — маскируем до записи.
            masked = mask_api_token(exc)
            logger.exception("Ошибка при создании заявки в Okdesk: %s", masked)
            raise SubmissionError(f"Ошибка API Okdesk: {masked}. Попробуйте повторить позже.", retry=True)

        if not issue_id:
            return ""

        device = service_request.device
        first_name = (context.user.first_name or "").split()
        okdesk_author = f"{context.user.last_name} {first_name[0] if first_name else ''}".strip()
        OkdeskIssue.objects.update_or_create(
            issue_id=issue_id,
            contract_device=device,
            defaults={
                "title": title,
                "created_at": timezone.now(),
                "status_name": "Открыта",
                "author_name": okdesk_author or context.user.username,
                "serial_numbers": device.serial_number or "",
                "company_name": device.organization.name if device.organization_id else "",
                "source": OkdeskIssue.SOURCE_CREATED,
                "created_by": context.user,
                "synced_at": timezone.now(),
            },
        )
        return str(issue_id)

    def reply(self, service_request, text, attachments=(), *, user=None, to_email="", cc=()):
        # Переиспользуем отправку комментария с панели Okdesk: то же право,
        # тот же личный токен — комментарий уходит от имени пользователя.
        from integrations.services_okdesk_send import OkdeskSendError, post_comment_to_okdesk

        if user is None or not user.has_perm("integrations.post_okdesk_comment"):
            raise SubmissionError("Нет права на отправку комментариев в Okdesk.", status=403)
        if attachments:
            raise SubmissionError(
                "Вложения в комментарий Okdesk из журнала не отправляются — приложите файл в самом Okdesk.",
                status=400,
            )

        issue_id = (service_request.external_number or "").strip()
        if not issue_id.isdigit():
            raise SubmissionError("У заявки нет номера обращения Okdesk — ответить некуда.", status=409)

        try:
            comment = post_comment_to_okdesk(user, int(issue_id), text)
        except OkdeskSendError as exc:
            raise SubmissionError(str(exc), status=exc.status_code)

        # external_id = id комментария Okdesk: периодический синк (services_okdesk_import)
        # увидит его в ленте и не создаст дубль
        record = ServiceRequestMessage.objects.create(
            service_request=service_request,
            channel=self.code,
            direction=ServiceRequestMessage.OUTGOING,
            external_id=str(comment["id"]),
            from_email=f"{user.last_name} {user.first_name}".strip() or user.username,
            body_text=text,
            sent_at=timezone.now(),
        )
        logger.info(
            "Заявка %s: комментарий отправлен в Okdesk #%s пользователем %s", service_request.number, issue_id, user
        )
        return record


class EmailChannel(SubmissionChannel):
    code = ServiceProvider.EMAIL

    def send(self, service_request, context):
        recipient = service_request.device.support_email
        if not recipient:
            provider = service_request.service_provider.name if service_request.service_provider_id else "не указан"
            raise SubmissionError(
                f"У подрядчика «{provider}» не задана почта сервис-деска — заявку по этому устройству "
                f"нужно подавать другим способом.",
                status=409,
            )

        html, text = build_description(service_request, context)

        # Подсказка про закрытие: точная тема из п. 6.6.4 ТЗ, по которой сработает
        # автозакрытие (close_by_letter ищет основы «работоспособн»/«восстановлен» + акт во вложении).
        closing_subject = f"Заявка № {service_request.number}. Работоспособность Оборудования восстановлена"
        text += (
            "\n\n---\n"
            "Когда работы будут выполнены, ответьте на это письмо с темой:\n"
            f"{closing_subject}\n"
            "и приложите скан или фото акта выполненных работ — заявка закроется автоматически."
        )
        html += (
            '<hr><p style="color:#6c757d;font-size:13px">'
            "Когда работы будут выполнены, ответьте на это письмо с темой:<br>"
            f"<b>{closing_subject}</b><br>"
            "и приложите скан или фото акта выполненных работ — заявка закроется автоматически.</p>"
        )

        subject = build_title(service_request, context)
        sender = settings.SERVICE_DESK_EMAIL or settings.DEFAULT_FROM_EMAIL

        if settings.SERVICE_DESK_EMAIL:
            # Ответ подрядчика должен попасть в общий ящик — только оттуда его заберёт
            # приём почты. Инициатор идёт в копию, чтобы переписку видел и он.
            reply_to = [settings.SERVICE_DESK_EMAIL]
            cc = [context.user.email] if context.user.email else None
        else:
            # Общего ящика нет: ответ уходит инициатору лично и в переписку не попадёт,
            # но это лучше, чем ответ на noreply.
            reply_to = [context.user.email] if context.user.email else None
            cc = None

        # Message-ID присваиваем сами: по нему узнаётся ответ, если подрядчик
        # напишет со своей темой без нашего номера заявки.
        message_id = make_msgid(domain=sender.rsplit("@", 1)[-1] or None)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=sender,
            to=[recipient],
            cc=cc,
            reply_to=reply_to,
            headers={"Message-ID": message_id},
        )
        message.attach_alternative(html, "text/html")

        try:
            message.send()
        except OSError as exc:
            logger.exception("Не удалось отправить письмо-заявку: %s", exc)
            raise SubmissionError(f"Почтовый сервер недоступен: {exc}. Попробуйте повторить позже.", retry=True)

        ServiceRequestMessage.objects.create(
            service_request=service_request,
            channel=self.code,
            direction=ServiceRequestMessage.OUTGOING,
            external_id=message_id,
            subject=subject,
            from_email=sender,
            to_emails=", ".join([recipient, *(cc or [])]),
            body_text=text,
            sent_at=timezone.now(),
        )
        return ""

    def reply(self, service_request, text, attachments=(), *, user=None, to_email="", cc=()):
        thread = list(service_request.messages.all())

        # По умолчанию отвечаем тому, кто написал последним: заявку принимает
        # сервис-деск, а ведёт её потом конкретный сотрудник со своего адреса.
        # Явный to_email проверен по белому списку адресов переписки во view.
        answered = [item.from_email for item in thread if item.direction == ServiceRequestMessage.INCOMING]
        recipient = to_email or (parseaddr(answered[-1])[1] if answered else service_request.device.support_email)
        if not recipient:
            raise SubmissionError("Некому отвечать: у подрядчика не задана почта сервис-деска.", status=409)
        cc = list(cc)

        # Ответы уходят с общего адреса сервис-деска, поэтому подписываем автора:
        # подрядчику видно, с кем именно он ведёт переписку
        if user is not None:
            fio = f"{user.last_name} {user.first_name}".strip() or user.username
            signature = [f"С уважением, {fio}"]
            phone = getattr(getattr(user, "profile", None), "phone", "")
            if phone:
                signature.append(phone)
            text = text.rstrip() + "\n\n" + "\n".join(signature)

        # Тема с нашим номером, а не «Re:» на тему подрядчика: по номеру узнаётся следующий ответ
        original = next(
            (item.subject for item in thread if item.direction == ServiceRequestMessage.OUTGOING and item.subject),
            f"Заявка № {service_request.number}",
        )
        subject = original if original.lower().startswith("re:") else f"Re: {original}"

        sender = settings.SERVICE_DESK_EMAIL or settings.DEFAULT_FROM_EMAIL
        message_id = make_msgid(domain=sender.rsplit("@", 1)[-1] or None)
        headers = {"Message-ID": message_id}
        last_external_id = next((item.external_id for item in reversed(thread) if item.external_id), "")
        if last_external_id:
            headers["In-Reply-To"] = last_external_id
            headers["References"] = last_external_id

        # Файл читаем один раз: он нужен и письму, и ленте
        payloads = [
            (upload.name, upload.read(), upload.content_type or "application/octet-stream") for upload in attachments
        ]

        letter = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=sender,
            to=[recipient],
            cc=cc or None,
            reply_to=[settings.SERVICE_DESK_EMAIL] if settings.SERVICE_DESK_EMAIL else None,
            headers=headers,
        )
        for filename, content, content_type in payloads:
            letter.attach(filename, content, content_type)

        try:
            letter.send()
        except OSError as exc:
            logger.exception("Не удалось отправить ответ по заявке %s: %s", service_request.number, exc)
            raise SubmissionError(f"Почтовый сервер недоступен: {exc}. Попробуйте повторить позже.", retry=True)

        record = ServiceRequestMessage.objects.create(
            service_request=service_request,
            channel=self.code,
            direction=ServiceRequestMessage.OUTGOING,
            external_id=message_id,
            in_reply_to=last_external_id,
            subject=subject,
            from_email=sender,
            to_emails=", ".join([recipient, *cc]),
            body_text=text,
            sent_at=timezone.now(),
        )
        for filename, content, content_type in payloads:
            attachment = ServiceRequestAttachment(
                message=record, filename=filename[:255], content_type=content_type[:100], size=len(content)
            )
            attachment.file.save(filename, ContentFile(content), save=False)
            attachment.save()

        logger.info("Заявка %s: ответ отправлен на %s пользователем %s", service_request.number, recipient, user)
        return record

    def fetch(self):
        from .services_mail import fetch_service_desk_mail

        return fetch_service_desk_mail()


class JournalChannel(SubmissionChannel):
    """Заявка живёт только у нас: регистрируется, нумеруется, считается в K1/K2.

    Режим для подрядчика, с которым канал ещё не согласован: журнал уже ведём,
    а в его систему ничего не пишем.
    """

    code = ServiceProvider.JOURNAL
    collects_urgency = False

    def send(self, service_request, context):
        logger.info("Заявка %s осталась в журнале: подрядчику не отправляем", service_request.number)
        return ""


CHANNELS = {channel.code: channel for channel in (OkdeskChannel, EmailChannel, JournalChannel)}


def fetch_provider_messages():
    """Забирает новые сообщения по всем каналам, которыми пользуются активные подрядчики."""
    trackers = ServiceProvider.objects.filter(is_active=True).values_list("issue_tracker", flat=True).distinct()

    stats = {}
    for tracker in trackers:
        channel = CHANNELS.get(tracker)
        if channel is not None:
            stats[tracker] = channel().fetch()
    return stats


def collects_urgency(device):
    """Спрашивать ли срочность: канал должен уметь её передать, а подрядчик — согласиться на норматив."""
    if not device.service_provider_id:
        return False
    channel = CHANNELS.get(device.service_provider.issue_tracker)
    if channel is None or not channel.collects_urgency:
        return False
    return device.service_provider.collects_urgency


def channel_for_device(device):
    """Канал подачи заявки по подрядчику устройства."""
    if not device.service_provider_id:
        raise SubmissionError("У устройства не указан подрядчик — непонятно, куда подавать заявку.", status=409)

    channel = CHANNELS.get(device.service_provider.issue_tracker)
    if channel is None:
        raise SubmissionError(
            f"У подрядчика «{device.service_provider.name}» не настроен приём заявок — " f"подайте заявку вручную.",
            status=409,
        )
    return channel()


# ─── Точка входа ──────────────────────────────────────────────────────────────


def submit_service_request(device_id, description, context, **journal_fields):
    """Регистрирует заявку в журнале и передаёт её подрядчику.

    Journal_fields принимает признаки заявки: stops_printing, counts_in_sla, is_critical,
    initiator_contacts. При ошибке доставки запись журнала откатывается — заявки,
    которую подрядчик не получил, в показателях быть не должно.
    """
    try:
        device = ContractDevice.objects.select_related(
            "organization", "city", "model__manufacturer", "service_provider"
        ).get(pk=device_id)
    except ContractDevice.DoesNotExist:
        raise SubmissionError("Устройство не найдено", status=404)

    channel = channel_for_device(device)
    if not collects_urgency(device):
        # Форму срочности такому подрядчику не показывают — на присланные флаги не полагаемся
        for flag in ("stops_printing", "counts_in_sla", "is_critical"):
            journal_fields.pop(flag, None)

    with transaction.atomic():
        service_request = ServiceRequest.objects.create(
            device=device,
            service_provider=device.service_provider,
            description=description,
            initiator=context.user,
            registered_at=timezone.now(),
            **journal_fields,
        )
        service_request.external_number = channel.send(service_request, context)
        if service_request.external_number:
            service_request.save(update_fields=["external_number", "updated_at"])

        # Ответ подрядчика адресован инициатору — он следит за заявкой по умолчанию
        if context.user is not None:
            ServiceRequestSubscription.objects.create(user=context.user, service_request=service_request)

    logger.info("Заявка %s по устройству %s передана каналом %s", service_request.number, device.pk, channel.code)
    return service_request
