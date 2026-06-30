# inventory/api_docs_decorators.py
"""
OpenAPI декораторы для существующих API views.
Добавляет документацию drf-spectacular к Django function-based views.
"""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.fields import BooleanField, CharField, IntegerField

from .serializers import ProbeSerialRequestSerializer

# ──────────────────────────────────────────────────────────────────────────────
# RESPONSE SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

PRINTER_ITEM_SCHEMA = inline_serializer(
    name="PrinterItem",
    fields={
        "id": IntegerField(help_text="ID"),
        "ip_address": CharField(help_text="IP-адрес"),
        "serial_number": CharField(help_text="Серийный номер", allow_null=True, allow_blank=True),
        "model": CharField(help_text="Модель (legacy)", allow_null=True, allow_blank=True),
        "organization": CharField(help_text="Организация", allow_null=True, allow_blank=True),
        "device_model": CharField(help_text="Модель устройства", allow_null=True),
        "manufacturer": CharField(help_text="Производитель", allow_null=True),
        "location": CharField(help_text="Расположение", allow_null=True, allow_blank=True),
        "is_active": BooleanField(help_text="Активен"),
        "snmp_community": CharField(help_text="SNMP community", allow_null=True, allow_blank=True),
        "connection_type": CharField(help_text="NETWORK/USB"),
        "polling_method": CharField(help_text="SNMP/WEB/USB_API"),
        "last_inventory": CharField(help_text="Последний опрос", allow_null=True),
        "last_inventory_status": CharField(help_text="Статус", allow_null=True),
        "a4_bw": IntegerField(help_text="A4 Ч/Б", allow_null=True),
        "a4_color": IntegerField(help_text="A4 цвет", allow_null=True),
        "a3_bw": IntegerField(help_text="A3 Ч/Б", allow_null=True),
        "a3_color": IntegerField(help_text="A3 цвет", allow_null=True),
    },
)

PRINTER_LIST_SCHEMA = inline_serializer(
    name="PrinterList",
    fields={
        "count": IntegerField(help_text="Всего"),
        "next": CharField(help_text="Следующая страница", allow_null=True, allow_blank=True),
        "previous": CharField(help_text="Предыдущая страница", allow_null=True, allow_blank=True),
        "results": serializers.ListField(child=PRINTER_ITEM_SCHEMA, help_text="Принтеры"),
    },
)

SYSTEM_STATUS_SCHEMA = inline_serializer(
    name="SystemStatus",
    fields={
        "celery": CharField(help_text="ok/down/unknown"),
        "redis": CharField(help_text="ok/down/unknown"),
        "database": CharField(help_text="ok/down/unknown"),
        "celery_workers": IntegerField(help_text="Кол-во воркеров", allow_null=True),
    },
)

STATUS_STATS_SCHEMA = inline_serializer(
    name="StatusStatistics",
    fields={
        "total": IntegerField(help_text="Всего принтеров"),
        "success": IntegerField(help_text="Успешные опросы"),
        "failed": IntegerField(help_text="Неудачные опросы"),
        "pending": IntegerField(help_text="Ожидают опроса"),
        "success_rate": CharField(help_text="% успешных"),
    },
)

ERROR_SCHEMA = inline_serializer(
    name="ErrorResponse",
    fields={
        "error": CharField(help_text="Тип ошибки"),
        "message": CharField(help_text="Сообщение"),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

api_printers_schema = extend_schema(
    operation_id="api_printers_list",
    methods=["GET"],
    tags=["printers"],
    summary="Список принтеров",
    description="Возвращает список принтеров с фильтрацией и пагинацией",
    parameters=[
        OpenApiParameter(name="q_ip", description="Фильтр по IP", type=str, required=False),
        OpenApiParameter(name="q_serial", description="Фильтр по serial", type=str, required=False),
        OpenApiParameter(name="q_org", description="Фильтр по организации", type=str, required=False),
        OpenApiParameter(name="q_manufacturer", description="Фильтр по производителю (ID)", type=int, required=False),
        OpenApiParameter(name="q_device_model", description="Фильтр по модели (ID)", type=int, required=False),
        OpenApiParameter(name="q_model_text", description="Фильтр по названию модели", type=str, required=False),
        OpenApiParameter(
            name="q_rule",
            description="Правило сопоставления",
            type=str,
            required=False,
            enum=["SN_MAC", "MAC_ONLY", "SN_ONLY", "NONE"],
        ),
        OpenApiParameter(
            name="q_active", description="Активность", type=str, required=False, enum=["true", "false", "all"]
        ),
        OpenApiParameter(name="page", description="Страница", type=int, required=False),
        OpenApiParameter(
            name="per_page",
            description="На странице",
            type=int,
            required=False,
            enum=[10, 25, 50, 100, 250, 500, 1000, 2000, 5000],
        ),
    ],
    responses={
        200: OpenApiResponse(response=PRINTER_LIST_SCHEMA, description="Список принтеров"),
        401: OpenApiResponse(description="Не авторизован"),
        403: OpenApiResponse(description="Нет прав"),
    },
)

api_printer_detail_schema = extend_schema(
    operation_id="api_printer_detail",
    tags=["printers"],
    summary="Детали принтера",
    description="Детальная информация о принтере по ID",
    parameters=[
        OpenApiParameter(name="pk", description="ID принтера", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(response=PRINTER_ITEM_SCHEMA, description="Детали принтера"),
        404: OpenApiResponse(response=ERROR_SCHEMA, description="Не найден"),
    },
)

api_probe_serial_schema = extend_schema(
    operation_id="api_probe_serial",
    tags=["inventory"],
    summary="SNMP Discovery по IP",
    description="Запускает SNMP discovery для получения серийного номера по IP-адресу",
    request=ProbeSerialRequestSerializer,
    responses={
        200: OpenApiResponse(description="Результат опроса с серийным номером"),
        400: OpenApiResponse(response=ERROR_SCHEMA, description="Ошибка"),
    },
)

api_system_status_schema = extend_schema(
    operation_id="api_system_status",
    tags=["system"],
    summary="Статус системы",
    description="Проверка состояния компонентов (Celery, Redis, БД)",
    responses={
        200: OpenApiResponse(response=SYSTEM_STATUS_SCHEMA, description="Статус"),
    },
)

api_status_statistics_schema = extend_schema(
    operation_id="api_status_statistics",
    tags=["system"],
    summary="Статистика опросов",
    description="Статистика по статусам опросов принтеров",
    responses={
        200: OpenApiResponse(response=STATUS_STATS_SCHEMA, description="Статистика"),
    },
)

api_models_by_manufacturer_schema = extend_schema(
    operation_id="api_models_by_manufacturer",
    tags=["printers"],
    summary="Модели по производителю",
    description="Список моделей принтеров указанного производителя",
    parameters=[
        OpenApiParameter(name="manufacturer_id", description="ID производителя", type=int, required=True),
    ],
    responses={
        200: OpenApiResponse(description="Список моделей"),
    },
)

api_all_printer_models_schema = extend_schema(
    operation_id="api_all_printer_models",
    tags=["printers"],
    summary="Все модели принтеров",
    description="Полный список моделей с производительностью",
    responses={
        200: OpenApiResponse(description="Список моделей"),
    },
)

api_printer_replacement_history_schema = extend_schema(
    operation_id="api_printer_replacement_history",
    tags=["printers"],
    summary="История замен",
    description="История замен принтера по serial number",
    parameters=[
        OpenApiParameter(name="pk", description="ID принтера", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(description="История замен"),
    },
)
