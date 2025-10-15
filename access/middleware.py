from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth import logout


class AppAccessMiddleware:
    """Ограничивает доступ к приложениям по app-level правам."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.rules = getattr(settings, "APP_ACCESS_RULES", {})
        self.exempt_namespaces = set(getattr(settings, "APP_ACCESS_EXEMPT_NAMESPACES", {
            "admin", "auth", "account", "accounts", "social_django",
        }))
        self.exempt_prefixes = tuple(getattr(settings, "APP_ACCESS_EXEMPT_PREFIXES", (
            "/static/", "/media/", "/ws/",
        )))

    def __call__(self, request):
        path = request.path

        # Явные исключения (статик, медиа, ws)
        if path.startswith(self.exempt_prefixes):
            return self.get_response(request)

        # Разрешение/namespace текущего URL
        try:
            match = resolve(path)
        except Exception:
            return self.get_response(request)

        namespace = (match.namespace or "").split(":")[0]

        # Если namespace в исключениях — пропускаем
        if namespace in self.exempt_namespaces:
            return self.get_response(request)

        # Вычисляем целевое приложение
        app_label = None
        if namespace:
            app_label = namespace
        else:
            mod = (match.func.__module__ or "").split(".")
            if mod:
                app_label = mod[0]

        perm = self.rules.get(app_label)
        if not perm:
            return self.get_response(request)

        # Проверка аутентификации
        if not request.user.is_authenticated:
            login_url = settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else reverse("login")
            return redirect(f"{login_url}?next={request.get_full_path()}")

        # Проверка права на доступ к приложению
        if not request.user.has_perm(perm):
            return HttpResponseForbidden("Forbidden: no app access")

        return self.get_response(request)


class WhitelistCheckMiddleware:
    """
    Проверяет, что пользователи из Keycloak все еще в whitelist.
    Если пользователь удален из whitelist - разлогинивает его.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/accounts/login/',
            '/accounts/logout/',
            '/oidc/',
            '/static/',
            '/media/',
        ]

    def __call__(self, request):
        # Пропускаем неавторизованных и exempt пути
        if not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)

        # Проверяем только пользователей из Keycloak (не superuser и не staff)
        if request.user.is_superuser or request.user.is_staff:
            return self.get_response(request)

        # Проверяем whitelist
        from access.models import AllowedUser

        try:
            allowed = AllowedUser.objects.get(
                username__iexact=request.user.username,
                is_active=True
            )
        except AllowedUser.DoesNotExist:
            # Пользователь не в whitelist или неактивен
            messages.error(
                request,
                f"Доступ для пользователя '{request.user.username}' был отозван. "
                "Обратитесь к администратору."
            )
            logout(request)
            return redirect('login_choice')

        return self.get_response(request)