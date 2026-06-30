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
    api_okdesk_active_grouped_schema,
    api_okdesk_analytics_schema,
    api_okdesk_authors_schema,
    api_okdesk_by_status_schema,
    api_okdesk_closed_schema,
    api_okdesk_daily_comments_schema,
    api_okdesk_daily_stats_schema,
    api_okdesk_issue_detail_schema,
    check_device_glpi_schema,
    check_multiple_devices_glpi_schema,
    create_okdesk_issue_schema,
    export_okdesk_active_all_schema,
    export_okdesk_active_filtered_schema,
    export_okdesk_by_status_schema,
    export_okdesk_closed_filtered_schema,
    export_okdesk_closed_schema,
    export_okdesk_created_schema,
    get_device_sync_status_schema,
    get_devices_not_in_glpi_schema,
    get_glpi_conflicts_schema,
    get_okdesk_issues_schema,
    okdesk_export_download_schema,
    okdesk_post_comment_schema,
    okdesk_refresh_issue_comments_schema,
    okdesk_sync_now_schema,
    okdesk_sync_status_schema,
)
from .serializers import (
    CheckDeviceGLPIRequestSerializer,
    CheckMultipleDevicesGLPIRequestSerializer,
    CreateOkdeskIssueRequestSerializer,
    PostCommentRequestSerializer,
    SyncNowRequestSerializer,
)
from .views import (
    check_device_glpi,
    check_multiple_devices_glpi,
    create_okdesk_issue,
    export_okdesk_active_all,
    export_okdesk_active_filtered,
    export_okdesk_closed,
    export_okdesk_closed_filtered,
    export_okdesk_created,
    export_okdesk_by_status,
    get_device_sync_status,
    get_devices_not_in_glpi_view,
    get_glpi_conflicts,
    get_okdesk_issues,
    okdesk_export_download,
    okdesk_post_comment,
    okdesk_refresh_issue_comments,
    okdesk_sync_now,
    okdesk_sync_status,
    api_okdesk_daily_stats,
    api_okdesk_daily_comments,
    api_okdesk_active_grouped,
    api_okdesk_by_status,
    api_okdesk_analytics,
    api_okdesk_authors,
    api_okdesk_closed,
    api_okdesk_issue_detail,
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
@get_device_sync_status_schema
def get_device_sync_status_drf(request, device_id):
    """DRF wrapper для get_device_sync_status"""
    return _wrap_json_response(get_device_sync_status(request, device_id))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@get_glpi_conflicts_schema
def get_glpi_conflicts_drf(request):
    """DRF wrapper для get_glpi_conflicts"""
    return _wrap_json_response(get_glpi_conflicts(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@get_devices_not_in_glpi_schema
def get_devices_not_in_glpi_drf(request):
    """DRF wrapper для get_devices_not_in_glpi_view"""
    return _wrap_json_response(get_devices_not_in_glpi_view(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@get_okdesk_issues_schema
def get_okdesk_issues_drf(request, device_id):
    """DRF wrapper для get_okdesk_issues"""
    return _wrap_json_response(get_okdesk_issues(request, device_id))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_daily_stats_schema
def api_okdesk_daily_stats_drf(request):
    """DRF wrapper для api_okdesk_daily_stats"""
    return _wrap_json_response(api_okdesk_daily_stats(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_daily_comments_schema
def api_okdesk_daily_comments_drf(request):
    """DRF wrapper для api_okdesk_daily_comments"""
    return _wrap_json_response(api_okdesk_daily_comments(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_active_grouped_schema
def api_okdesk_active_grouped_drf(request):
    """DRF wrapper для api_okdesk_active_grouped"""
    return _wrap_json_response(api_okdesk_active_grouped(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_by_status_schema
def api_okdesk_by_status_drf(request, status_name):
    """DRF wrapper для api_okdesk_by_status"""
    return _wrap_json_response(api_okdesk_by_status(request, status_name))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_analytics_schema
def api_okdesk_analytics_drf(request):
    """DRF wrapper для api_okdesk_analytics"""
    return _wrap_json_response(api_okdesk_analytics(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_authors_schema
def api_okdesk_authors_drf(request):
    """DRF wrapper для api_okdesk_authors"""
    return _wrap_json_response(api_okdesk_authors(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_closed_schema
def api_okdesk_closed_drf(request):
    """DRF wrapper для api_okdesk_closed"""
    return _wrap_json_response(api_okdesk_closed(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_okdesk_issue_detail_schema
def api_okdesk_issue_detail_drf(request, issue_id):
    """DRF wrapper для api_okdesk_issue_detail"""
    return _wrap_json_response(api_okdesk_issue_detail(request, issue_id))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_created_schema
def export_okdesk_created_drf(request, date_str):
    """DRF wrapper для export_okdesk_created"""
    return _wrap_json_response(export_okdesk_created(request, date_str))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_closed_schema
def export_okdesk_closed_drf(request, date_str):
    """DRF wrapper для export_okdesk_closed"""
    return _wrap_json_response(export_okdesk_closed(request, date_str))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_by_status_schema
def export_okdesk_by_status_drf(request, status_name):
    """DRF wrapper для export_okdesk_by_status"""
    return _wrap_json_response(export_okdesk_by_status(request, status_name))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_active_all_schema
def export_okdesk_active_all_drf(request):
    """DRF wrapper для export_okdesk_active_all"""
    return _wrap_json_response(export_okdesk_active_all(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_active_filtered_schema
def export_okdesk_active_filtered_drf(request):
    """DRF wrapper для export_okdesk_active_filtered"""
    return _wrap_json_response(export_okdesk_active_filtered(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@export_okdesk_closed_filtered_schema
def export_okdesk_closed_filtered_drf(request):
    """DRF wrapper для export_okdesk_closed_filtered"""
    return _wrap_json_response(export_okdesk_closed_filtered(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@okdesk_export_download_schema
def okdesk_export_download_drf(request, task_id):
    """DRF wrapper для okdesk_export_download"""
    return _wrap_json_response(okdesk_export_download(request, task_id))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@okdesk_sync_status_schema
def okdesk_sync_status_drf(request):
    """DRF wrapper для okdesk_sync_status"""
    return _wrap_json_response(okdesk_sync_status(request))


# ──────────────────────────────────────────────────────────────────────────────
# POST endpoints (GenericAPIView для auto-discovery serializer_class)
# ──────────────────────────────────────────────────────────────────────────────

class CheckDeviceGLPIAPIView(APIView):
    """
    DRF wrapper для check_device_glpi.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CheckDeviceGLPIRequestSerializer

    def post(self, request, device_id):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(check_device_glpi(mock_request, device_id))


CheckDeviceGLPIAPIView.post = check_device_glpi_schema(CheckDeviceGLPIAPIView.post)


class CheckMultipleDevicesGLPIAPIView(APIView):
    """
    DRF wrapper для check_multiple_devices_glpi.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CheckMultipleDevicesGLPIRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(check_multiple_devices_glpi(mock_request))


CheckMultipleDevicesGLPIAPIView.post = check_multiple_devices_glpi_schema(CheckMultipleDevicesGLPIAPIView.post)


class CreateOkdeskIssueAPIView(APIView):
    """
    DRF wrapper для create_okdesk_issue.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOkdeskIssueRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(create_okdesk_issue(mock_request))


CreateOkdeskIssueAPIView.post = create_okdesk_issue_schema(CreateOkdeskIssueAPIView.post)


class OkdeskRefreshIssueCommentsAPIView(APIView):
    """
    DRF wrapper для okdesk_refresh_issue_comments.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, issue_id):
        return _wrap_json_response(okdesk_refresh_issue_comments(request._request, issue_id))


OkdeskRefreshIssueCommentsAPIView.post = okdesk_refresh_issue_comments_schema(OkdeskRefreshIssueCommentsAPIView.post)


class OkdeskPostCommentAPIView(APIView):
    """
    DRF wrapper для okdesk_post_comment.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PostCommentRequestSerializer

    def post(self, request, issue_id):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(okdesk_post_comment(mock_request, issue_id))


OkdeskPostCommentAPIView.post = okdesk_post_comment_schema(OkdeskPostCommentAPIView.post)


class OkdeskSyncNowAPIView(APIView):
    """
    DRF wrapper для okdesk_sync_now.
    GenericAPIView с serializer_class для auto-discovery в Swagger UI.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SyncNowRequestSerializer

    def post(self, request):
        mock_request = _make_mock_django_request(request)
        return _wrap_json_response(okdesk_sync_now(mock_request))


OkdeskSyncNowAPIView.post = okdesk_sync_now_schema(OkdeskSyncNowAPIView.post)
