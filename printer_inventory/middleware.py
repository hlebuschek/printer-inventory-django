import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponseServerError, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

logger = logging.getLogger("printer_inventory.middleware")


class AjaxSessionRefreshMiddleware:
    """
    Перехватывает redirect на Keycloak для AJAX-запросов.
    Когда SessionRefresh middleware пытается перенаправить на Keycloak
    (из-за истёкшего OIDC-токена), AJAX-запросы получают 302 redirect,
    который браузер не может выполнить из fetch (CSP блокирует connect-src).
    Этот middleware возвращает 401 JSON вместо redirect для AJAX-запросов.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Проверяем: это AJAX-запрос и ответ — redirect на Keycloak?
        if (
            response.status_code in (301, 302, 303, 307, 308)
            and self._is_ajax(request)
            and self._is_oidc_redirect(response)
        ):
            logger.info(f"AJAX request to {request.path} got OIDC redirect, returning 401 instead")
            return JsonResponse(
                {"error": "session_expired", "message": "Сессия истекла"},
                status=401,
            )

        return response

    def _is_ajax(self, request):
        # Явный заголовок от fetchApi и jQuery
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return True
        # Браузер ставит Sec-Fetch-Mode: navigate только для обычной навигации.
        # fetch() запросы получают cors/same-origin/no-cors.
        sec_fetch_mode = request.headers.get("Sec-Fetch-Mode", "")
        if sec_fetch_mode and sec_fetch_mode != "navigate":
            return True
        return False

    def _is_oidc_redirect(self, response):
        location = response.get("Location", "")
        return "/openid-connect/auth" in location or "/protocol/openid-connect/" in location


def _get_client_ip(request):
    """
    Получение IP адреса клиента.
    Используем REMOTE_ADDR как надёжный источник.
    X-Forwarded-For легко подделать, поэтому доверяем ему только если
    настроен список доверенных прокси в settings.TRUSTED_PROXY_IPS.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "")
    trusted_proxies = getattr(settings, "TRUSTED_PROXY_IPS", None)
    if trusted_proxies and remote_addr in trusted_proxies:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Берём правый IP перед нашим доверенным прокси (последний добавленный прокси)
            ips = [ip.strip() for ip in x_forwarded_for.split(",")]
            return ips[-1] if ips else remote_addr
    return remote_addr


class ErrorHandlingMiddleware:
    """
    Middleware для улучшенной обработки ошибок и логирования.
    Работает в дополнение к встроенным обработчикам Django.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """
        Обрабатывает исключения, которые не были перехвачены в views.
        """
        # Логируем исключение с полной информацией
        logger.error(
            f"Exception in view: {request.path}",
            exc_info=True,
            extra={
                "request": request,
                "user": getattr(request, "user", None),
                "ip": self.get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "method": request.method,
                "query_params": dict(request.GET),
                "post_data_keys": list(request.POST.keys()) if hasattr(request, "POST") else [],
            },
        )

        # В DEBUG режиме позволяем Django показать детальную страницу ошибки
        if settings.DEBUG:
            return None

        # В production возвращаем красивые страницы ошибок
        try:
            if isinstance(exception, Http404):
                return self.handle_404(request, exception)
            elif isinstance(exception, PermissionDenied):
                return self.handle_403(request, exception)
            elif isinstance(exception, SuspiciousOperation):
                return self.handle_400(request, exception)
            else:
                return self.handle_500(request, exception)
        except Exception as e:
            # Если даже обработка ошибки вызвала ошибку, возвращаем базовый ответ
            logger.critical(f"Error in error handler: {e}", exc_info=True)
            return HttpResponseServerError("Internal Server Error")

    def handle_404(self, request, exception):
        """Обработка 404 ошибок"""
        logger.warning(f"404 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}")
        return render(
            request,
            "404.html",
            {
                "request": request,
                "exception": exception,
            },
            status=404,
        )

    def handle_403(self, request, exception):
        """Обработка 403 ошибок"""
        logger.warning(f"403 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}")
        return render(
            request,
            "403.html",
            {
                "request": request,
                "exception": exception,
            },
            status=403,
        )

    def handle_400(self, request, exception):
        """Обработка 400 ошибок"""
        logger.warning(f"400 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}")
        return render(
            request,
            "400.html",
            {
                "request": request,
                "exception": exception,
            },
            status=400,
        )

    @requires_csrf_token
    def handle_500(self, request, exception):
        """Обработка 500 ошибок"""
        logger.error(f"500 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}")
        return render(
            request,
            "500.html",
            {
                "request": request,
            },
            status=500,
        )

    def get_client_ip(self, request):
        return _get_client_ip(request)


class SecurityHeadersMiddleware:
    """
    Middleware для добавления заголовков безопасности.
    """

    # Пути, которые разрешено загружать в iframe (для silent re-auth)
    IFRAME_ALLOWED_PREFIXES = ("/oidc/", "/api/reauth-complete/")

    def __init__(self, get_response):
        self.get_response = get_response
        # Keycloak domain для frame-src (silent re-auth через iframe)
        keycloak_url = getattr(settings, "KEYCLOAK_SERVER_URL", "")
        if keycloak_url:
            self.frame_src = f"'self' {keycloak_url}"
        else:
            self.frame_src = "'self'"

    def __call__(self, request):
        response = self.get_response(request)

        # Добавляем заголовки безопасности
        if not settings.DEBUG:
            response["X-Content-Type-Options"] = "nosniff"

            # Не переписываем X-Frame-Options если он уже установлен
            # (например, через декоратор @xframe_options_exempt или reauth_complete view)
            if "X-Frame-Options" not in response:
                # Разрешаем OIDC-пути в iframe для silent re-auth
                if request.path.startswith(self.IFRAME_ALLOWED_PREFIXES):
                    response["X-Frame-Options"] = "SAMEORIGIN"
                else:
                    response["X-Frame-Options"] = "DENY"

            response["X-XSS-Protection"] = "1; mode=block"
            response["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Не переписываем CSP если он уже установлен (например, для iframe proxy)
            if "Content-Security-Policy" not in response:
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                    "font-src 'self' cdn.jsdelivr.net; "
                    "img-src 'self' data:; "
                    f"frame-src {self.frame_src}; "
                    "connect-src 'self' ws: wss:;"
                )
                response["Content-Security-Policy"] = csp

        return response


class RequestLoggingMiddleware:
    """
    Middleware для логирования запросов (опциональный).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Логируем только важные запросы в production
        if not settings.DEBUG and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            logger.info(f"{request.method} {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}")

        response = self.get_response(request)

        # Логируем ошибки
        if response.status_code >= 400:
            logger.warning(
                f"{response.status_code} {request.method} {request.path} - "
                f"User: {request.user} - IP: {self.get_client_ip(request)}"
            )

        return response

    def get_client_ip(self, request):
        return _get_client_ip(request)
