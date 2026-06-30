# inventory/serializers.py
"""
DRF Serializers для API request body validation.
Используется в Swagger UI для форм ввода POST запросов.
"""
from rest_framework import serializers


class ProbeSerialRequestSerializer(serializers.Serializer):
    ip = serializers.CharField(help_text="IP-адрес принтера", required=True)
    community = serializers.CharField(help_text="SNMP community (по умолчанию 'public')", required=False, default="public")


class SyncFromInventoryRequestSerializer(serializers.Serializer):
    year = serializers.IntegerField(help_text="Год (YYYY)", required=True, min_value=2020, max_value=2100)
    month = serializers.IntegerField(help_text="Месяц (1-12)", required=True, min_value=1, max_value=12)
