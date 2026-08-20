# printer_inventory/api_docs_views.py
"""
Защищённые view для API документации.
Требуют аутентификации и специального права view_api_docs.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerSplitView


def check_api_docs_access(user):
    """
    Проверяет доступ к API документации.
    Требует специальное право inventory.view_api_docs.
    НЕ выдаётся автоматически группам "Наблюдатель".
    """
    return user.has_perm("inventory.view_api_docs")


class APIAccessMixin:
    """Mixin для проверки прав доступа к API документации."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not check_api_docs_access(request.user):
            raise PermissionDenied("У вас нет прав для просмотра API документации (требуется inventory.view_api_docs)")
        return super().dispatch(request, *args, **kwargs)


@method_decorator(login_required, name="dispatch")
class PrivateSwaggerView(APIAccessMixin, SpectacularSwaggerSplitView):
    """
    Swagger UI с требованием аутентификации и специального права.
    Доступен только с правом inventory.view_api_docs.

    Split-вариант отдаёт инициализирующий JS отдельным запросом, а не инлайном:
    его шаблон живёт в пакете и nonce из CSP туда не подставить.
    """

    pass


@method_decorator(login_required, name="dispatch")
class PrivateRedocView(APIAccessMixin, SpectacularRedocView):
    """
    ReDoc с требованием аутентификации и специального права.
    Доступен только с правом inventory.view_api_docs.
    """

    pass


class PublicSchemaView(SpectacularAPIView):
    """
    OpenAPI schema БЕЗ авторизации.
    Swagger UI и ReDoc должны получить схему до авторизации.
    """

    pass
