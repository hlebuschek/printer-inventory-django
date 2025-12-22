"""
GLPI REST API клиент.

Поддерживает:
- Аутентификацию через user_token или app_token
- Поиск принтеров по серийному номеру
- Получение детальной информации о принтере
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class GLPIAPIError(Exception):
    """Базовое исключение для ошибок GLPI API"""
    pass


class GLPIAuthError(GLPIAPIError):
    """Ошибка аутентификации"""
    pass


class GLPIClient:
    """
    Клиент для работы с GLPI REST API.

    Использование:
        client = GLPIClient()
        results = client.search_printer_by_serial('ABC123')
    """

    def __init__(
        self,
        url: Optional[str] = None,
        app_token: Optional[str] = None,
        user_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Инициализация клиента GLPI.

        Args:
            url: URL GLPI API (например, https://glpi.company.com/apirest.php)
            app_token: Токен приложения (если используется)
            user_token: Токен пользователя (для аутентификации)
            username: Имя пользователя (альтернатива user_token)
            password: Пароль (альтернатива user_token)
        """
        self.url = url or getattr(settings, 'GLPI_API_URL', None)
        self.app_token = app_token or getattr(settings, 'GLPI_APP_TOKEN', None)
        self.user_token = user_token or getattr(settings, 'GLPI_USER_TOKEN', None)
        self.username = username or getattr(settings, 'GLPI_USERNAME', None)
        self.password = password or getattr(settings, 'GLPI_PASSWORD', None)

        if not self.url:
            raise GLPIAPIError("GLPI API URL не настроен. Установите GLPI_API_URL в settings.py или .env")

        # Session token будет получен при первом запросе
        self.session_token: Optional[str] = None

    def _get_headers(self, with_session: bool = False) -> Dict[str, str]:
        """Формирует заголовки для запроса"""
        headers = {
            'Content-Type': 'application/json',
        }

        if self.app_token:
            headers['App-Token'] = self.app_token

        if with_session and self.session_token:
            headers['Session-Token'] = self.session_token

        return headers

    def init_session(self) -> str:
        """
        Инициализирует сессию с GLPI API.

        Returns:
            Session token

        Raises:
            GLPIAuthError: Если аутентификация не удалась
        """
        headers = self._get_headers()

        # Используем либо user_token, либо basic auth
        if self.user_token:
            headers['Authorization'] = f'user_token {self.user_token}'
        elif self.username and self.password:
            auth = (self.username, self.password)
        else:
            raise GLPIAuthError(
                "Необходимо указать либо user_token, либо username/password для аутентификации"
            )

        try:
            response = requests.get(
                f"{self.url}/initSession",
                headers=headers,
                auth=auth if (self.username and self.password) else None,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')
                logger.info(f"GLPI session initialized successfully")
                return self.session_token
            else:
                error_msg = response.json().get('message', response.text)
                raise GLPIAuthError(f"Ошибка аутентификации GLPI: {error_msg}")

        except requests.RequestException as e:
            logger.error(f"Ошибка подключения к GLPI API: {e}")
            raise GLPIAPIError(f"Не удалось подключиться к GLPI API: {e}")

    def kill_session(self):
        """Завершает сессию с GLPI API"""
        if not self.session_token:
            return

        try:
            response = requests.get(
                f"{self.url}/killSession",
                headers=self._get_headers(with_session=True),
                timeout=10
            )
            if response.status_code == 200:
                logger.info("GLPI session killed successfully")
            self.session_token = None
        except requests.RequestException as e:
            logger.warning(f"Ошибка при завершении GLPI сессии: {e}")

    def _ensure_session(self):
        """Гарантирует наличие активной сессии"""
        if not self.session_token:
            self.init_session()

    def search_printer_by_serial(self, serial_number: str) -> Tuple[str, List[Dict], Optional[str]]:
        """
        Ищет принтер в GLPI по серийному номеру.

        Args:
            serial_number: Серийный номер для поиска

        Returns:
            Tuple из:
            - status: 'NOT_FOUND', 'FOUND_SINGLE', 'FOUND_MULTIPLE', 'ERROR'
            - list: Список найденных принтеров (каждый с полями id, name, serial, ...)
            - error: Сообщение об ошибке (если есть)
        """
        self._ensure_session()

        try:
            import json

            # GLPI API endpoint для поиска
            # Используем search endpoint с criteria в query параметрах
            # Формат: ?criteria[0][field]=5&criteria[0][searchtype]=equals&criteria[0][value]=SERIAL

            url = f"{self.url}/search/Printer"

            # Правильный формат query параметров для GLPI
            query_params = {
                'criteria[0][field]': '5',  # Поле serial
                'criteria[0][searchtype]': 'equals',
                'criteria[0][value]': serial_number,
                'forcedisplay[0]': '1',   # name
                'forcedisplay[1]': '5',   # serial
                'forcedisplay[2]': '23',  # manufacturer
                'forcedisplay[3]': '31',  # model
            }

            logger.info(f"=== GLPI Search Request ===")
            logger.info(f"URL: {url}")
            logger.info(f"Serial: {serial_number}")
            logger.info(f"Query params: {query_params}")

            response = requests.get(
                url,
                headers=self._get_headers(with_session=True),
                params=query_params,
                timeout=15
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response text (first 500 chars): {response.text[:500]}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"Parsed JSON successfully: {data}")
                except ValueError as json_err:
                    logger.error(f"Failed to parse JSON from 200 response: {json_err}")
                    logger.error(f"Full response text: {response.text}")
                    return ('ERROR', [], f"GLPI вернул некорректный JSON: {str(json_err)}")

                total_count = data.get('totalcount', 0)
                items = data.get('data', [])

                if total_count == 0:
                    return ('NOT_FOUND', [], None)
                elif total_count == 1:
                    return ('FOUND_SINGLE', items, None)
                else:
                    return ('FOUND_MULTIPLE', items, None)
            else:
                logger.warning(f"GLPI returned non-200 status: {response.status_code}")
                try:
                    error_msg = response.json().get('message', response.text) if response.text else 'Unknown error'
                except ValueError:
                    logger.error(f"Failed to parse error JSON. Raw text: {response.text}")
                    error_msg = response.text or 'Unknown error'

                logger.error(f"GLPI search error: {error_msg}")
                return ('ERROR', [], f"Ошибка GLPI API: {error_msg}")

        except requests.RequestException as e:
            logger.error(f"Ошибка при поиске в GLPI: {e}")
            return ('ERROR', [], f"Ошибка подключения: {str(e)}")
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при поиске в GLPI: {e}")
            return ('ERROR', [], f"Неожиданная ошибка: {str(e)}")

    def get_printer(self, printer_id: int) -> Optional[Dict]:
        """
        Получает детальную информацию о принтере по ID.

        Args:
            printer_id: ID принтера в GLPI

        Returns:
            Словарь с данными принтера или None при ошибке
        """
        self._ensure_session()

        try:
            response = requests.get(
                f"{self.url}/Printer/{printer_id}",
                headers=self._get_headers(with_session=True),
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения принтера {printer_id}: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Ошибка при получении данных принтера: {e}")
            return None

    def __enter__(self):
        """Context manager support"""
        self.init_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.kill_session()
        return False
