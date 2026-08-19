# integrations/serializers.py
"""
DRF Serializers для API request body validation.
Используется в Swagger UI для форм ввода POST запросов.
"""

from rest_framework import serializers


class CheckDeviceGLPIRequestSerializer(serializers.Serializer):
    """Request serializer для проверки устройства в GLPI."""

    force = serializers.BooleanField(
        help_text="Принудительная проверка (игнорировать кэш)", required=False, default=False
    )


class CheckMultipleDevicesGLPIRequestSerializer(serializers.Serializer):
    """Request serializer для массовой проверки устройств в GLPI."""

    device_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Список ID устройств (максимум 100)",
        required=True,
        min_length=1,
        max_length=100,
    )


class CreateServiceRequestSerializer(serializers.Serializer):
    """Request serializer для подачи заявки подрядчику."""

    device_id = serializers.IntegerField(help_text="ID устройства", required=True)
    cartridge = serializers.CharField(
        help_text="Картридж (опционально)", required=False, allow_null=True, allow_blank=True
    )
    service_type = serializers.CharField(
        help_text="Тип обслуживания", required=False, allow_null=True, allow_blank=True, default="Обслуживание"
    )
    comment = serializers.CharField(
        help_text="Комментарий (опционально)", required=False, allow_null=True, allow_blank=True
    )
    phone = serializers.CharField(help_text="Телефон (опционально)", required=False, allow_null=True, allow_blank=True)


class PostCommentRequestSerializer(serializers.Serializer):
    """Request serializer для отправки комментария в Okdesk."""

    content = serializers.CharField(help_text="Текст комментария", required=True)
    is_public = serializers.BooleanField(help_text="Публичный комментарий", required=False, default=True)


class SyncNowRequestSerializer(serializers.Serializer):
    """Request serializer для запуска синхронизации Okdesk."""

    issues = serializers.BooleanField(help_text="Синхронизировать заявки", required=False, default=True)
    comments = serializers.BooleanField(help_text="Синхронизировать комментарии", required=False, default=True)
