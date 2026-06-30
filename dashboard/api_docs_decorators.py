# dashboard/api_docs_decorators.py
"""
OpenAPI декораторы для dashboard API views.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.fields import BooleanField, CharField, IntegerField

PRINTER_STATUS_SCHEMA = inline_serializer(
    name="PrinterStatus",
    fields={
        "id": IntegerField(),
        "ip_address": CharField(),
        "serial_number": CharField(allow_null=True),
        "organization": CharField(allow_null=True),
        "last_inventory": CharField(allow_null=True),
        "status": CharField(),
        "has_problem": BooleanField(),
    },
)

POLL_STATS_SCHEMA = inline_serializer(
    name="PollStats",
    fields={
        "total": IntegerField(),
        "successful": IntegerField(),
        "failed": IntegerField(),
        "success_rate": CharField(),
        "last_poll": CharField(allow_null=True),
    },
)

LOW_CONSUMABLES_SCHEMA = inline_serializer(
    name="LowConsumables",
    fields={
        "printer": CharField(),
        "organization": CharField(),
        "toner_black": IntegerField(allow_null=True),
        "toner_cyan": IntegerField(allow_null=True),
        "toner_magenta": IntegerField(allow_null=True),
        "toner_yellow": IntegerField(allow_null=True),
    },
)

ORG_DEVICES_SCHEMA = inline_serializer(
    name="OrgDevices",
    fields={
        "organization": CharField(),
        "total_printers": IntegerField(),
        "active_printers": IntegerField(),
        "problem_printers": IntegerField(),
    },
)

API_ORGANIZATIONS_SCHEMA = inline_serializer(
    name="APIOrganizations",
    fields={
        "id": IntegerField(),
        "name": CharField(),
        "printer_count": IntegerField(),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

api_printer_status_schema = extend_schema(
    operation_id="api_printer_status",
    tags=["dashboard"],
    summary="Статус принтеров",
    description="Текущий статус всех принтеров",
    responses={
        200: OpenApiResponse(response=serializers.ListField(child=PRINTER_STATUS_SCHEMA), description="Статус принтеров"),
    },
)

api_poll_stats_schema = extend_schema(
    operation_id="api_poll_stats",
    tags=["dashboard"],
    summary="Статистика опросов",
    description="Общая статистика по опросам принтеров",
    responses={
        200: OpenApiResponse(response=POLL_STATS_SCHEMA, description="Статистика"),
    },
)

api_low_consumables_schema = extend_schema(
    operation_id="api_low_consumables",
    tags=["dashboard"],
    summary="Мало расходников",
    description="Принтеры с низким уровнем тонера/картриджей",
    responses={
        200: OpenApiResponse(response=serializers.ListField(child=LOW_CONSUMABLES_SCHEMA), description="Список"),
    },
)

api_problem_printers_schema = extend_schema(
    operation_id="api_problem_printers",
    tags=["dashboard"],
    summary="Проблемные принтеры",
    description="Принтеры с проблемами (не опрашиваются, ошибки и т.д.)",
    responses={
        200: OpenApiResponse(description="Список проблемных принтеров"),
    },
)

api_print_trend_schema = extend_schema(
    operation_id="api_print_trend",
    tags=["dashboard"],
    summary="Тренд печати",
    description="Статистика печати по месяцам",
    responses={
        200: OpenApiResponse(description="Данные тренда"),
    },
)

api_org_devices_schema = extend_schema(
    operation_id="api_org_devices",
    tags=["dashboard"],
    summary="Устройства по организациям",
    description="Количество устройств по организациям",
    responses={
        200: OpenApiResponse(response=serializers.ListField(child=ORG_DEVICES_SCHEMA), description="Список"),
    },
)

api_org_summary_schema = extend_schema(
    operation_id="api_org_summary",
    tags=["dashboard"],
    summary="Сводка по организациям",
    description="Подробная сводка по всем организациям",
    responses={
        200: OpenApiResponse(description="Сводка"),
    },
)

api_recent_activity_schema = extend_schema(
    operation_id="api_recent_activity",
    tags=["dashboard"],
    summary="Последняя активность",
    description="Последние действия в системе",
    responses={
        200: OpenApiResponse(description="Активность"),
    },
)

api_organizations_schema = extend_schema(
    operation_id="api_organizations",
    tags=["dashboard"],
    summary="Список организаций",
    description="Все организации с количеством принтеров",
    responses={
        200: OpenApiResponse(response=serializers.ListField(child=API_ORGANIZATIONS_SCHEMA), description="Список"),
    },
)

api_glpi_cross_check_schema = extend_schema(
    operation_id="api_glpi_cross_check",
    tags=["dashboard"],
    summary="GLPI перекрёстная проверка",
    description="Результаты перекрёстной проверки с GLPI",
    responses={
        200: OpenApiResponse(description="Результаты проверки"),
    },
)
