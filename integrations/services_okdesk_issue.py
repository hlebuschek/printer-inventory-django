"""Создание заявок в Okdesk по устройству из договора.

Раньше жило прямо во вьюхе; вынесено сюда, когда каналов подачи стало больше одного.
"""

import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

from .models import OkdeskIssue
from .services_okdesk_send import OkdeskSendError

logger = logging.getLogger(__name__)


def _api_url():
    return getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")


def _user_token(user):
    from access.models import UserOkdeskToken

    try:
        return UserOkdeskToken.objects.get(user=user).get_token()
    except UserOkdeskToken.DoesNotExist:
        raise OkdeskSendError(
            "API-токен Okdesk не настроен. Добавьте его в меню пользователя → Токен Okdesk.",
            status_code=403,
        )


def build_description(device, *, cartridge: str, service_type: str, comment: str, signature: str) -> str:
    """HTML-таблица по паттерну письма. escape() защищает от инъекций в сторонней системе."""
    org = escape(device.organization.name) if device.organization else ""
    city = escape(device.city.name) if device.city else ""
    manufacturer = escape(device.model.manufacturer.name) if device.model and device.model.manufacturer else ""
    model = escape(device.model.name) if device.model else ""

    return f"""
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
  <thead>
    <tr>
      <th>№</th>
      <th>Организация</th>
      <th>Город</th>
      <th>Адрес</th>
      <th>Кабинет</th>
      <th>Производитель</th>
      <th>Модель</th>
      <th>Серийный номер</th>
      <th>Картридж</th>
      <th>Ремонт/обслуживание</th>
      <th>Комментарии</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>{org}</td>
      <td>{city}</td>
      <td>{escape(device.address or "")}</td>
      <td>{escape(device.room_number or "")}</td>
      <td>{manufacturer}</td>
      <td>{model}</td>
      <td>{escape(device.serial_number or "")}</td>
      <td>{escape(cartridge)}</td>
      <td>{escape(service_type)}</td>
      <td>{escape(comment)}</td>
    </tr>
  </tbody>
</table>
<br>
<br>
<p>{signature}</p>
"""


def create_issue_for_device(user, device, *, cartridge="", service_type="Обслуживание", comment="", phone="") -> dict:
    """Создаёт заявку в Okdesk от имени пользователя. Возвращает {"issue_id": ...}."""
    token = _user_token(user)

    full_fio = f"{user.last_name} {user.first_name}".strip() or user.username
    signature_parts = [f"С уважением, {escape(full_fio)}"]
    if phone:
        signature_parts.append(escape(phone))

    description = build_description(
        device,
        cartridge=cartridge,
        service_type=service_type,
        comment=comment,
        signature="<br>".join(signature_parts),
    )
    city = escape(device.city.name) if device.city else ""
    title = f"Заявка на {escape(service_type).lower()}. {city}. {escape(device.serial_number or '')}"

    try:
        resp = requests.post(
            f"{_api_url()}/issues/",
            params={"api_token": token},
            json={"issue": {"title": title, "description": description}},
            verify=getattr(settings, "OKDESK_VERIFY_SSL", True),
            timeout=15,
        )
    except requests.Timeout:
        raise OkdeskSendError("Сервер Okdesk не отвечает. Попробуйте повторить через несколько минут.", 504)
    except requests.ConnectionError:
        raise OkdeskSendError("Нет соединения с сервером Okdesk. Проверьте сеть и попробуйте позже.", 502)
    except requests.RequestException as exc:
        logger.exception("Ошибка при создании заявки в Okdesk: %s", exc)
        raise OkdeskSendError(f"Ошибка API Okdesk: {exc}. Попробуйте повторить позже.", 502)

    if resp.status_code == 401:
        raise OkdeskSendError("Неверный API-токен Okdesk. Обновите токен в меню пользователя.", status_code=403)
    if not resp.ok:
        raise OkdeskSendError(f"Okdesk API ответил HTTP {resp.status_code}.", status_code=502)

    issue_id = (resp.json() or {}).get("id")
    if not issue_id:
        raise OkdeskSendError("Okdesk принял заявку, но не вернул её номер.", status_code=502)

    # Формат автора в Okdesk — "Фамилия Имя", без отчества.
    first_name_only = (user.first_name or "").split()[0] if user.first_name else ""
    author_name = f"{user.last_name} {first_name_only}".strip() or user.username

    OkdeskIssue.objects.update_or_create(
        issue_id=issue_id,
        contract_device=device,
        defaults={
            "title": title,
            "created_at": timezone.now(),
            "status_name": "Открыта",
            "author_name": author_name,
            "serial_numbers": device.serial_number or "",
            "company_name": escape(device.organization.name) if device.organization else "",
            "source": OkdeskIssue.SOURCE_CREATED,
            "created_by": user,
            "synced_at": timezone.now(),
        },
    )
    logger.info("Okdesk: заявка #%s создана пользователем %s по устройству %s", issue_id, user.username, device.pk)
    return {"issue_id": issue_id}
