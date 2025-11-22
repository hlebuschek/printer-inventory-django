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

    # Проверяем, явно ли пользователь хочет выбрать способ входа вручную
    # (например, после logout или при переключении аккаунтов)
    manual_choice = request.GET.get('manual', False)

    # Если Keycloak настроен, не было ошибки и не требуется ручной выбор - автоматически редиректим
    if keycloak_enabled and not keycloak_failed and not manual_choice:
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


def custom_logout(request):
    """
    Кастомный logout, который предотвращает автоматический редирект на Keycloak.
    После выхода пользователь попадает на страницу выбора способа входа.
    """
    from django.contrib.auth import logout

    # Выполняем logout
    logout(request)

    # Добавляем сообщение об успешном выходе
    messages.success(request, 'Вы успешно вышли из системы.')

    # Редиректим на страницу входа с параметром manual=1
    # Это предотвратит автоматический редирект на Keycloak
    return redirect(f"{reverse('login_choice')}?manual=1")


class CustomOIDCCallbackView(OIDCAuthenticationCallbackView):
    """
    Кастомный callback view для OIDC, который поддерживает редирект
    на исходную страницу после успешной авторизации и обработку ошибок
    """

    def get(self, request):
        """
        Переопределяем метод get для полного контроля над процессом аутентификации.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Проверяем наличие ошибки в параметрах
        if 'error' in request.GET:
            logger.warning(f"OIDC error in callback: {request.GET.get('error')}")
            return self.login_failure()

        # Вызываем родительский метод для получения пользователя
        # Родительский get() делает всю работу по обмену code на токены
        # и вызывает authenticate()
        try:
            # Выполняем аутентификацию через родительский класс
            response = super().get(request)

            # Если родительский метод успешно аутентифицировал пользователя
            if request.user.is_authenticated:
                # Добавляем приветственное сообщение
                user_name = request.user.get_full_name() or request.user.username
                messages.success(request, f'Добро пожаловать, {user_name}!')

                # Получаем URL для редиректа
                success_url = self.get_success_url()
                return redirect(success_url)
            else:
                logger.error("Parent get() didn't authenticate user!")
                return self.login_failure()

        except Exception as e:
            logger.error(f"Exception in OIDC callback: {e}", exc_info=True)
            return self.login_failure()

    def get_success_url(self):
        """
        Получает URL для редиректа после успешной авторизации.
        Приоритет:
        1. next из сессии (сохраненный при переходе на страницу логина)
        2. next из GET параметров
        3. state параметр (может содержать next)
        4. LOGIN_REDIRECT_URL из settings
        """
        # Проверяем сессию
        next_url = self.request.session.get('oidc_login_next', None)

        # Если нет в сессии, проверяем GET параметры
        if not next_url:
            next_url = self.request.GET.get('next')

        # Если все еще пусто, используем дефолтный URL
        if not next_url:
            next_url = settings.LOGIN_REDIRECT_URL or '/'

        # Очищаем из сессии
        if 'oidc_login_next' in self.request.session:
            del self.request.session['oidc_login_next']

        # Проверяем, что URL безопасен (не ведет на внешний сайт)
        if next_url.startswith('http://') or next_url.startswith('https://'):
            # Если это внешний URL, используем дефолтный
            return settings.LOGIN_REDIRECT_URL or '/'

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