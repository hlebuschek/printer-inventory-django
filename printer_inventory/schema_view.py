# printer_inventory/schema_view.py
"""
Кастомный view для отдачи OpenAPI схемы.
Заменяет drf-spectacular SpectacularAPIView.
"""
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_GET


def check_api_docs_access(user):
    """
    Проверяет доступ к API документации.
    Требует специальное право inventory.view_api_docs.
    """
    return user.has_perm("inventory.view_api_docs")


@require_GET
@login_required
def custom_schema_view(request):
    """
    Отдаёт OpenAPI 3.0 схему в формате JSON.
    Требует аутентификации и права inventory.view_api_docs.
    """
    if not check_api_docs_access(request.user):
        raise PermissionDenied("У вас нет прав для просмотра API документации (требуется inventory.view_api_docs)")

    from .openapi_schema import generate_openapi_schema

    schema = generate_openapi_schema(request)
    return JsonResponse(schema, json_dumps_params={'indent': 2, 'ensure_ascii': False})
