# contracts/api_docs_decorators.py
"""
OpenAPI декораторы для contracts API views.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.fields import BooleanField, CharField, IntegerField

CONTRACT_DEVICE_SCHEMA = inline_serializer(
    name="ContractDevice",
    fields={
        "id": IntegerField(),
        "serial_number": CharField(allow_null=True),
        "ip_address": CharField(allow_null=True),
        "inventory_number": CharField(allow_null=True),
        "device_model": CharField(allow_null=True),
        "manufacturer": CharField(allow_null=True),
        "organization": CharField(allow_null=True),
        "city": CharField(allow_null=True),
        "contract_status": CharField(allow_null=True),
        "is_active": BooleanField(),
    },
)

CONTRACT_DEVICES_SCHEMA = inline_serializer(
    name="ContractDevicesList",
    fields={
        "count": IntegerField(),
        "next": CharField(allow_null=True),
        "previous": CharField(allow_null=True),
        "results": serializers.ListField(child=CONTRACT_DEVICE_SCHEMA),
    },
)

DEVICE_MODEL_SCHEMA = inline_serializer(
    name="DeviceModel",
    fields={
        "id": IntegerField(),
        "name": CharField(),
        "manufacturer": CharField(),
        "a4_bw_speed": IntegerField(allow_null=True),
        "a4_color_speed": IntegerField(allow_null=True),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

api_contract_devices_schema = extend_schema(
    operation_id="api_contract_devices",
    tags=["contracts"],
    summary="Список устройств в договоре",
    description="Возвращает список устройств с фильтрацией и пагинацией",
    parameters=[
        OpenApiParameter(name="q_serial", description="Серийный номер", type=str, required=False),
        OpenApiParameter(name="q_ip", description="IP-адрес", type=str, required=False),
        OpenApiParameter(name="q_model", description="Модель", type=str, required=False),
        OpenApiParameter(name="q_org", description="Организация", type=str, required=False),
        OpenApiParameter(name="q_city", description="Город", type=str, required=False),
        OpenApiParameter(name="page", description="Страница", type=int, required=False),
        OpenApiParameter(name="per_page", description="На странице", type=int, required=False),
    ],
    responses={
        200: OpenApiResponse(response=CONTRACT_DEVICES_SCHEMA, description="Список устройств"),
        403: OpenApiResponse(description="Нет прав"),
    },
)

api_contract_filters_schema = extend_schema(
    operation_id="api_contract_filters",
    tags=["contracts"],
    summary="Фильтры для устройств",
    description="Возвращает доступные значения для фильтрации",
    responses={
        200: OpenApiResponse(description="Фильтры (города, модели, статусы)"),
    },
)

api_device_models_by_manufacturer_schema = extend_schema(
    operation_id="api_device_models_by_manufacturer",
    tags=["contracts"],
    summary="Модели по производителю",
    description="Список моделей указанного производителя",
    parameters=[
        OpenApiParameter(name="manufacturer_id", description="ID производителя", type=int, required=True),
    ],
    responses={
        200: OpenApiResponse(response=serializers.ListField(child=DEVICE_MODEL_SCHEMA), description="Список моделей"),
    },
)
