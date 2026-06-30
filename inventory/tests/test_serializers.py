"""
Тесты для DRF Serializers.

Проверяет валидацию данных в Serializers:
- ProbeSerialRequestSerializer
- SyncFromInventoryRequestSerializer
"""
from django.test import SimpleTestCase

from inventory.serializers import (
    ProbeSerialRequestSerializer,
    SyncFromInventoryRequestSerializer,
)
from rest_framework import serializers as drf_serializers


class ProbeSerialRequestSerializerTests(SimpleTestCase):
    """Тесты для ProbeSerialRequestSerializer."""

    def test_valid_data(self):
        """Валидные данные проходят."""
        serializer = ProbeSerialRequestSerializer(data={
            'ip': '10.0.0.1',
            'community': 'public'
        })
        self.assertTrue(serializer.is_valid())

    def test_ip_required(self):
        """IP является обязательным полем."""
        serializer = ProbeSerialRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip', serializer.errors)

    def test_community_optional_with_default(self):
        """Community опционален, имеет default значение."""
        serializer = ProbeSerialRequestSerializer(data={
            'ip': '10.0.0.1'
        })
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['community'], 'public')

    def test_community_explicit_value(self):
        """Явно указанный community сохраняется."""
        serializer = ProbeSerialRequestSerializer(data={
            'ip': '10.0.0.1',
            'community': 'private'
        })
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['community'], 'private')


class SyncFromInventoryRequestSerializerTests(SimpleTestCase):
    """Тесты для SyncFromInventoryRequestSerializer."""

    def test_valid_data(self):
        """Валидные данные проходят."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2024,
            'month': 6
        })
        self.assertTrue(serializer.is_valid())

    def test_year_required(self):
        """Year является обязательным полем."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'month': 6
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('year', serializer.errors)

    def test_month_required(self):
        """Month является обязательным полем."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2024
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('month', serializer.errors)

    def test_year_minimum(self):
        """Year не может быть меньше 2020."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2019,
            'month': 6
        })
        self.assertFalse(serializer.is_valid())

    def test_year_maximum(self):
        """Year не может быть больше 2100."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2101,
            'month': 6
        })
        self.assertFalse(serializer.is_valid())

    def test_month_minimum(self):
        """Month не может быть меньше 1."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2024,
            'month': 0
        })
        self.assertFalse(serializer.is_valid())

    def test_month_maximum(self):
        """Month не может быть больше 12."""
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2024,
            'month': 13
        })
        self.assertFalse(serializer.is_valid())

    def test_boundary_values(self):
        """Граничные значения проходят валидацию."""
        # Минимум
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2020,
            'month': 1
        })
        self.assertTrue(serializer.is_valid())

        # Максимум
        serializer = SyncFromInventoryRequestSerializer(data={
            'year': 2100,
            'month': 12
        })
        self.assertTrue(serializer.is_valid())
