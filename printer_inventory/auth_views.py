# printer_inventory/auth_views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView


def login_choice(request):
    """Страница выбора способа входа: Django или Keycloak"""

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

    context = {
        'keycloak_enabled': keycloak_enabled,
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
    на исходную страницу после успешной авторизации
    """

    def get_success_url(self):
        """
        Получает URL для редиректа после успешной авторизации.
        Приоритет:
        1. next из сессии (сохраненный при переходе на страницу логина)
        2. next из GET параметров
        3. LOGIN_REDIRECT_URL из settings
        """
        # Проверяем сессию
        next_url = self.request.session.pop('oidc_login_next', None)

        # Если нет в сессии, проверяем GET параметры
        if not next_url:
            next_url = self.request.GET.get('next')

        # Если все еще пусто, используем дефолтный URL
        if not next_url:
            next_url = settings.LOGIN_REDIRECT_URL or '/'

        # Проверяем, что URL безопасен (не ведет на внешний сайт)
        if next_url.startswith('http://') or next_url.startswith('https://'):
            # Если это внешний URL, используем дефолтный
            return settings.LOGIN_REDIRECT_URL or '/'

        return next_url

    def login_success(self):
        """Переопределяем метод успешного логина для использования нашего get_success_url"""
        auth_login(self.request, self.user, backend='printer_inventory.auth_backends.CustomOIDCAuthenticationBackend')

        # Добавляем сообщение об успешном входе
        user_name = self.user.get_full_name() or self.user.username
        messages.success(self.request, f'Добро пожаловать, {user_name}!')

        return redirect(self.get_success_url())