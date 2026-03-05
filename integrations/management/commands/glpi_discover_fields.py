"""
Команда для определения правильных имен ресурсов и полей Plugin Fields в GLPI.

Использование:
    python manage.py glpi_discover_fields
    python manage.py glpi_discover_fields --printer-id 2983

Скрипт выполняет:
1. Подключение к GLPI API
2. Поиск всех ресурсов PluginFields для Printer
3. Вывод структуры найденных ресурсов с полями
4. Проверка существующих записей для конкретного принтера (если указан --printer-id)
"""

import logging

import requests

from django.core.management.base import BaseCommand

from integrations.glpi.client import GLPIClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Определяет правильные имена ресурсов и полей Plugin Fields в GLPI"

    def add_arguments(self, parser):
        parser.add_argument("--printer-id", type=int, help="ID принтера в GLPI для проверки существующих записей")

    def handle(self, *args, **options):
        printer_id = options.get("printer_id")

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🔍 ИССЛЕДОВАНИЕ PLUGIN FIELDS В GLPI"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

        try:
            # Подключение к GLPI
            client = GLPIClient()
            client.init_session()
            self.stdout.write(self.style.SUCCESS("✓ Подключение к GLPI установлено"))
            self.stdout.write("")

            # Шаг 1: Поиск всех доступных ресурсов
            self.stdout.write(self.style.WARNING("📋 Шаг 1: Поиск доступных ресурсов Plugin Fields"))
            self.stdout.write("-" * 70)

            plugin_resources = self._find_plugin_resources(client)

            if not plugin_resources:
                self.stdout.write(self.style.ERROR("❌ Не найдено ресурсов Plugin Fields"))
                return

            # Шаг 2: Исследование каждого найденного ресурса
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("📊 Шаг 2: Исследование структуры ресурсов"))
            self.stdout.write("-" * 70)

            for resource_name in plugin_resources:
                self._investigate_resource(client, resource_name, printer_id)

            # Шаг 3: Рекомендации
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 70))
            self.stdout.write(self.style.SUCCESS("💡 РЕКОМЕНДАЦИИ ПО НАСТРОЙКЕ"))
            self.stdout.write(self.style.SUCCESS("=" * 70))
            self.stdout.write("")
            self.stdout.write("Обновите настройки в .env файле:")
            self.stdout.write("")
            self.stdout.write("GLPI_CONTRACT_RESOURCE_NAME=<имя_ресурса_из_списка_выше>")
            self.stdout.write("GLPI_CONTRACT_FIELD_NAME=<имя_поля_из_структуры>")
            self.stdout.write("")
            self.stdout.write("После обновления .env перезапустите Celery workers:")
            self.stdout.write("  supervisorctl restart all")
            self.stdout.write("")

            client.kill_session()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка: {e}"))
            logger.exception("Ошибка при исследовании Plugin Fields")

    def _find_plugin_resources(self, client: GLPIClient):
        """Ищет все ресурсы Plugin Fields для Printer"""

        # Список потенциальных имен ресурсов Plugin Fields
        potential_names = [
            "PluginFieldsPrinterprinter",
            "PluginFieldsPrinterprinterservices",
            "PluginFieldsPrinterx",
            "PluginFieldsPrinters",
            "PluginFieldsContainer",
        ]

        found_resources = []

        for resource_name in potential_names:
            try:
                response = requests.get(
                    f"{client.url}/{resource_name}",
                    headers=client._get_headers(with_session=True),
                    params={"range": "0-0"},  # Запрашиваем только 1 запись для проверки
                    timeout=10,
                    verify=client.verify_ssl,
                )

                if response.status_code == 200:
                    found_resources.append(resource_name)
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Найден: {resource_name}"))
                elif response.status_code == 206:  # Partial content - тоже успех
                    found_resources.append(resource_name)
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Найден: {resource_name}"))
                else:
                    self.stdout.write(f"  - {resource_name}: не найден (HTTP {response.status_code})")

            except Exception as e:
                self.stdout.write(f"  - {resource_name}: ошибка ({str(e)[:50]})")

        return found_resources

    def _investigate_resource(self, client: GLPIClient, resource_name: str, printer_id: int = None):
        """Исследует структуру конкретного ресурса"""

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"📦 Ресурс: {resource_name}"))
        self.stdout.write("-" * 70)

        try:
            # Получаем записи из ресурса
            response = requests.get(
                f"{client.url}/{resource_name}",
                headers=client._get_headers(with_session=True),
                params={"range": "0-4"},  # Первые 5 записей
                timeout=10,
                verify=client.verify_ssl,
            )

            if response.status_code in [200, 206]:
                data = response.json()

                if isinstance(data, list) and len(data) > 0:
                    # Показываем структуру первой записи
                    first_record = data[0]

                    self.stdout.write(f"Всего записей: {len(data)} (показано)")
                    self.stdout.write("Пример структуры записи:")
                    self.stdout.write("")

                    # Форматируем и выводим поля
                    for key, value in first_record.items():
                        if isinstance(value, (str, int, bool, type(None))):
                            value_str = str(value)[:50]
                            self.stdout.write(f"  • {key:30s} = {value_str}")

                    # Ищем поля похожие на "договор" или "contract"
                    self.stdout.write("")
                    self.stdout.write("🎯 Потенциальные поля для договора:")
                    contract_fields = [
                        key
                        for key in first_record.keys()
                        if "contract" in key.lower()
                        or "dogovor" in key.lower()
                        or "stated" in key.lower()
                        or "заявлен" in key.lower()
                    ]

                    if contract_fields:
                        for field in contract_fields:
                            self.stdout.write(self.style.SUCCESS(f"  ✓ {field} = {first_record[field]}"))
                    else:
                        self.stdout.write("  (не найдено полей с 'contract' или 'stated' в имени)")

                    # Если указан printer_id, ищем запись для этого принтера
                    if printer_id:
                        self.stdout.write("")
                        self.stdout.write(f"🔍 Поиск записи для принтера ID={printer_id}:")

                        # Получаем больше записей для поиска
                        full_response = requests.get(
                            f"{client.url}/{resource_name}",
                            headers=client._get_headers(with_session=True),
                            params={"range": "0-999"},
                            timeout=15,
                            verify=client.verify_ssl,
                        )

                        if full_response.status_code in [200, 206]:
                            full_data = full_response.json()

                            found = False
                            for record in full_data:
                                if record.get("items_id") == printer_id:
                                    found = True
                                    self.stdout.write(self.style.SUCCESS(f"  ✓ Найдена запись ID={record['id']}:"))

                                    for key, value in record.items():
                                        if isinstance(value, (str, int, bool, type(None))):
                                            value_str = str(value)[:50]
                                            self.stdout.write(f"    • {key:28s} = {value_str}")
                                    break

                            if not found:
                                self.stdout.write(
                                    self.style.WARNING(f"  ⚠ Запись для принтера {printer_id} не найдена")
                                )
                                self.stdout.write("  (возможно, нужно создать новую запись)")

                else:
                    self.stdout.write(self.style.WARNING("  Ресурс пустой (нет записей)"))

            else:
                error_text = response.text[:200] if response.text else f"HTTP {response.status_code}"
                self.stdout.write(self.style.ERROR(f"  ❌ Ошибка получения данных: {error_text}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Ошибка: {str(e)[:100]}"))
            logger.exception(f"Ошибка при исследовании {resource_name}")
