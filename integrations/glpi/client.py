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
        password: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        recursive: Optional[bool] = None,
        entities_id: Optional[str] = None,
        contract_field_name: Optional[str] = None,
        contract_resource_name: Optional[str] = None
    ):
        """
        Инициализация клиента GLPI.

        Args:
            url: URL GLPI API (например, https://glpi.company.com/apirest.php)
            app_token: Токен приложения (если используется)
            user_token: Токен пользователя (для аутентификации)
            username: Имя пользователя (альтернатива user_token)
            password: Пароль (альтернатива user_token)
            verify_ssl: Проверять SSL сертификат (по умолчанию True)
            recursive: Рекурсивный просмотр entities (для GLPI v10, по умолчанию True)
            entities_id: ID entity или 'all' (по умолчанию 'all')
            contract_field_name: Имя Plugin Field для обновления договора (по умолчанию из settings)
            contract_resource_name: Имя ресурса PluginFields для договора (по умолчанию из settings)
        """
        self.url = url or getattr(settings, 'GLPI_API_URL', None)
        self.app_token = app_token or getattr(settings, 'GLPI_APP_TOKEN', None)
        self.user_token = user_token or getattr(settings, 'GLPI_USER_TOKEN', None)
        self.username = username or getattr(settings, 'GLPI_USERNAME', None)
        self.password = password or getattr(settings, 'GLPI_PASSWORD', None)
        self.verify_ssl = verify_ssl if verify_ssl is not None else getattr(settings, 'GLPI_VERIFY_SSL', True)
        self.recursive = recursive if recursive is not None else getattr(settings, 'GLPI_RECURSIVE', True)
        self.entities_id = entities_id or getattr(settings, 'GLPI_ENTITIES_ID', 'all')
        self.contract_field_name = contract_field_name or getattr(settings, 'GLPI_CONTRACT_FIELD_NAME', '')
        self.contract_resource_name = contract_resource_name or getattr(settings, 'GLPI_CONTRACT_RESOURCE_NAME', '')

        if not self.url:
            raise GLPIAPIError("GLPI API URL не настроен. Установите GLPI_API_URL в settings.py или .env")

        # Валидация и нормализация URL
        self.url = self._normalize_url(self.url)

        # Отключаем предупреждения о непроверенных сертификатах
        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Session token будет получен при первом запросе
        self.session_token: Optional[str] = None

    def _normalize_url(self, url: str) -> str:
        """
        Валидация и нормализация GLPI API URL.

        Проверяет корректность URL и исправляет типичные ошибки.

        Args:
            url: URL для проверки

        Returns:
            Нормализованный URL

        Raises:
            GLPIAPIError: Если URL некорректен
        """
        url = url.strip()

        # Проверка наличия протокола
        if not url.startswith(('http://', 'https://')):
            raise GLPIAPIError(
                f"GLPI_API_URL должен начинаться с http:// или https://\n"
                f"Получено: {url}\n"
                f"Пример: https://glpi.company.com/apirest.php"
            )

        # Проверка что URL содержит слэш перед apirest.php
        # Типичная ошибка: https://hostnameapirest.php вместо https://hostname/apirest.php
        if 'apirest.php' in url and not '/apirest.php' in url:
            raise GLPIAPIError(
                f"GLPI_API_URL содержит ошибку: отсутствует слэш перед apirest.php\n"
                f"Получено: {url}\n"
                f"Должно быть: URL должен содержать /apirest.php (со слэшем)\n"
                f"Пример: https://glpi.company.com/apirest.php"
            )

        # Убираем trailing slash
        url = url.rstrip('/')

        # Логируем успешную валидацию для отладки
        logger.info(f"GLPI API URL validated: {url}")

        return url

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
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')

                # Изменяем active entities для доступа ко всей структуре (GLPI v10)
                if self.recursive or self.entities_id != 'all':
                    self.change_active_entities()

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
                timeout=10,
                verify=self.verify_ssl
            )
            self.session_token = None
        except requests.RequestException:
            # Игнорируем ошибки при завершении сессии
            self.session_token = None

    def change_active_entities(self):
        """
        Изменяет активную entity и режим рекурсии.

        Это необходимо для GLPI v10 для доступа ко всей структуре организации.
        По умолчанию API возвращает только данные из назначенной пользователю entity.

        Raises:
            GLPIAPIError: Если не удалось изменить entity
        """
        if not self.session_token:
            raise GLPIAPIError("Сессия не инициализирована. Сначала вызовите init_session()")

        try:
            # Параметры для изменения entity
            params = {
                'entities_id': self.entities_id,
                'is_recursive': self.recursive
            }

            response = requests.post(
                f"{self.url}/changeActiveEntities",
                headers=self._get_headers(with_session=True),
                json=params,
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                logger.info(f"GLPI: изменена active entity на '{self.entities_id}' (recursive={self.recursive})")
            else:
                # Не критичная ошибка - продолжаем работу
                logger.warning(f"GLPI: не удалось изменить active entity: {response.status_code}")

        except requests.RequestException as e:
            # Не критичная ошибка - продолжаем работу
            logger.warning(f"GLPI: ошибка при изменении active entity: {e}")

    def _ensure_session(self):
        """Гарантирует наличие активной сессии"""
        if not self.session_token:
            self.init_session()

    def search_printer_by_serial(self, serial_number: str) -> Tuple[str, List[Dict], Optional[str]]:
        """
        Ищет принтер в GLPI по серийному номеру.

        Поиск выполняется по полям (в порядке приоритета):
        1. Стандартное поле serial (ID=5) через /search/Printer
        2. Кастомное поле "серийный номер на бирке" (ID настраивается) через /search/Printer
        3. Fallback: поиск через /PluginFieldsPrinterx/ (если предыдущие не сработали)

        Args:
            serial_number: Серийный номер для поиска

        Returns:
            Tuple из:
            - status: 'NOT_FOUND', 'FOUND_SINGLE', 'FOUND_MULTIPLE', 'ERROR'
            - list: Список найденных принтеров
            - error: Сообщение об ошибке (если есть)
        """
        self._ensure_session()

        try:
            # Шаг 1: Поиск по стандартному полю serial (ID=5)
            serial_field_id = getattr(settings, 'GLPI_SERIAL_FIELD_ID', '5')

            query_params = {
                'criteria[0][field]': serial_field_id,
                'criteria[0][searchtype]': 'contains',
                'criteria[0][value]': serial_number,
                'forcedisplay[0]': '2',   # ID (IMPORTANT!)
                'forcedisplay[1]': '1',   # name
                'forcedisplay[2]': '5',   # serial
                'forcedisplay[3]': '23',  # manufacturer
                'forcedisplay[4]': '31',  # states_name (состояние: "в ремонте", "актив" и т.д.)
            }

            response = requests.get(
                f"{self.url}/search/Printer",
                headers=self._get_headers(with_session=True),
                params=query_params,
                timeout=15,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                total_count = data.get('totalcount', 0)

                if total_count > 0:
                    items = data.get('data', [])
                    if total_count == 1:
                        return ('FOUND_SINGLE', items, None)
                    else:
                        return ('FOUND_MULTIPLE', items, None)

            # Шаг 2: Поиск по кастомному полю "серийный номер на бирке" через /search/Printer
            label_serial_field_id = getattr(settings, 'GLPI_LABEL_SERIAL_FIELD_ID', '')

            if label_serial_field_id:
                logger.debug(f"Поиск по кастомному полю {label_serial_field_id} для серийника: {serial_number}")

                label_query_params = {
                    'criteria[0][field]': label_serial_field_id,
                    'criteria[0][searchtype]': 'contains',
                    'criteria[0][value]': serial_number,
                    'forcedisplay[0]': '2',   # ID
                    'forcedisplay[1]': '1',   # name
                    'forcedisplay[2]': '5',   # serial
                    'forcedisplay[3]': '23',  # manufacturer
                    'forcedisplay[4]': '31',  # states_name
                    'forcedisplay[5]': label_serial_field_id,  # само кастомное поле
                }

                label_response = requests.get(
                    f"{self.url}/search/Printer",
                    headers=self._get_headers(with_session=True),
                    params=label_query_params,
                    timeout=15,
                    verify=self.verify_ssl
                )

                logger.debug(f"Кастомное поле - Status: {label_response.status_code}")

                if label_response.status_code == 200:
                    label_data = label_response.json()
                    label_total_count = label_data.get('totalcount', 0)

                    logger.debug(f"Кастомное поле - найдено записей: {label_total_count}")

                    if label_total_count > 0:
                        label_items = label_data.get('data', [])
                        logger.info(f"GLPI: найдено по кастомному полю '{serial_number}' - {label_total_count} записей")
                        if label_total_count == 1:
                            return ('FOUND_SINGLE', label_items, None)
                        else:
                            return ('FOUND_MULTIPLE', label_items, None)
                else:
                    logger.warning(f"Кастомное поле - ошибка {label_response.status_code}: {label_response.text[:200]}")

            # Шаг 3: Fallback - поиск через /PluginFieldsPrinterx/ (медленный метод)
            # Используется только если предыдущие способы не сработали
            try:
                logger.debug(f"Используем fallback - поиск через /PluginFieldsPrinterx/ для: {serial_number}")

                plugin_response = requests.get(
                    f"{self.url}/PluginFieldsPrinterx/",
                    headers=self._get_headers(with_session=True),
                    timeout=15,
                    verify=self.verify_ssl
                )

                logger.debug(f"Fallback - Status: {plugin_response.status_code}")

                if plugin_response.status_code == 200:
                    plugin_data = plugin_response.json()
                    logger.debug(f"Fallback - получено записей из PluginFieldsPrinterx: {len(plugin_data)}")

                    # Ищем принтеры с совпадающим серийным номером на бирке
                    found_printer_ids = []
                    for record in plugin_data:
                        label_serial = record.get('serialnumberonlabelfield', '').strip()
                        items_id = record.get('items_id')

                        # Точное совпадение
                        if label_serial and label_serial.lower() == serial_number.lower():
                            if items_id:
                                found_printer_ids.append(items_id)
                                logger.debug(f"Fallback - найдено совпадение: items_id={items_id}, serial={label_serial}")

                    logger.debug(f"Fallback - найдено ID принтеров: {found_printer_ids}")

                    if found_printer_ids:
                        # Получаем полную информацию о найденных принтерах
                        printers = []
                        for printer_id in found_printer_ids:
                            printer_resp = requests.get(
                                f"{self.url}/Printer/{printer_id}",
                                headers=self._get_headers(with_session=True),
                                timeout=10,
                                verify=self.verify_ssl
                            )
                            if printer_resp.status_code == 200:
                                printers.append(printer_resp.json())

                        logger.info(f"GLPI: найдено через fallback '{serial_number}' - {len(printers)} принтеров")

                        if len(printers) == 1:
                            return ('FOUND_SINGLE', printers, None)
                        elif len(printers) > 1:
                            return ('FOUND_MULTIPLE', printers, None)
                else:
                    logger.debug(f"Fallback - ошибка {plugin_response.status_code}: {plugin_response.text[:200]}")

            except Exception as plugin_error:
                # Игнорируем ошибки fallback метода
                logger.debug(f"Fallback поиск через PluginFieldsPrinterx не удался: {plugin_error}")

            # Не найдено ни одним способом
            return ('NOT_FOUND', [], None)

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
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения принтера {printer_id}: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Ошибка при получении данных принтера: {e}")
            return None

    def update_printer_counter(self, printer_id: int, page_counter: int) -> Tuple[bool, Optional[str]]:
        """
        Обновляет счетчик страниц принтера в GLPI.

        Args:
            printer_id: ID принтера в GLPI
            page_counter: Новое значение счетчика страниц

        Returns:
            Tuple из:
            - success: True если обновление успешно
            - error: Сообщение об ошибке (если есть)
        """
        self._ensure_session()

        try:
            # Данные для обновления
            # Поле last_pages_counter - текущий счетчик страниц в GLPI
            update_data = {
                "input": {
                    "last_pages_counter": str(page_counter)
                }
            }

            response = requests.put(
                f"{self.url}/Printer/{printer_id}",
                headers=self._get_headers(with_session=True),
                json=update_data,
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code in [200, 201]:
                return (True, None)
            else:
                error_msg = response.json().get('message', response.text) if response.text else f"HTTP {response.status_code}"
                logger.error(f"Failed to update printer {printer_id}: {error_msg}")
                return (False, f"Ошибка обновления: {error_msg}")

        except requests.RequestException as e:
            logger.error(f"Request error updating printer {printer_id}: {e}")
            return (False, f"Ошибка подключения: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error updating printer {printer_id}: {e}")
            return (False, f"Неожиданная ошибка: {str(e)}")

    def get_state_name(self, state_id: int) -> Optional[str]:
        """
        Получает название состояния по ID из GLPI.

        Args:
            state_id: ID состояния в GLPI

        Returns:
            Название состояния или None при ошибке
        """
        if not state_id:
            return None

        self._ensure_session()

        try:
            response = requests.get(
                f"{self.url}/State/{state_id}",
                headers=self._get_headers(with_session=True),
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                state_name = data.get('name', data.get('completename', ''))
                return state_name
            else:
                return None

        except requests.RequestException as e:
            logger.error(f"Error getting state name for ID {state_id}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error getting state name for ID {state_id}: {e}")
            return None

    def update_contract_field(
        self,
        printer_id: int,
        is_in_contract: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        Обновляет поле "Заявлен в договоре" в Plugin Fields для принтера.

        Plugin Fields хранятся в отдельном ресурсе (например, PluginFieldsPrinterXXX).
        Сначала ищется существующая запись для принтера. Если её нет - создаётся новая через POST.
        Если есть - обновляется через PATCH.

        Args:
            printer_id: ID принтера в GLPI
            is_in_contract: True - "Да", False - "Нет"

        Returns:
            Tuple из:
            - success: True если обновление успешно
            - error: Сообщение об ошибке (если есть)
        """
        self._ensure_session()

        if not self.contract_field_name:
            return (False, "GLPI_CONTRACT_FIELD_NAME не настроен")

        if not self.contract_resource_name:
            return (False, "GLPI_CONTRACT_RESOURCE_NAME не настроен")

        try:
            new_value = 1 if is_in_contract else 0

            logger.info(f"Обновление поля договора для принтера {printer_id}:")
            logger.info(f"  Ресурс: {self.contract_resource_name}")
            logger.info(f"  Поле: {self.contract_field_name}")
            logger.info(f"  Значение: {new_value}")

            # Шаг 1: Ищем существующую запись для принтера через search API
            search_params = {
                'criteria[0][field]': 'items_id',
                'criteria[0][searchtype]': 'equals',
                'criteria[0][value]': printer_id,
                'criteria[1][link]': 'AND',
                'criteria[1][field]': 'itemtype',
                'criteria[1][searchtype]': 'equals',
                'criteria[1][value]': 'Printer',
            }

            response = requests.get(
                f"{self.url}/search/{self.contract_resource_name}",
                headers=self._get_headers(with_session=True),
                params=search_params,
                timeout=10,
                verify=self.verify_ssl
            )

            existing_record_id = None
            if response.status_code == 200:
                data = response.json()
                total_count = data.get('totalcount', 0)
                if total_count > 0:
                    # Берем ID первой найденной записи
                    items = data.get('data', [])
                    if items:
                        # Search API возвращает поля с номерами
                        existing_record_id = items[0].get('2')  # Поле ID обычно под номером 2
                        logger.info(f"  Найдена существующая запись: ID={existing_record_id}")
                else:
                    logger.info(f"  Запись для принтера {printer_id} не найдена, будет создана новая")

            # Шаг 2: Обновляем или создаём запись
            if existing_record_id:
                # Обновляем существующую запись через PATCH
                update_data = {
                    "input": {
                        "id": existing_record_id,
                        self.contract_field_name: new_value
                    }
                }

                logger.info(f"  Обновление записи ID={existing_record_id} через PATCH")

                response = requests.patch(
                    f"{self.url}/{self.contract_resource_name}/{existing_record_id}",
                    headers=self._get_headers(with_session=True),
                    json=update_data,
                    timeout=10,
                    verify=self.verify_ssl
                )

                if response.status_code in [200, 201]:
                    logger.info(f"✓ Обновлена запись PluginFields ID={existing_record_id} для принтера {printer_id}")
                    return (True, None)
                else:
                    error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                    logger.error(f"Ошибка обновления: {error_msg}")
                    return (False, f"Ошибка обновления: {error_msg}")

            else:
                # Создаём новую запись через POST
                create_data = {
                    "input": {
                        "items_id": printer_id,
                        "itemtype": "Printer",
                        self.contract_field_name: new_value
                    }
                }

                logger.info(f"  Создание новой записи через POST")
                logger.info(f"  Данные: {create_data}")

                response = requests.post(
                    f"{self.url}/{self.contract_resource_name}",
                    headers=self._get_headers(with_session=True),
                    json=create_data,
                    timeout=10,
                    verify=self.verify_ssl
                )

                if response.status_code in [200, 201]:
                    logger.info(f"✓ Создана новая запись PluginFields для принтера {printer_id}")
                    return (True, None)
                else:
                    error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                    logger.error(f"Ошибка создания: {error_msg}")
                    return (False, f"Ошибка создания: {error_msg}")

        except requests.RequestException as e:
            logger.error(f"Request error updating contract field for printer {printer_id}: {e}")
            return (False, f"Ошибка подключения: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error updating contract field for printer {printer_id}: {e}")
            return (False, f"Неожиданная ошибка: {str(e)}")

    def __enter__(self):
        """Context manager support"""
        self.init_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.kill_session()
        return False
