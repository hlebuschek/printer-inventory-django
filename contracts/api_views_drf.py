"""
DRF API View wrappers для OpenAPI документации.
Обёртывают существующие Django views для совместимости с drf-spectacular.
"""
import json

from rest_framework.decorators import api_view, permission_classes as drf_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .api_docs_decorators import (
    api_contract_devices_schema,
    api_contract_filters_schema,
    api_device_models_by_manufacturer_schema,
)
from .api_views import (
    api_contract_devices,
    api_contract_filters,
    api_device_models_by_manufacturer,
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


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_contract_devices_schema
def api_contract_devices_drf(request):
    """DRF wrapper для api_contract_devices"""
    return _wrap_json_response(api_contract_devices(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_contract_filters_schema
def api_contract_filters_drf(request):
    """DRF wrapper для api_contract_filters"""
    return _wrap_json_response(api_contract_filters(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_device_models_by_manufacturer_schema
def api_device_models_by_manufacturer_drf(request):
    """DRF wrapper для api_device_models_by_manufacturer"""
    return _wrap_json_response(api_device_models_by_manufacturer(request))
