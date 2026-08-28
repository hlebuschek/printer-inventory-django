import logging

from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

logger = logging.getLogger(__name__)

# ВАЖНО: возвращаем результат render(..., status=...) напрямую.
# Оборачивание render() в HttpResponseForbidden(...) передаёт HttpResponse как content,
# сеттер content вызывает у него .close() → досрочный сигнал request_finished →
# close_old_connections() закрывает соединение с БД посреди запроса.


def custom_404(request, exception):
    """Кастомная страница 404 - Страница не найдена"""
    logger.warning(f'404 error: {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}')

    return render(request, "404.html", {"request": request, "exception": exception}, status=404)


def custom_403(request, exception):
    """Кастомная страница 403 - Доступ запрещён"""
    logger.warning(f'403 error: {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}')

    return render(request, "403.html", {"request": request, "exception": exception}, status=403)


@requires_csrf_token
def custom_500(request):
    """Кастомная страница 500 - Внутренняя ошибка сервера"""
    logger.error(f'500 error: {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}')

    return render(request, "500.html", {"request": request}, status=500)


def custom_400(request, exception):
    """Кастомная страница 400 - Неверный запрос"""
    logger.warning(f'400 error: {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}')

    return render(request, "400.html", {"request": request, "exception": exception}, status=400)


def custom_csrf_failure(request, reason=""):
    """Кастомная страница для ошибок CSRF"""
    logger.warning(
        f'CSRF failure: {request.path} - Reason: {reason} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}'
    )

    return render(request, "403_csrf.html", {"request": request, "reason": reason}, status=403)


def generic_error(request, error_code, error_title=None, error_message=None):
    """Универсальная страница для других ошибок"""
    logger.warning(f'{error_code} error: {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}')

    context = {
        "request": request,
        "error_code": str(error_code),
        "error_title": error_title,
        "error_message": error_message,
    }
    return render(request, "error.html", context, status=error_code)


# Обработчики для специфичных ошибок
def custom_401(request, exception=None):
    """Требуется авторизация"""
    return generic_error(
        request, 401, "Требуется авторизация", "Для доступа к этой странице необходимо войти в систему."
    )


def custom_405(request, exception=None):
    """Метод не разрешён"""
    logger.warning(
        f'405 error: {request.method} {request.path} - User: {request.user} - IP: {request.META.get("REMOTE_ADDR")}'
    )

    return render(request, "405.html", {"request": request, "exception": exception}, status=405)


def custom_429(request, exception=None):
    """Слишком много запросов"""
    return generic_error(
        request,
        429,
        "Слишком много запросов",
        "Вы превысили лимит запросов. Пожалуйста, подождите перед повторной попыткой.",
    )


def custom_502(request, exception=None):
    """Неверный шлюз"""
    return generic_error(request, 502, "Неверный шлюз", "Сервер получил неверный ответ от вышестоящего сервера.")


def custom_503(request, exception=None):
    """Сервис недоступен"""
    return generic_error(
        request, 503, "Сервис недоступен", "Сервис временно недоступен. Возможно, проводятся технические работы."
    )


def custom_504(request, exception=None):
    """Время ожидания шлюза истекло"""
    return generic_error(
        request, 504, "Время ожидания истекло", "Сервер не получил своевременный ответ от вышестоящего сервера."
    )


# Функция-хелпер для использования в view
def render_error_response(request, code, title=None, message=None):
    """
    Хелпер для быстрого рендера страниц ошибок в собственных view.

    Использование:
    return render_error_response(request, 403, 'Недостаточно прав', 'У вас нет прав для выполнения этой операции.')
    """
    return generic_error(request, code, title, message)
