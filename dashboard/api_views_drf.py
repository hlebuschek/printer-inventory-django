"""
DRF API View wrappers для OpenAPI документации.
Обёртывают существующие Django views для совместимости с drf-spectacular.
"""
import json

from rest_framework.decorators import api_view, permission_classes as drf_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .api_docs_decorators import (
    api_glpi_cross_check_schema,
    api_low_consumables_schema,
    api_org_devices_schema,
    api_org_summary_schema,
    api_organizations_schema,
    api_printer_status_schema,
    api_poll_stats_schema,
    api_print_trend_schema,
    api_problem_printers_schema,
    api_recent_activity_schema,
)
from .views.api_views import (
    api_printer_status,
    api_poll_stats,
    api_low_consumables,
    api_problem_printers,
    api_print_trend,
    api_org_devices,
    api_org_summary,
    api_recent_activity,
    api_organizations,
    api_glpi_cross_check,
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
@api_printer_status_schema
def api_printer_status_drf(request):
    """DRF wrapper для api_printer_status"""
    return _wrap_json_response(api_printer_status(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_poll_stats_schema
def api_poll_stats_drf(request):
    """DRF wrapper для api_poll_stats"""
    return _wrap_json_response(api_poll_stats(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_low_consumables_schema
def api_low_consumables_drf(request):
    """DRF wrapper для api_low_consumables"""
    return _wrap_json_response(api_low_consumables(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_problem_printers_schema
def api_problem_printers_drf(request):
    """DRF wrapper для api_problem_printers"""
    return _wrap_json_response(api_problem_printers(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_print_trend_schema
def api_print_trend_drf(request):
    """DRF wrapper для api_print_trend"""
    return _wrap_json_response(api_print_trend(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_org_devices_schema
def api_org_devices_drf(request):
    """DRF wrapper для api_org_devices"""
    return _wrap_json_response(api_org_devices(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_org_summary_schema
def api_org_summary_drf(request):
    """DRF wrapper для api_org_summary"""
    return _wrap_json_response(api_org_summary(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_recent_activity_schema
def api_recent_activity_drf(request):
    """DRF wrapper для api_recent_activity"""
    return _wrap_json_response(api_recent_activity(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_organizations_schema
def api_organizations_drf(request):
    """DRF wrapper для api_organizations"""
    return _wrap_json_response(api_organizations(request))


@api_view(["GET"])
@drf_permission([IsAuthenticated])
@api_glpi_cross_check_schema
def api_glpi_cross_check_drf(request):
    """DRF wrapper для api_glpi_cross_check"""
    return _wrap_json_response(api_glpi_cross_check(request))
