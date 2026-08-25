"""
Авторизация в M4.

По документации у M4 ровно один способ: заголовок `Authorization: Bearer <token>`.
Токен берём в порядке приоритета:

1. Личный токен пользователя (`access.UserM4Token`) — заявка создаётся от его имени.
2. Служебный токен подключения — для работы без пользователя, когда собираем заявки и статусы.

Адрес сервис-деска лежит в `integrations.M4Connection` подрядчика: подрядчиков на M4 может
быть несколько, и URL у каждого свой. Из токена его не вывести, поэтому он обязателен.
"""

import logging
from dataclasses import dataclass

from .errors import M4NotConfigured

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class M4Credentials:
    """Токен и базовый URL, которых достаточно для вызова любого метода."""

    token: str
    api_url: str


def get_connection(provider):
    """Подключение подрядчика к M4. Без него подавать заявку некуда."""
    from ..models import M4Connection

    if provider is None:
        raise M4NotConfigured("Не указан подрядчик, которому подаётся заявка.")

    try:
        return M4Connection.objects.get(provider=provider)
    except M4Connection.DoesNotExist:
        raise M4NotConfigured(f"Для подрядчика «{provider.name}» не заведено подключение к M4.")


def _personal_token(user) -> str:
    """Личный токен пользователя, если он его сохранил. Отсутствие — не ошибка."""
    if user is None or not getattr(user, "is_authenticated", False):
        return ""

    from access.models import UserM4Token

    try:
        return UserM4Token.objects.get(user=user).get_token()
    except UserM4Token.DoesNotExist:
        return ""


def missing_credentials(user, provider) -> str:
    """Чего не хватает для подачи заявки. Пустая строка — всё на месте.

    Причин ровно две, и чинят их разные люди: подключение заводит администратор,
    личный токен — сам пользователь. Интерфейсу нужно понимать, кому жаловаться.
    """
    try:
        connection = get_connection(provider)
    except M4NotConfigured as exc:
        return str(exc)

    if not connection.api_url:
        return f"У подключения «{connection.provider.name}» не заполнен адрес сервис-деска M4."
    if _personal_token(user) or connection.encrypted_token:
        return ""
    return "Нет токена M4: добавьте личный токен в меню пользователя."


def has_credentials(user, provider) -> bool:
    """Есть ли чем авторизоваться в M4. Нужно интерфейсу, чтобы не показывать заведомо нерабочую форму."""
    return not missing_credentials(user, provider)


def get_credentials(user=None, provider=None) -> M4Credentials:
    """Возвращает токен и базовый URL для вызовов M4 конкретного подрядчика."""
    connection = get_connection(provider)

    if not connection.api_url:
        raise M4NotConfigured(f"У подключения «{connection.provider.name}» не заполнен адрес сервис-деска M4.")

    token = _personal_token(user) or connection.get_token()
    if not token:
        raise M4NotConfigured("Нет токена M4: добавьте личный токен в меню пользователя.")

    return M4Credentials(token=token, api_url=connection.api_url.rstrip("/"))
