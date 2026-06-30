"""OpenAPI (drf-spectacular) декораторы для supplies_report API endpoints."""

from datetime import time

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers

# Импорт request serializers
from .serializers import (
    GroupUpdateRequestSerializer,
    ItemUpdateRequestSerializer,
)

# ─── Schema Serializers ─────────────────────────────────────────────────────────────


class PrinterSummarySerializer(serializers.Serializer):
    """Минимальная информация о принтере."""

    id = serializers.IntegerField()
    ip_address = serializers.IPAddressField()
    serial_number = serializers.CharField(allow_blank=True, allow_null=True)
    model = serializers.CharField()
    is_active = serializers.BooleanField()


class ReportGroupItemSerializer(serializers.Serializer):
    """Элемент группы отчётов (принтер в группе)."""

    id = serializers.IntegerField()
    sort_order = serializers.IntegerField()
    location = serializers.CharField(allow_blank=True)
    additional_info = serializers.CharField(allow_blank=True)
    printer = PrinterSummarySerializer()


class ConsumableSummarySerializer(serializers.Serializer):
    """Информация о расходнике."""

    color_label = serializers.CharField()
    toner_text = serializers.CharField()
    drum_text = serializers.CharField()


class ReportRowSerializer(serializers.Serializer):
    """Стока отчёта для письма."""

    item_id = serializers.IntegerField()
    printer_id = serializers.IntegerField()
    ip = serializers.IPAddressField()
    model = serializers.CharField()
    location = serializers.CharField(allow_blank=True)
    additional = serializers.CharField(allow_blank=True)
    consumables = ConsumableSummarySerializer(many=True)
    last_polled_at = serializers.DateTimeField(allow_null=True)
    is_stale = serializers.BooleanField()
    no_data = serializers.BooleanField()


class ReportGroupSerializer(serializers.Serializer):
    """Группа отчётов по расходникам."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    location_label = serializers.CharField(allow_blank=True)
    subject_template = serializers.CharField(allow_blank=True)
    body_intro = serializers.CharField(allow_blank=True)
    body_signature = serializers.CharField(allow_blank=True)
    from_email = serializers.EmailField(allow_blank=True, allow_null=True)
    to_emails = serializers.CharField(allow_blank=True)
    cc_emails = serializers.CharField(allow_blank=True)
    stale_threshold_hours = serializers.IntegerField()
    is_active = serializers.BooleanField()
    auto_send_enabled = serializers.BooleanField()
    auto_send_time = serializers.TimeField(allow_null=True)
    auto_send_weekdays = serializers.CharField(allow_blank=True)
    last_sent_at = serializers.DateTimeField(allow_null=True)
    last_send_error = serializers.CharField(allow_blank=True)
    items_count = serializers.IntegerField()
    updated_at = serializers.DateTimeField(allow_null=True)


class ReportGroupListSerializer(serializers.Serializer):
    """Список групп отчётов."""

    groups = ReportGroupSerializer(many=True)


class ReportGroupDetailSerializer(serializers.Serializer):
    """Детали группы с элементами и строками отчёта."""

    group = ReportGroupSerializer()
    items = ReportGroupItemSerializer(many=True)
    rows = ReportRowSerializer(many=True)


# ─── Request/Response Serializers для PATCH ────────────────────────────────────────


class GroupUpdateResponseSerializer(serializers.Serializer):
    """Ответ при успешном обновлении группы."""

    group = ReportGroupSerializer()
    changed = serializers.ListField(child=serializers.CharField())


class ItemUpdateResponseSerializer(serializers.Serializer):
    """Ответ при успешном обновлении элемента."""

    item = ReportGroupItemSerializer()
    changed = serializers.ListField(child=serializers.CharField())


# ─── Error Responses ───────────────────────────────────────────────────────────────


class ErrorSerializer(serializers.Serializer):
    """Базовый сериализатор ошибок (текстовый)."""

    detail = serializers.CharField()


# ─── Декораторы ────────────────────────────────────────────────────────────────────


api_groups_list_schema = extend_schema(
    operation_id="api_supplies_report_groups_list",
    summary="Список групп отчётов по расходникам",
    description=(
        "Возвращает все группы отчётов с количеством элементов. "
        "Требует право доступа `supplies_report.access_supplies_report`."
    ),
    tags=["Supplies Report API"],
    responses={
        200: OpenApiResponse(
            response=ReportGroupListSerializer,
            description="Список групп отчётов.",
        ),
        401: OpenApiResponse(
            response=ErrorSerializer,
            description="Пользователь не аутентифицирован.",
        ),
        403: OpenApiResponse(
            response=ErrorSerializer,
            description="Нет права доступа `supplies_report.access_supplies_report`.",
        ),
    },
)


api_group_detail_schema = extend_schema(
    operation_id="api_supplies_report_group_detail",
    summary="Детали группы отчётов",
    description=(
        "Возвращает полную информацию о группе включая элементы (items) "
        "и строки отчёта (rows) для генерации письма. "
        "Требует право доступа `supplies_report.access_supplies_report`."
    ),
    tags=["Supplies Report API"],
    responses={
        200: OpenApiResponse(
            response=ReportGroupDetailSerializer,
            description="Детали группы с элементами и строками отчёта.",
        ),
        401: OpenApiResponse(
            response=ErrorSerializer,
            description="Пользователь не аутентифицирован.",
        ),
        403: OpenApiResponse(
            response=ErrorSerializer,
            description="Нет права доступа `supplies_report.access_supplies_report`.",
        ),
        404: OpenApiResponse(
            response=ErrorSerializer,
            description="Группа не найдена.",
        ),
    },
)


api_group_update_schema = extend_schema(
    operation_id="api_supplies_report_group_update",
    summary="Обновление группы отчётов",
    description=(
        "Частичное обновление полей группы отчётов. "
        "В теле запроса передавать только те поля, которые нужно изменить. "
        "Требует право `supplies_report.manage_supplies_report`."
    ),
    tags=["Supplies Report API"],
    request=GroupUpdateRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=GroupUpdateResponseSerializer,
            description="Группа успешно обновлена. Возвращает актуальные данные группы " "и список изменённых полей.",
        ),
        400: OpenApiResponse(
            response=ErrorSerializer,
            description="Невалидный JSON или неверное значение поля.",
        ),
        401: OpenApiResponse(
            response=ErrorSerializer,
            description="Пользователь не аутентифицирован.",
        ),
        403: OpenApiResponse(
            response=ErrorSerializer,
            description="Нет права `supplies_report.manage_supplies_report`.",
        ),
        404: OpenApiResponse(
            response=ErrorSerializer,
            description="Группа не найдена.",
        ),
    },
)


api_item_update_schema = extend_schema(
    operation_id="api_supplies_report_item_update",
    summary="Обновление элемента группы",
    description=(
        "Частичное обновление полей элемента группы (location, additional_info, "
        "sort_order, printer_id). Требует право `supplies_report.manage_supplies_report`."
    ),
    tags=["Supplies Report API"],
    request=ItemUpdateRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=ItemUpdateResponseSerializer,
            description="Элемент успешно обновлён. Возвращает актуальные данные " "элемента и список изменённых полей.",
        ),
        400: OpenApiResponse(
            response=ErrorSerializer,
            description="Невалидный JSON, неверное значение поля или принтер не найден.",
        ),
        401: OpenApiResponse(
            response=ErrorSerializer,
            description="Пользователь не аутентифицирован.",
        ),
        403: OpenApiResponse(
            response=ErrorSerializer,
            description="Нет права `supplies_report.manage_supplies_report`.",
        ),
        404: OpenApiResponse(
            response=ErrorSerializer,
            description="Элемент не найден.",
        ),
    },
)
