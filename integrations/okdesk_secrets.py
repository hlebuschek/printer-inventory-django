"""Скрытие api_token в текстах ошибок Okdesk.

Okdesk принимает токен только query-параметром, а requests кладёт полный URL
в сообщение исключения (HTTPError, ConnectionError, таймауты). Без маскировки
такой текст уносит рабочий токен в общий лог и в тела ответов API, где его
читает любой пользователь с правом на просмотр заявок.
"""

import re

_TOKEN_RE = re.compile(r"(api_token=)[^&\s\"'<>]+", re.IGNORECASE)


def mask_api_token(value) -> str:
    """Заменяет значение api_token в произвольном тексте на «***»."""
    return _TOKEN_RE.sub(r"\1***", str(value))
