#!/usr/bin/env python
"""
Скрипт для диагностики GLPI Plugin Fields API.
Проверяет доступные поля и структуру данных.
"""
import os
import sys
import django
import json

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')
django.setup()

from integrations.glpi.client import GLPIClient


def test_plugin_fields():
    """Проверяет структуру данных плагина Fields"""
    print("=" * 80)
    print("GLPI Plugin Fields API Diagnostics")
    print("=" * 80)

    with GLPIClient() as client:
        print(f"\n✓ Успешно подключились к GLPI API: {client.url}")
        print(f"  Session Token: {client.session_token[:20]}...")

        # 1. Проверка эндпоинта PluginFieldsPrinterx
        print("\n" + "=" * 80)
        print("1. GET /PluginFieldsPrinterx/")
        print("=" * 80)

        import requests
        response = requests.get(
            f"{client.url}/PluginFieldsPrinterx/",
            headers=client._get_headers(with_session=True),
            timeout=15,
            verify=client.verify_ssl
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Количество записей: {len(data)}")

            if data:
                print("\n--- Первая запись (структура) ---")
                first_record = data[0]
                print(json.dumps(first_record, indent=2, ensure_ascii=False))

                print("\n--- Доступные поля ---")
                for key in sorted(first_record.keys()):
                    value = first_record[key]
                    value_str = str(value)[:50] if value else "null"
                    print(f"  {key:30} = {value_str}")

                # Проверяем наличие нужного поля
                print("\n--- Проверка поля serialnumberonlabelfield ---")
                if 'serialnumberonlabelfield' in first_record:
                    print(f"  ✓ Поле существует!")
                    print(f"  Значение: {first_record['serialnumberonlabelfield']}")
                else:
                    print(f"  ✗ Поле НЕ найдено!")
                    print(f"  Похожие поля:")
                    for key in first_record.keys():
                        if 'serial' in key.lower():
                            print(f"    - {key} = {first_record[key]}")
        else:
            print(f"Ошибка: {response.text}")

        # 2. Проверка через listSearchOptions
        print("\n" + "=" * 80)
        print("2. GET /listSearchOptions/Printer")
        print("=" * 80)

        response2 = requests.get(
            f"{client.url}/listSearchOptions/Printer",
            headers=client._get_headers(with_session=True),
            timeout=15,
            verify=client.verify_ssl
        )

        if response2.status_code == 200:
            options = response2.json()
            print(f"Найдено опций: {len(options)}")

            print("\n--- Все доступные поля для поиска ---")
            for field_id, field_info in sorted(options.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                if isinstance(field_info, dict):
                    name = field_info.get('name', '')
                    field = field_info.get('field', '')
                    table = field_info.get('table', '')
                    print(f"  [{field_id:3}] {name:40} (table: {table}, field: {field})")
        else:
            print(f"Status: {response2.status_code}")
            print(f"Response: {response2.text[:200]}")

        # 3. Проверка schema плагина
        print("\n" + "=" * 80)
        print("3. GET /PluginFieldsContainer/")
        print("=" * 80)

        response3 = requests.get(
            f"{client.url}/PluginFieldsContainer/",
            headers=client._get_headers(with_session=True),
            timeout=15,
            verify=client.verify_ssl
        )

        print(f"Status Code: {response3.status_code}")
        if response3.status_code == 200:
            containers = response3.json()
            print(f"Количество контейнеров: {len(containers)}")

            for container in containers:
                if isinstance(container, dict):
                    print(f"\nКонтейнер: {container.get('name', 'N/A')}")
                    print(f"  ID: {container.get('id')}")
                    print(f"  Type: {container.get('type')}")
                    print(f"  Itemtypes: {container.get('itemtypes')}")
        else:
            print(f"Response: {response3.text[:200]}")

        # 4. Тестовый поиск по конкретному серийнику
        print("\n" + "=" * 80)
        print("4. Тестовый поиск (введите серийный номер для теста)")
        print("=" * 80)

        test_serial = input("Введите серийный номер для проверки (или Enter для пропуска): ").strip()

        if test_serial:
            print(f"\nИщем: {test_serial}")
            status, items, error = client.search_printer_by_serial(test_serial)

            print(f"\nРезультат: {status}")
            if items:
                print(f"Найдено устройств: {len(items)}")
                for i, item in enumerate(items):
                    print(f"\n--- Устройство {i+1} ---")
                    print(json.dumps(item, indent=2, ensure_ascii=False))
            if error:
                print(f"Ошибка: {error}")


if __name__ == '__main__':
    try:
        test_plugin_fields()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
