import logging
import traceback
from django.http import HttpResponseServerError, Http404
from django.shortcuts import render
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.views.decorators.csrf import requires_csrf_token

logger = logging.getLogger('printer_inventory.middleware')


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
            f'Exception in view: {request.path}',
            exc_info=True,
            extra={
                'request': request,
                'user': getattr(request, 'user', None),
                'ip': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'method': request.method,
                'query_params': dict(request.GET),
                'post_data_keys': list(request.POST.keys()) if hasattr(request, 'POST') else [],
            }
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
            logger.critical(f'Error in error handler: {e}', exc_info=True)
            return HttpResponseServerError("Internal Server Error")

    def handle_404(self, request, exception):
        """Обработка 404 ошибок"""
        logger.warning(f'404 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}')
        return render(request, '404.html', {
            'request': request,
            'exception': exception,
        }, status=404)

    def handle_403(self, request, exception):
        """Обработка 403 ошибок"""
        logger.warning(f'403 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}')
        return render(request, '403.html', {
            'request': request,
            'exception': exception,
        }, status=403)

    def handle_400(self, request, exception):
        """Обработка 400 ошибок"""
        logger.warning(f'400 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}')
        return render(request, '400.html', {
            'request': request,
            'exception': exception,
        }, status=400)

    @requires_csrf_token
    def handle_500(self, request, exception):
        """Обработка 500 ошибок"""
        logger.error(f'500 error: {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}')
        return render(request, '500.html', {
            'request': request,
        }, status=500)

    def get_client_ip(self, request):
        """Получение IP адреса клиента с учётом прокси"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class SecurityHeadersMiddleware:
    """
    Middleware для добавления заголовков безопасности.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Добавляем заголовки безопасности
        if not settings.DEBUG:
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            # Content Security Policy (базовый)
            csp = "default-src 'self'; " \
                  "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; " \
                  "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; " \
                  "font-src 'self' cdn.jsdelivr.net; " \
                  "img-src 'self' data:; " \
                  "connect-src 'self' ws: wss:;"
            response['Content-Security-Policy'] = csp

        return response


class RequestLoggingMiddleware:
    """
    Middleware для логирования запросов (опциональный).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Логируем только важные запросы в production
        if not settings.DEBUG and request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            logger.info(
                f'{request.method} {request.path} - User: {request.user} - IP: {self.get_client_ip(request)}'
            )

        response = self.get_response(request)

        # Логируем ошибки
        if response.status_code >= 400:
            logger.warning(
                f'{response.status_code} {request.method} {request.path} - '
                f'User: {request.user} - IP: {self.get_client_ip(request)}'
            )

        return response

    def get_client_ip(self, request):
        """Получение IP адреса клиента с учётом прокси"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip