"""
DRF API View wrappers для OpenAPI документации.
Обёртывают существующие Django views для совместимости с drf-spectacular.
Для POST endpoints используется GenericAPIView для auto-discovery serializer_class.
"""

import json

from django.http import HttpRequest
from django.utils.encoding import force_bytes
from rest_framework.decorators import api_view, permission_classes as drf_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_docs_decorators import (
    api_change_history_schema,
    api_device_report_schema,
    api_glpi_export_status_schema,
    api_month_changes_list_schema,
    api_month_diff_schema,
    api_month_detail_schema,
    api_month_users_stats_schema,
    api_months_list_schema,
    api_reset_manual_flag_schema,
    api_start_glpi_export_schema,
    api_sync_from_inventory_schema,
    api_toggle_auto_sync_schema,
    api_toggle_month_published_schema,
    api_toggle_serial_override_schema,
    api_update_counters_schema,
    api_delete_month_schema,
)
from .serializers import (
    DeleteMonthRequestSerializer,
    GLPIExportStartRequestSerializer,
    ResetManualRequestSerializer,
    SerialOverrideRequestSerializer,
    ToggleAutoSyncRequestSerializer,
    ToggleMonthPublishedRequestSerializer,
    UpdateCountersRequestSerializer,
)
from .views import (
    api_sync_from_inventory,
    api_update_counters,
    api_change_history,
    api_reset_manual_flag,
    api_months_list,
    api_month_diff,
    api_month_detail,
    api_toggle_serial_override,
    api_toggle_month_published,
    api_toggle_auto_sync,
    api_delete_month,
    api_month_users_stats,
    api_month_changes_list,
    api_device_report,
    api_start_glpi_export,
    api_glpi_export_status,
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
@api_change_history_schema
def api_change_history_drf(request, pk):
    """DRF wrapper для api_change_history"""
    return _wrap_json_response(api_change_history(request, pk))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_months_list_schema
def api_months_list_drf(request):
    """DRF wrapper для api_months_list"""
    return _wrap_json_response(api_months_list(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_month_diff_schema
def api_month_diff_drf(request, year, month):
    """DRF wrapper для api_month_diff"""
    return _wrap_json_response(api_month_diff(request, year, month))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_month_detail_schema
def api_month_detail_drf(request, year, month):
    """DRF wrapper для api_month_detail"""
    return _wrap_json_response(api_month_detail(request, year, month))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_month_users_stats_schema
def api_month_users_stats_drf(request, year, month):
    """DRF wrapper для api_month_users_stats"""
    return _wrap_json_response(api_month_users_stats(request, year, month))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_month_changes_list_schema
def api_month_changes_list_drf(request, year, month):
    """DRF wrapper для api_month_changes_list"""
    return _wrap_json_response(api_month_changes_list(request, year, month))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_device_report_schema
def api_device_report_drf(request, year, month, serial_number):
    """DRF wrapper для api_device_report"""
    return _wrap_json_response(api_device_report(request, year, month, serial_number))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_glpi_export_status_schema
def api_glpi_export_status_drf(request, task_id):
    """DRF wrapper для api_glpi_export_status"""
    return _wrap_json_response(api_glpi_export_status(request, task_id))


# ──────────────────────────────────────────────────────────────────────────────
# POST endpoints (GenericAPIView для auto-discovery serializer_class)
# ──────────────────────────────────────────────────────────────────────────────


class SyncFromInventoryAPIView(APIView):
    """
    DRF wrapper для api_sync_from_inventory.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, year, month):
        return _wrap_json_response(api_sync_from_inventory(request._request, year, month))


SyncFromInventoryAPIView.post = api_sync_from_inventory_schema(SyncFromInventoryAPIView.post)


class UpdateCountersAPIView(APIView):
    """
    DRF wrapper для api_update_counters.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UpdateCountersRequestSerializer

    def post(self, request, pk):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_update_counters(mock_request, pk))


UpdateCountersAPIView.post = api_update_counters_schema(UpdateCountersAPIView.post)


class ResetManualFlagAPIView(APIView):
    """
    DRF wrapper для api_reset_manual_flag.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ResetManualRequestSerializer

    def post(self, request, pk):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_reset_manual_flag(mock_request, pk))


ResetManualFlagAPIView.post = api_reset_manual_flag_schema(ResetManualFlagAPIView.post)


class ToggleSerialOverrideAPIView(APIView):
    """
    DRF wrapper для api_toggle_serial_override.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SerialOverrideRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_toggle_serial_override(mock_request))


ToggleSerialOverrideAPIView.post = api_toggle_serial_override_schema(ToggleSerialOverrideAPIView.post)


class ToggleMonthPublishedAPIView(APIView):
    """
    DRF wrapper для api_toggle_month_published.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ToggleMonthPublishedRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_toggle_month_published(mock_request))


ToggleMonthPublishedAPIView.post = api_toggle_month_published_schema(ToggleMonthPublishedAPIView.post)


class ToggleAutoSyncAPIView(APIView):
    """
    DRF wrapper для api_toggle_auto_sync.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ToggleAutoSyncRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_toggle_auto_sync(mock_request))


ToggleAutoSyncAPIView.post = api_toggle_auto_sync_schema(ToggleAutoSyncAPIView.post)


class DeleteMonthAPIView(APIView):
    """
    DRF wrapper для api_delete_month.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DeleteMonthRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_delete_month(mock_request))


DeleteMonthAPIView.post = api_delete_month_schema(DeleteMonthAPIView.post)


class StartGLPIExportAPIView(APIView):
    """
    DRF wrapper для api_start_glpi_export.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = GLPIExportStartRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(api_start_glpi_export(mock_request))


StartGLPIExportAPIView.post = api_start_glpi_export_schema(StartGLPIExportAPIView.post)
