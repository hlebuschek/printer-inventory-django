"""Создание заявок подрядчику в M4 по устройству из договора."""

import logging

from django.utils import timezone

from ..models import M4Issue
from .client import M4Client
from .errors import M4Error

logger = logging.getLogger(__name__)


def build_title(device, service_type: str) -> str:
    city = device.city.name if device.city else ""
    parts = [p for p in (f"Заявка на {service_type.lower()}", city, device.serial_number) if p]
    return ". ".join(parts)


def build_description(device, *, cartridge: str, service_type: str, comment: str, requester: str, phone: str) -> str:
    """Тело заявки простым текстом: как M4 отрисует HTML — неизвестно, а текст читается всегда."""
    manufacturer = device.model.manufacturer.name if device.model and device.model.manufacturer else ""
    rows = [
        ("Организация", device.organization.name if device.organization else ""),
        ("Город", device.city.name if device.city else ""),
        ("Адрес", device.address or ""),
        ("Кабинет", device.room_number or ""),
        ("Производитель", manufacturer),
        ("Модель", device.model.name if device.model else ""),
        ("Серийный номер", device.serial_number or ""),
        ("Картридж", cartridge),
        ("Ремонт/обслуживание", service_type),
        ("Комментарий", comment),
        ("Заявитель", requester),
        ("Телефон", phone),
    ]
    return "\n".join(f"{label}: {value}" for label, value in rows if value)


def build_task_params(device, *, title: str, description: str, requester: str, phone: str) -> dict:
    """Собирает params для M4CreateTask. Обязательны только caption и fullcaption."""
    params = {
        "caption": title,
        "fullcaption": description,
    }

    # locationId не знаем: справочник объектов M4 с нашими адресами не сопоставлен.
    # По документации M4 сам заведёт объект по адресу и привяжет его к заявке.
    if device.address:
        params["address"] = device.address

    contact = {}
    if requester:
        contact["name"] = requester
    if phone:
        contact["phone"] = phone
    if contact:
        params["contactPerson"] = contact

    return params


def create_task_for_device(user, device, *, cartridge="", service_type="Обслуживание", comment="", phone="") -> dict:
    """Создаёт заявку в M4 и сохраняет её локально. Возвращает {"task_id": ...}."""
    provider = device.service_provider
    requester = f"{user.last_name} {user.first_name}".strip() or user.username

    title = build_title(device, service_type)
    description = build_description(
        device,
        cartridge=cartridge,
        service_type=service_type,
        comment=comment,
        requester=requester,
        phone=phone,
    )
    params = build_task_params(device, title=title, description=description, requester=requester, phone=phone)

    result = M4Client(user=user, provider=provider).call("M4CreateTask", params)
    task_id = result.get("taskId")
    if not task_id:
        raise M4Error("M4 принял заявку, но не вернул её номер (result.taskId).")

    now = timezone.now()
    M4Issue.objects.update_or_create(
        task_id=int(task_id),
        defaults={
            "title": title,
            "contract_device": device,
            "serial_number": device.serial_number or "",
            "created_at": now,
            "synced_at": now,
            "created_by": user,
            "author_name": requester,
        },
    )
    logger.info("M4: заявка #%s создана пользователем %s по устройству %s", task_id, user.username, device.pk)
    return {"task_id": int(task_id)}
