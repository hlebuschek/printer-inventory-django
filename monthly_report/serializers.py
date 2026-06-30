# monthly_report/serializers.py
"""
DRF Serializers для API request body validation.
Используется в Swagger UI для форм ввода POST запросов.
"""
from rest_framework import serializers


class UpdateCountersRequestSerializer(serializers.Serializer):
    """Request serializer для обновления счётчиков."""
    a4_bw_end = serializers.IntegerField(
        help_text="A4 ч/б конец",
        required=False,
        allow_null=True
    )
    a4_color_end = serializers.IntegerField(
        help_text="A4 цвет конец",
        required=False,
        allow_null=True
    )
    a3_bw_end = serializers.IntegerField(
        help_text="A3 ч/б конец",
        required=False,
        allow_null=True
    )
    a3_color_end = serializers.IntegerField(
        help_text="A3 цвет конец",
        required=False,
        allow_null=True
    )
    notes = serializers.CharField(
        help_text="Заметки",
        required=False,
        allow_null=True,
        allow_blank=True
    )


class ResetManualRequestSerializer(serializers.Serializer):
    """Request serializer для сброса флага ручного редактирования."""
    field = serializers.CharField(
        help_text="Имя поля для сброса (например, a4_bw_end_manual)",
        required=True
    )


class SerialOverrideRequestSerializer(serializers.Serializer):
    """Request serializer для управления оверрайдом серийного номера."""
    serial_number = serializers.CharField(
        help_text="Серийный номер устройства",
        required=True
    )
    allow = serializers.BooleanField(
        help_text="Разрешить/запретить ручное редактирование",
        required=True
    )
    mode = serializers.CharField(
        help_text="Режим оверрайда: this_month/permanent/until_date",
        required=False,
        allow_null=True,
        allow_blank=True
    )
    year = serializers.IntegerField(
        help_text="Год (для режима this_month)",
        required=False,
        allow_null=True
    )
    month = serializers.IntegerField(
        help_text="Месяц (для режима this_month)",
        required=False,
        allow_null=True,
        min_value=1,
        max_value=12
    )
    expires_at = serializers.CharField(
        help_text="Дата истечения (ISO формат) (для режима until_date)",
        required=False,
        allow_null=True,
        allow_blank=True
    )


class ToggleMonthPublishedRequestSerializer(serializers.Serializer):
    """Request serializer для переключения статуса публикации месяца."""
    year = serializers.IntegerField(
        help_text="Год",
        required=True,
        min_value=2020,
        max_value=2100
    )
    month = serializers.IntegerField(
        help_text="Месяц (1-12)",
        required=True,
        min_value=1,
        max_value=12
    )
    is_published = serializers.BooleanField(
        help_text="Статус публикации",
        required=True
    )


class ToggleAutoSyncRequestSerializer(serializers.Serializer):
    """Request serializer для переключения автосинхронизации."""
    year = serializers.IntegerField(
        help_text="Год",
        required=True,
        min_value=2020,
        max_value=2100
    )
    month = serializers.IntegerField(
        help_text="Месяц (1-12)",
        required=True,
        min_value=1,
        max_value=12
    )
    auto_sync_enabled = serializers.BooleanField(
        help_text="Включить/выключить автосинхронизацию",
        required=True
    )


class DeleteMonthRequestSerializer(serializers.Serializer):
    """Request serializer для удаления месяца."""
    year = serializers.IntegerField(
        help_text="Год",
        required=True,
        min_value=2020,
        max_value=2100
    )
    month = serializers.IntegerField(
        help_text="Месяц (1-12)",
        required=True,
        min_value=1,
        max_value=12
    )


class GLPIExportStartRequestSerializer(serializers.Serializer):
    """Request serializer для запуска выгрузки в GLPI."""
    month = serializers.CharField(
        help_text="Месяц в формате YYYY-MM (опционально, по умолчанию текущий)",
        required=False,
        allow_null=True,
        allow_blank=True
    )
