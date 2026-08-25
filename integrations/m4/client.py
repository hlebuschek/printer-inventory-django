"""
Клиент M4.

У M4 не REST, а JSON-RPC 2.0: все методы уходят POST-ом на один и тот же базовый URL
сервис-деска, а имя метода передаётся в теле, в поле `method`. Никаких `/M4CreateTask`
в пути быть не должно.
"""

import itertools
import logging

import requests
from django.conf import settings

from . import auth
from .errors import M4AuthError, M4Error

logger = logging.getLogger(__name__)

_request_ids = itertools.count(1)


class M4Client:
    """Вызовы методов M4 от имени пользователя или по служебному токену подрядчика.

    client = M4Client(user=request.user, provider=device.service_provider)
    result = client.call("M4GetTaskType", {})
    """

    def __init__(self, user=None, provider=None, credentials: auth.M4Credentials | None = None):
        self._user = user
        self._provider = provider
        self._credentials = credentials

    @property
    def credentials(self) -> auth.M4Credentials:
        if self._credentials is None:
            self._credentials = auth.get_credentials(self._user, self._provider)
        return self._credentials

    def call(self, method: str, params: dict | None = None) -> dict:
        """Вызывает метод M4 и возвращает содержимое result."""
        response = self._post(method, params or {})

        # Перевыпустить токен за пользователя нельзя: своего логина и пароля у нас нет.
        if response.status_code == 401:
            raise M4AuthError("M4 отклонил токен. Обновите его в меню пользователя.")
        if not response.ok:
            raise M4Error(f"M4 ответил HTTP {response.status_code} на метод {method}.")

        try:
            payload = response.json() or {}
        except ValueError:
            raise M4Error(f"M4 вернул не JSON на метод {method}.")

        error = payload.get("error")
        if error:
            code = error.get("code")
            message = error.get("message") or "без описания"
            raise M4Error(f"M4 вернул ошибку по методу {method}: {message} (код {code}).")

        return payload.get("result") or {}

    def _post(self, method: str, params: dict):
        body = {
            "jsonrpc": "2.0",
            "id": next(_request_ids),
            "method": method,
            "params": params,
        }
        try:
            return requests.post(
                self.credentials.api_url,
                json=body,
                headers={"Authorization": f"Bearer {self.credentials.token}"},
                verify=getattr(settings, "M4_VERIFY_SSL", True),
                timeout=getattr(settings, "M4_TIMEOUT", (5, 20)),
            )
        except requests.Timeout:
            raise M4Error("Сервер M4 не отвечает. Попробуйте повторить через несколько минут.", 504)
        except requests.ConnectionError:
            raise M4Error("Нет соединения с M4. Проверьте сеть и попробуйте позже.", 502)
