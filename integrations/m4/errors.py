"""Ошибки интеграции с M4. status_code уходит в HTTP-ответ вьюхи."""


class M4Error(Exception):
    """Базовая ошибка интеграции. Текст показывается пользователю."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class M4NotConfigured(M4Error):
    """Не хватает настроек или учётных данных — чинится администратором, не пользователем."""

    def __init__(self, message: str):
        super().__init__(message, status_code=503)


class M4AuthError(M4Error):
    """M4 не принял учётные данные."""

    def __init__(self, message: str):
        super().__init__(message, status_code=403)
