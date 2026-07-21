# inventory/api_views_drf.py
"""
DRF API View wrappers для OpenAPI документации.
Обёртывают существующие Django views для совместимости с drf-spectacular.
Для POST endpoints используется GenericAPIView для auto-discovery serializer_class.
"""

import json

from rest_framework.decorators import api_view, permission_classes as drf_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_docs_decorators import (
    api_all_printer_models_schema,
    api_models_by_manufacturer_schema,
    api_printer_detail_schema,
    api_printer_replacement_history_schema,
    api_printers_schema,
    api_probe_serial_schema,
    api_status_statistics_schema,
    api_system_status_schema,
)
from .serializers import ProbeSerialRequestSerializer
from .views.api_views import (
    api_all_printer_models,
    api_models_by_manufacturer,
    api_printer,
    api_printer_replacement_history,
    api_printers,
    api_probe_serial,
    api_status_statistics,
    api_system_status,
)


def _wrap_json_response(http_response):
    """Конвертирует Django JsonResponse в DRF Response"""
    if hasattr(http_response, "content"):
        try:
            data = json.loads(http_response.content.decode("utf-8"))
            return Response(data=data, status=http_response.status_code)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                data={"raw_content": http_response.content.decode("utf-8", errors="replace")},
                status=http_response.status_code,
            )
    return Response(data={}, status=http_response.status_code)


# ──────────────────────────────────────────────────────────────────────────────
# GET endpoints (оставлены как @api_view функции)
# ──────────────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_printers_schema
def api_printers_drf(request):
    """DRF wrapper для api_printers"""
    return _wrap_json_response(api_printers(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_printer_detail_schema
def api_printer_detail_drf(request, pk):
    """DRF wrapper для api_printer"""
    return _wrap_json_response(api_printer(request, pk))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_system_status_schema
def api_system_status_drf(request):
    """DRF wrapper для api_system_status"""
    return _wrap_json_response(api_system_status(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_status_statistics_schema
def api_status_statistics_drf(request):
    """DRF wrapper для api_status_statistics"""
    return _wrap_json_response(api_status_statistics(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_models_by_manufacturer_schema
def api_models_by_manufacturer_drf(request):
    """DRF wrapper для api_models_by_manufacturer"""
    return _wrap_json_response(api_models_by_manufacturer(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_all_printer_models_schema
def api_all_printer_models_drf(request):
    """DRF wrapper для api_all_printer_models"""
    return _wrap_json_response(api_all_printer_models(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_printer_replacement_history_schema
def api_printer_replacement_history_drf(request, pk):
    """DRF wrapper для api_printer_replacement_history"""
    return _wrap_json_response(api_printer_replacement_history(request, pk))


# ──────────────────────────────────────────────────────────────────────────────
# POST endpoints (GenericAPIView для auto-discovery serializer_class)
# ──────────────────────────────────────────────────────────────────────────────


class ProbeSerialAPIView(APIView):
    """
    DRF wrapper для api_probe_serial.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProbeSerialRequestSerializer

    def post(self, request):
        # DRF Request уже прочитал тело, поэтому создаём mock Django request
        # с данными из request.data
        from django.http import HttpRequest
        from django.utils.encoding import force_bytes

        mock_request = HttpRequest()
        mock_request.method = "POST"
        mock_request.META = request.META
        mock_request.user = request.user
        mock_request._body = force_bytes(json.dumps(request.data))

        return _wrap_json_response(api_probe_serial(mock_request))


ProbeSerialAPIView.post = api_probe_serial_schema(ProbeSerialAPIView.post)
