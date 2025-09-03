from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.http import HttpResponseForbidden

class AppAccessMiddleware:
    """Ограничивает доступ к приложениям по app-level правам.
    Правила настраиваются в settings.APP_ACCESS_RULES = {
        'inventory': 'inventory.access_inventory_app',
        'contracts': 'contracts.access_contracts_app',
    }
    Опирается на namespace/имя приложения из url resolver.
    """
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
            # Падает назад к модулю view: inventory.views.* → "inventory"
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