"""
Выбор канала подачи заявки.

Подрядчиков несколько, и заявка по устройству уходит туда, где его обслуживают:
у одного это Okdesk, у другого — сервис-деск M4. Канал определяется полем
`ServiceProvider.issue_tracker`, а не настройками, потому что в одном договоре
устройства могут быть у разных подрядчиков.
"""

import logging

from contracts.models import ServiceProvider

from .m4 import services as m4_services
from .m4.errors import M4Error
from .services_okdesk_issue import create_issue_for_device
from .services_okdesk_send import OkdeskSendError

logger = logging.getLogger(__name__)

# Обе ошибки несут status_code для HTTP-ответа — вьюхе достаточно поймать этот кортеж.
DispatchError = (OkdeskSendError, M4Error)


def _remember_phone(user, phone: str):
    """Телефон заявителя переиспользуется в следующих заявках, независимо от канала."""
    if not phone:
        return

    from access.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.phone != phone:
        profile.phone = phone
        profile.save(update_fields=["phone", "updated_at"])


def dispatch_service_request(user, device, *, cartridge="", service_type="Обслуживание", comment="", phone="") -> dict:
    """Отправляет заявку подрядчику, который обслуживает устройство.

    Возвращает словарь с ключом канала и внешним номером заявки: своего номера
    у заявки нет, идентификатор всегда выдаёт система подрядчика.
    """
    provider = device.service_provider
    if provider is None:
        raise OkdeskSendError(
            "У устройства не указан подрядчик — некуда подавать заявку. Обратитесь к администратору.",
            status_code=409,
        )
    if not provider.is_active:
        raise OkdeskSendError(f"Подрядчик «{provider.name}» отключён — заявки по нему не принимаются.", 409)

    _remember_phone(user, phone)
    payload = {
        "cartridge": cartridge,
        "service_type": service_type,
        "comment": comment,
        "phone": phone,
    }

    if provider.issue_tracker == ServiceProvider.OKDESK:
        result = create_issue_for_device(user, device, **payload)
        return {"channel": ServiceProvider.OKDESK, "issue_id": result["issue_id"]}

    if provider.issue_tracker == ServiceProvider.M4:
        result = m4_services.create_task_for_device(user, device, **payload)
        return {"channel": ServiceProvider.M4, "issue_id": result["task_id"]}

    raise OkdeskSendError(
        f"У подрядчика «{provider.name}» не подключён приём заявок. Обратитесь к администратору.",
        status_code=409,
    )
