"""
Сводные тесты для всех изменений проекта.

Включает базовые проверки для:
- HYBRID polling (уже в test_hybrid_polling.py)
- Serializers (уже в test_serializers.py)
- API v2 endpoints (упрощённая версия)
"""

from django.test import TestCase

from inventory.models import PollingMethod
from inventory.serializers import ProbeSerialRequestSerializer


class HybridPollingSmokeTests(TestCase):
    """Smoke tests для HYBRID polling."""

    def test_hybrid_choice_exists(self):
        """HYBRID выбор существует в PollingMethod."""
        self.assertIn("HYBRID", [choice[0] for choice in PollingMethod.choices])

    def test_hybrid_label_is_meaningful(self):
        """Label для HYBRID содержит 'Совмещённый' и 'SNMP + Web'."""
        for value, label in PollingMethod.choices:
            if value == "HYBRID":
                self.assertIn("Совмещённый", label)
                self.assertIn("SNMP + Web", label)


class SerializersBasicTests(TestCase):
    """Базовые тесты для Serializers."""

    def test_probe_serial_serializer_accepts_ip(self):
        """ProbeSerialRequestSerializer принимает IP."""
        serializer = ProbeSerialRequestSerializer(data={"ip": "10.0.0.1", "community": "public"})
        self.assertTrue(serializer.is_valid())


class ApiV2SmokeTests(TestCase):
    """Smoke tests для API v2 endpoints."""

    def test_api_v2_endpoints_configured(self):
        """API v2 endpoints настроены в urlconf."""
        # Проверяем что urls.py можно импортировать без ошибок
        try:
            from inventory import urls

            self.assertTrue(hasattr(urls, "urlpatterns"))
        except ImportError:
            self.fail("Cannot import inventory.urls")

    def test_api_v2_views_module_exists(self):
        """Модуль api_views_drf существует."""
        try:
            from inventory import api_views_drf

            self.assertTrue(hasattr(api_views_drf, "api_printers_drf"))
        except ImportError:
            self.fail("Cannot import api_views_drf")


class SettingsConfigurationTests(TestCase):
    """Тесты конфигурации настроек."""

    def test_drf_installed(self):
        """DRF установлен в INSTALLED_APPS."""
        from django.conf import settings

        self.assertIn("rest_framework", settings.INSTALLED_APPS)

    def test_drf_spectacular_installed(self):
        """drf-spectacular установлен в INSTALLED_APPS."""
        from django.conf import settings

        self.assertIn("drf_spectacular", settings.INSTALLED_APPS)

    def test_rest_framework_configured(self):
        """REST_FRAMEWORK настроен (условно)."""
        from django.conf import settings

        try:
            import drf_spectacular  # noqa: F401

            # Если drf-spectacular установлен, REST_FRAMEWORK должен быть настроен
            self.assertTrue(
                hasattr(settings, "REST_FRAMEWORK"),
                "REST_FRAMEWORK should be configured when drf-spectacular is installed",
            )
        except ImportError:
            # Если drf-spectacular не установлен, проверяем что пакет установлен
            import rest_framework  # noqa: F401

            self.assertTrue("rest_framework" in settings.INSTALLED_APPS, "djangorestframework should be installed")


class RequirementsTests(TestCase):
    """Проверка зависимостей."""

    def test_djangorestframework_in_requirements(self):
        """djangorestframework указан в requirements.txt."""
        with open("requirements.txt", "r") as f:
            content = f.read()
        self.assertIn("djangorestframework", content)

    def test_drf_spectacular_in_requirements(self):
        """drf-spectacular указан в requirements.txt."""
        with open("requirements.txt", "r") as f:
            content = f.read()
        self.assertIn("drf-spectacular", content)
