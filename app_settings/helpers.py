import os
from typing import Any, Optional
from .models import AppSetting


def get_setting(key: str, default: Any = None, use_env_fallback: bool = True) -> Any:
    """
    Получить значение настройки с fallback на .env и default.

    Порядок приоритета:
    1. Активная настройка из БД
    2. Переменная окружения (если use_env_fallback=True)
    3. Значение default

    Args:
        key: Ключ настройки
        default: Значение по умолчанию
        use_env_fallback: Использовать .env как fallback

    Returns:
        Значение настройки
    """
    # Пробуем получить из БД
    db_value = AppSetting.get(key)
    if db_value is not None:
        return db_value

    # Fallback на .env
    if use_env_fallback:
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value

    # Fallback на default
    return default


def get_settings_dict(category: Optional[str] = None) -> dict:
    """
    Получить словарь всех настроек (или по категории).

    Args:
        category: Категория настроек (опционально)

    Returns:
        dict: {key: value}
    """
    return AppSetting.get_all(category=category)


def is_keycloak_enabled() -> bool:
    """Проверка, настроен ли Keycloak"""
    client_id = get_setting('OIDC_CLIENT_ID', '')
    client_secret = get_setting('OIDC_CLIENT_SECRET', '')
    return bool(client_id and client_secret)