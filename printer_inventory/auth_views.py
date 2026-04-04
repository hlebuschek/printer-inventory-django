# printer_inventory/auth_views.py
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods


def _safe_next_url(request, next_url):
    """Проверяет, что URL безопасен для редиректа (не ведёт на внешний сайт)."""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return "/"


def login_choice(request):
    """
    Страница входа с автоматическим редиректом на Keycloak.
    Если пользователь не прошел авторизацию через Keycloak,
    показываем форму Django логина.
    """

    # Если пользователь уже авторизован, перенаправляем на запрошенную страницу
    if request.user.is_authenticated:
        next_url = _safe_next_url(request, request.GET.get("next", "/"))
        return redirect(next_url)

    # Сохраняем next URL в сессии для последующего использования
    next_url = request.GET.get("next", "/")
    request.session["oidc_login_next"] = next_url

    # Проверяем, настроен ли Keycloak
    keycloak_enabled = bool(
        getattr(settings, "OIDC_RP_CLIENT_ID", "") and getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", "")
    )

    # Проверяем флаг ошибки Keycloak (установлен в CustomOIDCCallbackView)
    keycloak_failed = request.session.pop("keycloak_auth_failed", False)

    # Если была ошибка Keycloak, добавляем сообщение в Django messages
    keycloak_error_message = request.session.pop("keycloak_error_message", None)
    if keycloak_failed and keycloak_error_message:
        messages.error(request, keycloak_error_message)

    # Проверяем, явно ли пользователь хочет выбрать способ входа вручную
    # (например, после logout или при переключении аккаунтов)
    manual_choice = request.GET.get("manual", False)

    # Если Keycloak настроен, не было ошибки и не требуется ручной выбор - автоматически редиректим
    if keycloak_enabled and not keycloak_failed and not manual_choice:
        # Перенаправляем на OIDC authentication с параметром next
        from django.http import QueryDict

        query_params = QueryDict(mutable=True)
        query_params["next"] = next_url
        return redirect(f"{reverse('oidc_authentication_init')}?{query_params.urlencode()}")

    context = {
        "keycloak_enabled": keycloak_enabled,
        "keycloak_failed": keycloak_failed,
        "next": next_url,
    }

    return render(request, "registration/login_choice.html", context)


@ensure_csrf_cookie
def django_login(request):
    """Стандартный Django логин"""
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = _safe_next_url(request, request.POST.get("next", "/"))

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect(next_url)
            else:
                messages.error(request, "Неверное имя пользователя или пароль.")

    context = {
        "next": request.GET.get("next", "/"),
    }

    return render(request, "registration/django_login.html", context)


def keycloak_access_denied(request):
    """Страница отказа в доступе для Keycloak"""
    return render(request, "registration/keycloak_access_denied.html")


def custom_logout(request):
    """
    Кастомный logout, который предотвращает автоматический редирект на Keycloak.
    После выхода пользователь попадает на страницу выбора способа входа.
    """
    from django.contrib.auth import logout

    # Выполняем logout
    logout(request)

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

        logger.debug(f"OIDC callback: session_key={request.session.session_key}")

        # Проверяем наличие ошибки в параметрах
        if "error" in request.GET:
            logger.warning(f"OIDC error in callback: {request.GET.get('error')}")
            return self.login_failure()

        try:
            # Выполняем аутентификацию через родительский класс
            super().get(request)
            logger.debug(f"Parent get() returned, user authenticated: {request.user.is_authenticated}")

            # Если родительский метод успешно аутентифицировал пользователя
            if request.user.is_authenticated:
                logger.info(f"User authenticated: {request.user.username}")
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
        next_url = self.request.session.get("oidc_login_next", None)

        # Если нет в сессии, проверяем GET параметры
        if not next_url:
            next_url = self.request.GET.get("next")

        # Если все еще пусто, используем дефолтный URL
        if not next_url:
            next_url = settings.LOGIN_REDIRECT_URL or "/"

        # Очищаем из сессии
        if "oidc_login_next" in self.request.session:
            del self.request.session["oidc_login_next"]

        # Проверяем, что URL безопасен (не ведет на внешний сайт)
        return _safe_next_url(self.request, next_url)

    def login_failure(self):
        """
        Переопределяем метод ошибки логина.
        Устанавливаем флаги в сессии и редиректим на страницу Django логина.
        """
        from django.contrib.auth import logout

        # ВАЖНО: Полностью разлогиниваем пользователя
        # Это предотвращает бесконечный цикл редиректов
        # когда у пользователя есть Django сессия, но токены Keycloak истекли
        if self.request.user.is_authenticated:
            logout(self.request)

        # Устанавливаем флаг ошибки Keycloak
        self.request.session["keycloak_auth_failed"] = True

        # Определяем сообщение об ошибке
        error_message = "Не удалось войти через Keycloak. "

        # Попробуем получить детали ошибки
        if hasattr(self, "failure_url"):
            # Возможно была ошибка авторизации (пользователь не в whitelist)
            error_message += "Возможно, ваш аккаунт не добавлен в систему или неактивен."
        else:
            error_message += "Попробуйте войти используя логин и пароль."

        self.request.session["keycloak_error_message"] = error_message

        # Редиректим на страницу login_choice с параметром manual=1
        # Это предотвратит автоматический редирект обратно на Keycloak
        return redirect(f"{reverse('login_choice')}?manual=1")


def reauth_complete(request):
    """
    Минимальная страница-заглушка для скрытого iframe при silent re-auth.
    После прохождения OIDC flow (Keycloak prompt=none) iframe загружает эту страницу.
    Она отправляет postMessage родительскому окну, сигнализируя об успешной реавторизации.
    """
    html = """<!DOCTYPE html>
<html><head><title>reauth</title></head><body>
<script>
if (window.parent !== window) {
    window.parent.postMessage({type: 'reauth-ok'}, window.location.origin);
}
</script>
</body></html>"""
    response = HttpResponse(html, content_type="text/html")
    # Разрешаем загрузку в iframe (только same-origin)
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


@require_http_methods(["POST"])
def heartbeat(request):
    """
    Endpoint для поддержания сессии активной.

    Проактивно обновляет OIDC-токен через refresh_token серверно,
    без redirect на Keycloak и без iframe. Работает через cookie сессии.

    Вызывается каждые 5 минут из session-manager.js.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)

    # Проверяем, скоро ли истечёт OIDC-токен (за 2 минуты до истечения)
    import time

    expiration = request.session.get("oidc_id_token_expiration", 0)
    time_left = expiration - time.time()
    token_refreshed = False

    if time_left < 120:  # Менее 2 минут до истечения
        refresh_token = request.session.get("oidc_refresh_token")
        if refresh_token:
            success = _refresh_oidc_token(request, refresh_token)
            if success:
                token_refreshed = True
            else:
                # refresh_token невалиден — пользователю нужно перелогиниться
                return JsonResponse(
                    {"ok": False, "error": "session_expired", "message": "Сессия истекла"},
                    status=401,
                )

    return JsonResponse(
        {
            "ok": True,
            "username": request.user.username,
            "token_refreshed": token_refreshed,
        }
    )


def _refresh_oidc_token(request, refresh_token):
    """
    Серверное обновление OIDC-токена через refresh_token grant.
    Обращается к Keycloak token endpoint напрямую, без redirect.
    """
    import logging
    import time

    import requests as http_requests

    logger = logging.getLogger(__name__)

    token_endpoint = settings.OIDC_OP_TOKEN_ENDPOINT
    client_id = settings.OIDC_RP_CLIENT_ID
    client_secret = settings.OIDC_RP_CLIENT_SECRET
    verify_ssl = getattr(settings, "OIDC_VERIFY_SSL", True)

    try:
        response = http_requests.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            verify=verify_ssl,
            timeout=10,
        )

        if response.status_code != 200:
            logger.warning(f"OIDC token refresh failed: {response.status_code} {response.text[:200]}")
            return False

        token_data = response.json()

        # Обновляем токены в сессии
        if "access_token" in token_data:
            request.session["oidc_access_token"] = token_data["access_token"]
        if "id_token" in token_data:
            request.session["oidc_id_token"] = token_data["id_token"]
        if "refresh_token" in token_data:
            request.session["oidc_refresh_token"] = token_data["refresh_token"]

        # Обновляем expiration — SessionRefresh middleware не будет тригерить redirect
        expiration_interval = getattr(settings, "OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS", 15 * 60)
        request.session["oidc_id_token_expiration"] = time.time() + expiration_interval

        logger.info(f"OIDC token refreshed server-side for user {request.user.username}")
        return True

    except http_requests.RequestException as e:
        logger.error(f"OIDC token refresh request failed: {e}")
        return False
