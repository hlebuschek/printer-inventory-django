# printer_inventory/auth_views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView


def login_choice(request):
    """
    Страница входа с автоматическим редиректом на Keycloak.
    Если пользователь не прошел авторизацию через Keycloak,
    показываем форму Django логина.
    """

    # Если пользователь уже авторизован, перенаправляем на главную
    if request.user.is_authenticated:
        return redirect('index')

    # Сохраняем next URL в сессии для последующего использования
    next_url = request.GET.get('next', '/')
    request.session['oidc_login_next'] = next_url

    # Проверяем, настроен ли Keycloak
    keycloak_enabled = bool(
        getattr(settings, 'OIDC_RP_CLIENT_ID', '') and
        getattr(settings, 'OIDC_OP_AUTHORIZATION_ENDPOINT', '')
    )

    # Проверяем флаг ошибки Keycloak (установлен в CustomOIDCCallbackView)
    keycloak_failed = request.session.pop('keycloak_auth_failed', False)
    error_message = request.session.pop('keycloak_error_message', None)

    # Если Keycloak настроен и не было ошибки - автоматически редиректим туда
    if keycloak_enabled and not keycloak_failed:
        # Перенаправляем на OIDC authentication с параметром next
        from django.http import QueryDict
        query_params = QueryDict(mutable=True)
        query_params['next'] = next_url
        return redirect(f"{reverse('oidc_authentication_init')}?{query_params.urlencode()}")

    # Если была ошибка Keycloak - показываем сообщение
    if error_message:
        messages.error(request, error_message)

    context = {
        'keycloak_enabled': keycloak_enabled,
        'keycloak_failed': keycloak_failed,
        'next': next_url,
    }

    return render(request, 'registration/login_choice.html', context)


def django_login(request):
    """Стандартный Django логин"""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '/')

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
                return redirect(next_url)
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')

    context = {
        'next': request.GET.get('next', '/'),
    }

    return render(request, 'registration/django_login.html', context)


def keycloak_access_denied(request):
    """Страница отказа в доступе для Keycloak """
    return render(request, 'registration/keycloak_access_denied.html')


class CustomOIDCCallbackView(OIDCAuthenticationCallbackView):
    """
    Кастомный callback view для OIDC, который поддерживает редирект
    на исходную страницу после успешной авторизации и обработку ошибок
    """

    def login_success(self):
        """
        Переопределяем метод успешного логина.
        Родительский класс уже выполнил auth_login, просто добавляем сообщение и редиректим.
        """
        # Добавляем сообщение об успешном входе
        user_name = self.user.get_full_name() or self.user.username
        messages.success(self.request, f'Добро пожаловать, {user_name}!')

        # Возвращаем redirect используя наш get_success_url
        return redirect(self.get_success_url())

    def get_success_url(self):
        """
        Получает URL для редиректа после успешной авторизации.
        Приоритет:
        1. next из сессии (сохраненный при переходе на страницу логина)
        2. next из GET параметров
        3. state параметр (может содержать next)
        4. LOGIN_REDIRECT_URL из settings
        """
        import logging
        logger = logging.getLogger(__name__)

        # Проверяем сессию
        next_url = self.request.session.get('oidc_login_next', None)
        logger.info(f"get_success_url: oidc_login_next from session = {next_url}")

        # Если нет в сессии, проверяем GET параметры
        if not next_url:
            next_url = self.request.GET.get('next')
            logger.info(f"get_success_url: next from GET = {next_url}")

        # Если все еще пусто, используем дефолтный URL
        if not next_url:
            next_url = settings.LOGIN_REDIRECT_URL or '/'
            logger.info(f"get_success_url: using default = {next_url}")

        # Очищаем из сессии
        if 'oidc_login_next' in self.request.session:
            del self.request.session['oidc_login_next']

        # Проверяем, что URL безопасен (не ведет на внешний сайт)
        if next_url.startswith('http://') or next_url.startswith('https://'):
            # Если это внешний URL, используем дефолтный
            logger.warning(f"get_success_url: unsafe URL {next_url}, using default")
            return settings.LOGIN_REDIRECT_URL or '/'

        logger.info(f"get_success_url: final URL = {next_url}")
        return next_url

    def login_failure(self):
        """
        Переопределяем метод ошибки логина.
        Устанавливаем флаги в сессии и редиректим на страницу Django логина.
        """
        # Устанавливаем флаг ошибки Keycloak
        self.request.session['keycloak_auth_failed'] = True

        # Определяем сообщение об ошибке
        error_message = 'Не удалось войти через Keycloak. '

        # Попробуем получить детали ошибки
        if hasattr(self, 'failure_url'):
            # Возможно была ошибка авторизации (пользователь не в whitelist)
            error_message += 'Возможно, ваш аккаунт не добавлен в систему или неактивен.'
        else:
            error_message += 'Попробуйте войти используя логин и пароль.'

        self.request.session['keycloak_error_message'] = error_message

        # Редиректим на страницу login_choice, которая покажет форму Django логина
        return redirect('login_choice')