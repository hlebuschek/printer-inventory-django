# printer_inventory/auth_views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.conf import settings


def login_choice(request):
    """Страница выбора способа входа: Django или Keycloak"""

    # Если пользователь уже авторизован, перенаправляем на главную
    if request.user.is_authenticated:
        return redirect('index')

    # Проверяем, настроен ли Keycloak
    keycloak_enabled = bool(
        getattr(settings, 'OIDC_RP_CLIENT_ID', '') and
        getattr(settings, 'OIDC_OP_AUTHORIZATION_ENDPOINT', '')
    )

    context = {
        'keycloak_enabled': keycloak_enabled,
        'next': request.GET.get('next', '/'),
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
                login(request, user)
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