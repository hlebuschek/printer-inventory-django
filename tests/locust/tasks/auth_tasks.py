"""
Задачи авторизации для Locust тестов

Этот модуль содержит миксины для авторизации через Django и Keycloak.
"""

import logging
import re
from urllib.parse import urljoin, urlparse, parse_qs
from locust.exception import StopUser

logger = logging.getLogger(__name__)


class DjangoAuthMixin:
    """
    Миксин для авторизации через стандартную Django форму.

    Использует endpoint: /accounts/django-login/

    Атрибуты:
        username (str): Имя пользователя Django
        password (str): Пароль пользователя
    """

    username = None
    password = None

    def login(self):
        """
        Выполняет вход через Django форму.

        Returns:
            bool: True если вход успешен, False иначе

        Raises:
            StopUser: Если не удалось авторизоваться
        """
        if not self.username or not self.password:
            logger.error("Django username or password not set")
            raise StopUser("Django credentials not configured")

        # 1. Получаем страницу логина для получения CSRF токена
        logger.info(f"Fetching Django login page for user: {self.username}")
        response = self.client.get(
            "/accounts/django-login/",
            name="/accounts/django-login/ [GET]"
        )

        if response.status_code != 200:
            logger.error(f"Failed to get login page: {response.status_code}")
            raise StopUser(f"Failed to get login page: {response.status_code}")

        # 2. Извлекаем CSRF токен из HTML
        csrf_token = self._extract_csrf_token(response.text)
        if not csrf_token:
            logger.error("Failed to extract CSRF token from login page")
            raise StopUser("CSRF token not found")

        logger.debug(f"CSRF token extracted: {csrf_token[:20]}...")

        # 3. Django требует CSRF cookie для проверки.
        # Если cookie не установлен Django, устанавливаем вручную
        if 'csrftoken' not in self.client.cookies:
            logger.debug("CSRF cookie not set by server, setting manually")
            # Извлекаем domain из base_url
            parsed = urlparse(self.client.base_url)
            domain = parsed.hostname or 'localhost'

            # Устанавливаем cookie с CSRF токеном
            self.client.cookies.set(
                name='csrftoken',
                value=csrf_token,
                domain=domain,
                path='/'
            )
            logger.debug(f"Set CSRF cookie for domain: {domain}")

        # 4. Отправляем POST запрос с credentials и необходимыми заголовками
        login_data = {
            'username': self.username,
            'password': self.password,
            'csrfmiddlewaretoken': csrf_token,
            'next': '/',
        }

        # Django требует Referer заголовок для CSRF защиты
        headers = {
            'Referer': self.client.base_url + '/accounts/django-login/',
            'X-CSRFToken': csrf_token,
        }

        logger.info(f"Attempting Django login for user: {self.username}")
        response = self.client.post(
            "/accounts/django-login/",
            data=login_data,
            headers=headers,
            name="/accounts/django-login/ [POST]",
            allow_redirects=False  # Не следуем редиректам автоматически
        )

        # 5. Проверяем успешность входа
        if response.status_code in [302, 301]:  # Редирект = успешный вход
            logger.info(f"✓ Django login successful for user: {self.username}")

            # Следуем редиректу
            redirect_url = response.headers.get('Location', '/')
            self.client.get(redirect_url, name="[after login redirect]")

            return True
        else:
            logger.error(f"✗ Django login failed for user: {self.username}, status: {response.status_code}")
            logger.error(f"Response text: {response.text[:500]}")
            raise StopUser(f"Login failed: {response.status_code}")

    def _extract_csrf_token(self, html):
        """
        Извлекает CSRF токен из HTML страницы.

        Args:
            html (str): HTML содержимое страницы

        Returns:
            str: CSRF токен или None
        """
        # Ищем в input элементе
        match = re.search(
            r'<input[^>]*name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']',
            html
        )
        if match:
            return match.group(1)

        # Ищем в мета теге
        match = re.search(
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
            html
        )
        if match:
            return match.group(1)

        return None


class KeycloakAuthMixin:
    """
    Миксин для авторизации через Keycloak OIDC.

    Этот класс эмулирует полный OAuth2/OIDC flow:
    1. Инициирует OIDC аутентификацию
    2. Получает форму входа Keycloak
    3. Авторизуется в Keycloak
    4. Обрабатывает callback с кодом авторизации

    Атрибуты:
        keycloak_username (str): Имя пользователя в Keycloak
        keycloak_password (str): Пароль пользователя в Keycloak
    """

    keycloak_username = None
    keycloak_password = None

    def login(self):
        """
        Выполняет вход через Keycloak OIDC flow.

        Returns:
            bool: True если вход успешен, False иначе

        Raises:
            StopUser: Если не удалось авторизоваться
        """
        if not self.keycloak_username or not self.keycloak_password:
            logger.error("Keycloak username or password not set")
            raise StopUser("Keycloak credentials not configured")

        try:
            # Шаг 1: Инициируем OIDC аутентификацию
            logger.info(f"Initiating Keycloak OIDC flow for user: {self.keycloak_username}")
            auth_url = self._initiate_oidc_auth()

            # Шаг 2: Получаем форму входа Keycloak
            logger.info("Fetching Keycloak login form")
            keycloak_login_url, keycloak_data = self._get_keycloak_login_form(auth_url)

            # Шаг 3: Отправляем credentials в Keycloak
            logger.info(f"Submitting Keycloak credentials for user: {self.keycloak_username}")
            callback_url = self._submit_keycloak_login(
                keycloak_login_url,
                keycloak_data
            )

            # Шаг 4: Обрабатываем callback (обмен кода на токен происходит на бэкенде)
            logger.info("Processing OIDC callback")
            self._process_oidc_callback(callback_url)

            logger.info(f"✓ Keycloak login successful for user: {self.keycloak_username}")
            return True

        except Exception as e:
            logger.error(f"✗ Keycloak login failed for user: {self.keycloak_username}: {e}")
            raise StopUser(f"Keycloak login failed: {e}")

    def _initiate_oidc_auth(self):
        """
        Инициирует OIDC аутентификацию.

        Returns:
            str: URL формы входа Keycloak
        """
        response = self.client.get(
            "/oidc/authenticate/",
            name="/oidc/authenticate/ [GET]",
            allow_redirects=False
        )

        if response.status_code not in [302, 301]:
            raise Exception(f"OIDC init failed: {response.status_code}")

        # Должны получить редирект на Keycloak
        keycloak_auth_url = response.headers.get('Location')
        if not keycloak_auth_url or 'auth/realms' not in keycloak_auth_url:
            raise Exception("Invalid Keycloak auth URL")

        logger.debug(f"Keycloak auth URL: {keycloak_auth_url}")
        return keycloak_auth_url

    def _get_keycloak_login_form(self, auth_url):
        """
        Получает форму входа Keycloak.

        Args:
            auth_url (str): URL авторизации Keycloak

        Returns:
            tuple: (login_url, form_data) - URL для отправки формы и данные формы
        """
        # Используем catch_response чтобы не учитывать этот запрос в статистике
        # (это внешний сервис)
        with self.client.get(
            auth_url,
            name="[Keycloak] GET login form",
            catch_response=True,
            allow_redirects=True
        ) as response:
            response.success()  # Всегда считаем успешным

            if response.status_code != 200:
                raise Exception(f"Failed to get Keycloak form: {response.status_code}")

            # Извлекаем URL формы из action атрибута
            match = re.search(r'<form[^>]*action="([^"]+)"', response.text)
            if not match:
                raise Exception("Keycloak form action not found")

            form_action = match.group(1).replace('&amp;', '&')

            # Собираем данные формы
            form_data = {}

            # Извлекаем все скрытые поля
            for match in re.finditer(
                r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
                response.text
            ):
                form_data[match.group(1)] = match.group(2)

            logger.debug(f"Keycloak form action: {form_action}")
            logger.debug(f"Keycloak form data: {list(form_data.keys())}")

            return form_action, form_data

    def _submit_keycloak_login(self, login_url, form_data):
        """
        Отправляет credentials в Keycloak.

        Args:
            login_url (str): URL для отправки формы
            form_data (dict): Данные формы

        Returns:
            str: URL callback с кодом авторизации
        """
        # Добавляем credentials
        form_data['username'] = self.keycloak_username
        form_data['password'] = self.keycloak_password

        # Отправляем форму
        with self.client.post(
            login_url,
            data=form_data,
            name="[Keycloak] POST login",
            catch_response=True,
            allow_redirects=False
        ) as response:
            response.success()  # Всегда считаем успешным

            if response.status_code not in [302, 301]:
                raise Exception(f"Keycloak login failed: {response.status_code}")

            # Получаем URL callback
            callback_url = response.headers.get('Location')
            if not callback_url or 'code=' not in callback_url:
                raise Exception("Invalid callback URL from Keycloak")

            logger.debug(f"Callback URL received: {callback_url[:100]}...")
            return callback_url

    def _process_oidc_callback(self, callback_url):
        """
        Обрабатывает OIDC callback.

        Args:
            callback_url (str): URL callback с кодом авторизации
        """
        # Извлекаем путь и параметры
        parsed = urlparse(callback_url)
        callback_path = parsed.path + '?' + parsed.query if parsed.query else parsed.path

        # Отправляем запрос на callback endpoint
        response = self.client.get(
            callback_path,
            name="/oidc/callback/ [GET]",
            allow_redirects=True
        )

        if response.status_code != 200:
            raise Exception(f"OIDC callback failed: {response.status_code}")

        # Проверяем, что мы вошли (есть сессия)
        # Попробуем запросить защищенную страницу
        check_response = self.client.get(
            "/printers/",
            name="[check auth] /printers/",
            catch_response=True
        )

        if check_response.status_code == 200:
            check_response.success()
        else:
            check_response.failure(f"Auth check failed: {check_response.status_code}")
            raise Exception("Authentication verification failed")
