# supplies_report/serializers.py
"""
DRF Serializers для API request body validation.
Используется в Swagger UI для форм ввода POST/PATCH запросов.
"""

from rest_framework import serializers
from datetime import time


class GroupUpdateRequestSerializer(serializers.Serializer):
    """Request serializer для обновления группы отчётов (все optional)."""

    name = serializers.CharField(required=False, allow_blank=True)
    location_label = serializers.CharField(required=False, allow_blank=True)
    subject_template = serializers.CharField(required=False, allow_blank=True)
    body_intro = serializers.CharField(required=False, allow_blank=True)
    body_signature = serializers.CharField(required=False, allow_blank=True)
    from_email = serializers.EmailField(required=False, allow_null=True)
    to_emails = serializers.CharField(required=False, allow_blank=True)
    cc_emails = serializers.CharField(required=False, allow_blank=True)
    stale_threshold_hours = serializers.IntegerField(required=False, min_value=1)
    is_active = serializers.BooleanField(required=False)
    auto_send_enabled = serializers.BooleanField(required=False)
    auto_send_time = serializers.TimeField(required=False, allow_null=True)
    auto_send_weekdays = serializers.CharField(required=False, allow_blank=True)


class ItemUpdateRequestSerializer(serializers.Serializer):
    """Request serializer для обновления элемента группы (все optional)."""

    location = serializers.CharField(required=False, allow_blank=True)
    additional_info = serializers.CharField(required=False, allow_blank=True)
    sort_order = serializers.IntegerField(required=False)
    printer_id = serializers.IntegerField(required=False)
