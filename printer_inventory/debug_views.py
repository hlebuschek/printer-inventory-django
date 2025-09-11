"""
Debug views для тестирования обработчиков ошибок.
Работают только при DEBUG=True.
"""

from django.http import Http404, HttpResponseBadRequest
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


def test_404(request):
    """Тестовая 404 ошибка"""
    raise Http404("Это тестовая страница для проверки обработчика 404 ошибок")


def test_403(request):
    """Тестовая 403 ошибка"""
    raise PermissionDenied("Это тестовая страница для проверки обработчика 403 ошибок")


def test_400(request):
    """Тестовая 400 ошибка"""
    raise SuspiciousOperation("Это тестовая страница для проверки обработчика 400 ошибок")


@csrf_exempt
def test_500(request):
    """Тестовая 500 ошибка"""
    # Намеренно вызываем исключение
    raise Exception("Это тестовая страница для проверки обработчика 500 ошибок")


def test_405(request):
    """Тестовая 405 ошибка - разрешён только POST"""
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    return JsonResponse({'message': 'POST запрос успешно обработан'})


def test_csrf_form(request):
    """Форма для тестирования CSRF ошибки"""
    return render(request, 'debug/test_csrf.html')


@require_http_methods(["POST"])
def test_csrf_submit(request):
    """Обработчик формы без CSRF защиты - вызовет CSRF ошибку"""
    return JsonResponse({'message': 'Форма отправлена успешно'})


def error_test_menu(request):
    """Меню для тестирования всех типов ошибок"""
    return render(request, 'debug/error_test_menu.html')