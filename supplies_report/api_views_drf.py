"""
DRF API View wrappers для OpenAPI документации.
Обёртывают существующие Django views для совместимости с drf-spectacular.
Для PATCH endpoints используется GenericAPIView для auto-discovery serializer_class.
"""
import json

from django.http import HttpRequest
from django.utils.encoding import force_bytes
from rest_framework.decorators import api_view, permission_classes as drf_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_docs_decorators import (
    api_group_detail_schema,
    api_group_update_schema,
    api_groups_list_schema,
    api_item_update_schema,
)
from .serializers import (
    GroupUpdateRequestSerializer,
    ItemUpdateRequestSerializer,
)
from .views import (
    api_groups_list,
    api_group_detail,
    api_group_update,
    api_item_update,
)


def _wrap_json_response(http_response):
    """Конвертирует Django JsonResponse в DRF Response"""
    if hasattr(http_response, 'content'):
        try:
            data = json.loads(http_response.content.decode('utf-8'))
            return Response(data=data, status=http_response.status_code)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                data={"raw_content": http_response.content.decode('utf-8', errors='replace')},
                status=http_response.status_code
            )
    return Response(data={}, status=http_response.status_code)


def _make_mock_django_request(drf_request):
    """
    Создаёт mock Django request с данными из DRF Request.
    DRF уже прочитал тело запроса, поэтому мы не можем использовать request._request напрямую.
    """
    mock_request = HttpRequest()
    mock_request.method = drf_request.method
    mock_request.META = drf_request.META
    mock_request.user = drf_request.user
    mock_request._body = force_bytes(json.dumps(drf_request.data))
    return mock_request


# ──────────────────────────────────────────────────────────────────────────────
# GET endpoints (оставлены как @api_view функции)
# ──────────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_groups_list_schema
def api_groups_list_drf(request):
    """DRF wrapper для api_groups_list"""
    return _wrap_json_response(api_groups_list(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_group_detail_schema
def api_group_detail_drf(request, group_id):
    """DRF wrapper для api_group_detail"""
    return _wrap_json_response(api_group_detail(request, group_id))


# ──────────────────────────────────────────────────────────────────────────────
# PATCH endpoints (GenericAPIView для auto-discovery serializer_class)
# ──────────────────────────────────────────────────────────────────────────────

class GroupUpdateAPIView(APIView):
    """
    DRF wrapper для api_group_update.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = GroupUpdateRequestSerializer

    def patch(self, request, group_id):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_group_update(mock_request, group_id))


GroupUpdateAPIView.patch = api_group_update_schema(GroupUpdateAPIView.patch)


class ItemUpdateAPIView(APIView):
    """
    DRF wrapper для api_item_update.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ItemUpdateRequestSerializer

    def patch(self, request, item_id):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_item_update(mock_request, item_id))


ItemUpdateAPIView.patch = api_item_update_schema(ItemUpdateAPIView.patch)
