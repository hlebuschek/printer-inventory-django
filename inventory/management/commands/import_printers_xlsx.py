"""
Команда для безопасного импорта принтеров из Excel с проверкой коллизий.

Формат Excel (первая строка - заголовки):
| IP адрес      | Серийный номер | MAC адрес          | SNMP Community | Организация | Метод опроса |
|---------------|----------------|---------------------|----------------|-------------|--------------|
| 192.168.1.100 | ABC123         | AA:BB:CC:DD:EE:FF  | public         | Альфа       | SNMP         |
| 192.168.1.101 | XYZ456         | 11:22:33:44:55:66  | public         | Альфа       | WEB          |

Примечания:
- IP адрес - обязательный
- Серийный номер - опционально (получится при первом опросе)
- MAC адрес - опционально, но ПРОВЕРЯЕТСЯ на коллизии
- SNMP Community - по умолчанию "public"
- Организация - обязательная (название должно существовать в БД)
- Метод опроса - SNMP или WEB (по умолчанию SNMP)

Примеры использования:

# Анализ без изменений (dry-run)
python manage.py import_printers_xlsx printers.xlsx --dry-run

# Импорт с автоматическим созданием организаций
python manage.py import_printers_xlsx printers.xlsx --auto-create-org

# Импорт с пропуском коллизий
python manage.py import_printers_xlsx printers.xlsx --skip-collisions

# Детальный вывод
python manage.py import_printers_xlsx printers.xlsx --dry-run --show-details
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from inventory.models import Printer, Organization, PollingMethod
import openpyxl
import os


class Command(BaseCommand):
    help = (
        "Импорт принтеров из Excel с проверкой коллизий IP/MAC адресов.\n"
        "Формат: IP | Серийник | MAC | SNMP Community | Организация | Метод опроса"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "xlsx_file",
            type=str,
            help="Путь к Excel файлу с принтерами"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать результаты анализа, не сохранять изменения"
        )
        parser.add_argument(
            "--skip-collisions",
            action="store_true",
            help="Пропустить принтеры с коллизиями IP/MAC вместо ошибки"
        )
        parser.add_argument(
            "--auto-create-org",
            action="store_true",
            help="Автоматически создавать организации, если они не существуют"
        )
        parser.add_argument(
            "--show-details",
            action="store_true",
            help="Показать детальную информацию по каждому принтеру"
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default=None,
            help="Название листа Excel (по умолчанию - первый лист)"
        )

    def handle(self, *args, **opts):
        xlsx_file = opts["xlsx_file"]
        dry_run = opts["dry_run"]
        skip_collisions = opts["skip_collisions"]
        auto_create_org = opts["auto_create_org"]
        show_details = opts["show_details"]
        sheet_name = opts["sheet"]

        # Проверка файла
        if not os.path.exists(xlsx_file):
            raise CommandError(f"Файл не найден: {xlsx_file}")

        self.stdout.write(
            self.style.SUCCESS("=== Импорт принтеров из Excel ===")
        )
        self.stdout.write(f"Файл: {xlsx_file}")

        # Загрузка Excel
        try:
            wb = openpyxl.load_workbook(xlsx_file, data_only=True)
            if sheet_name:
                if sheet_name not in wb.sheetnames:
                    raise CommandError(f"Лист '{sheet_name}' не найден в файле")
                ws = wb[sheet_name]
            else:
                ws = wb.active
        except Exception as e:
            raise CommandError(f"Ошибка открытия Excel: {e}")

        self.stdout.write(f"Лист: {ws.title}")

        # Парсинг заголовков
        headers_row = 1
        headers = {}
        for col_idx, cell in enumerate(ws[headers_row], start=1):
            if cell.value:
                header = str(cell.value).strip().lower()
                headers[header] = col_idx

        # Проверка обязательных столбцов
        required_headers = ['ip адрес', 'ip_address', 'ip']
        ip_col = None
        for h in required_headers:
            if h in headers:
                ip_col = headers[h]
                break

        if not ip_col:
            raise CommandError(
                f"Не найден столбец с IP адресом. Ожидается: {', '.join(required_headers)}"
            )

        # Опциональные столбцы
        sn_col = headers.get('серийный номер') or headers.get('serial_number') or headers.get('sn')
        mac_col = headers.get('mac адрес') or headers.get('mac_address') or headers.get('mac')
        snmp_col = headers.get('snmp community') or headers.get('snmp')
        org_col = headers.get('организация') or headers.get('organization') or headers.get('org')
        method_col = headers.get('метод опроса') or headers.get('polling_method') or headers.get('method')

        self.stdout.write(f"\nНайдены столбцы:")
        self.stdout.write(f"  IP адрес: колонка {ip_col}")
        if sn_col:
            self.stdout.write(f"  Серийный номер: колонка {sn_col}")
        if mac_col:
            self.stdout.write(f"  MAC адрес: колонка {mac_col}")
        if snmp_col:
            self.stdout.write(f"  SNMP Community: колонка {snmp_col}")
        if org_col:
            self.stdout.write(f"  Организация: колонка {org_col}")
        if method_col:
            self.stdout.write(f"  Метод опроса: колонка {method_col}")

        # Счетчики
        stats = {
            'total': 0,
            'success': 0,
            'ip_collision': 0,
            'mac_collision': 0,
            'org_not_found': 0,
            'org_created': 0,
            'invalid_ip': 0,
            'skipped': 0,
        }

        problems = {
            'ip_collisions': [],
            'mac_collisions': [],
            'org_not_found': [],
            'invalid_ips': [],
        }

        # Кэш существующих принтеров
        existing_ips = set(
            Printer.objects.values_list('ip_address', flat=True)
        )
        existing_macs = set(
            Printer.objects.exclude(
                Q(mac_address__isnull=True) | Q(mac_address='')
            ).values_list('mac_address', flat=True)
        )

        # Кэш организаций
        org_cache = {
            org.name.strip().lower(): org
            for org in Organization.objects.all()
        }

        to_create = []

        # Парсинг строк
        for row_idx in range(headers_row + 1, ws.max_row + 1):
            row = ws[row_idx]

            # Получение значений
            ip_value = row[ip_col - 1].value
            if not ip_value:
                continue  # Пустая строка

            ip_address = str(ip_value).strip()
            serial_number = str(row[sn_col - 1].value).strip() if sn_col and row[sn_col - 1].value else ""
            mac_address = str(row[mac_col - 1].value).strip().upper() if mac_col and row[mac_col - 1].value else ""
            snmp_community = str(row[snmp_col - 1].value).strip() if snmp_col and row[snmp_col - 1].value else "public"
            org_name = str(row[org_col - 1].value).strip() if org_col and row[org_col - 1].value else ""
            polling_method = str(row[method_col - 1].value).strip().upper() if method_col and row[method_col - 1].value else "SNMP"

            stats['total'] += 1

            # Валидация метода опроса
            if polling_method not in ['SNMP', 'WEB']:
                polling_method = PollingMethod.SNMP

            # Валидация IP
            if not self._validate_ip(ip_address):
                stats['invalid_ip'] += 1
                problems['invalid_ips'].append({
                    'row': row_idx,
                    'ip': ip_address
                })
                if show_details:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  INVALID_IP (строка {row_idx}): {ip_address}"
                        )
                    )
                continue

            # Проверка коллизий IP
            if ip_address in existing_ips:
                stats['ip_collision'] += 1
                problems['ip_collisions'].append({
                    'row': row_idx,
                    'ip': ip_address
                })
                if show_details:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  IP_COLLISION (строка {row_idx}): {ip_address} уже существует"
                        )
                    )
                if not skip_collisions:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Коллизия IP на строке {row_idx}: {ip_address} уже существует!\n"
                            f"Используйте --skip-collisions для пропуска таких принтеров."
                        )
                    )
                    return
                continue

            # Проверка коллизий MAC (если указан)
            if mac_address and mac_address in existing_macs:
                stats['mac_collision'] += 1
                problems['mac_collisions'].append({
                    'row': row_idx,
                    'mac': mac_address,
                    'ip': ip_address
                })
                if show_details:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  MAC_COLLISION (строка {row_idx}): {mac_address} уже существует (IP: {ip_address})"
                        )
                    )
                if not skip_collisions:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Коллизия MAC на строке {row_idx}: {mac_address} уже существует!\n"
                            f"Это может быть прошитая модель. Используйте --skip-collisions для пропуска."
                        )
                    )
                    return
                continue

            # Обработка организации
            organization = None
            if org_name:
                org_key = org_name.lower()
                if org_key in org_cache:
                    organization = org_cache[org_key]
                elif auto_create_org:
                    # Создаем организацию
                    if not dry_run:
                        organization = Organization.objects.create(name=org_name)
                        org_cache[org_key] = organization
                    stats['org_created'] += 1
                    if show_details:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ORG_CREATED (строка {row_idx}): {org_name}"
                            )
                        )
                else:
                    stats['org_not_found'] += 1
                    problems['org_not_found'].append({
                        'row': row_idx,
                        'org': org_name,
                        'ip': ip_address
                    })
                    if show_details:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ORG_NOT_FOUND (строка {row_idx}): {org_name} для IP {ip_address}"
                            )
                        )
                    continue

            # Создание принтера
            printer = Printer(
                ip_address=ip_address,
                serial_number=serial_number or "",
                mac_address=mac_address or None,
                snmp_community=snmp_community,
                organization=organization,
                polling_method=polling_method
            )

            to_create.append(printer)

            # Добавляем в кэш для проверки дублей внутри файла
            existing_ips.add(ip_address)
            if mac_address:
                existing_macs.add(mac_address)

            stats['success'] += 1

            if show_details:
                org_str = f"[{organization.name}]" if organization else "[без организации]"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK (строка {row_idx}): {ip_address} {org_str} | SN:{serial_number or 'пусто'} | "
                        f"MAC:{mac_address or 'пусто'} | {polling_method}"
                    )
                )

        # Сохранение
        if not dry_run and to_create:
            self.stdout.write(f"\nСохраняем {len(to_create)} принтеров...")
            try:
                with transaction.atomic():
                    Printer.objects.bulk_create(to_create)
                    self.stdout.write(self.style.SUCCESS("Все принтеры успешно сохранены!"))
            except Exception as e:
                raise CommandError(f"Ошибка при сохранении: {e}")
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY-RUN: {len(to_create)} принтеров будет создано при реальном запуске"
                )
            )

        # Итоговая статистика
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("ИТОГОВАЯ СТАТИСТИКА:"))
        self.stdout.write(f"  Всего строк обработано: {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"  Успешно подготовлено: {stats['success']}"))

        if stats['ip_collision'] > 0:
            self.stdout.write(
                self.style.ERROR(f"  Коллизии IP адресов: {stats['ip_collision']}")
            )
        if stats['mac_collision'] > 0:
            self.stdout.write(
                self.style.ERROR(f"  Коллизии MAC адресов: {stats['mac_collision']}")
            )
        if stats['org_not_found'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  Организация не найдена: {stats['org_not_found']}")
            )
        if stats['org_created'] > 0:
            self.stdout.write(
                self.style.SUCCESS(f"  Организаций создано: {stats['org_created']}")
            )
        if stats['invalid_ip'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  Невалидные IP адреса: {stats['invalid_ip']}")
            )

        # Детали проблем
        if problems['ip_collisions']:
            self.stdout.write(f"\n{self.style.ERROR('КОЛЛИЗИИ IP АДРЕСОВ:')}")
            for coll in problems['ip_collisions'][:10]:
                self.stdout.write(f"  Строка {coll['row']}: {coll['ip']}")
            if len(problems['ip_collisions']) > 10:
                self.stdout.write(f"  ... и ещё {len(problems['ip_collisions']) - 10}")

        if problems['mac_collisions']:
            self.stdout.write(f"\n{self.style.ERROR('КОЛЛИЗИИ MAC АДРЕСОВ (прошитые модели?):')}")
            for coll in problems['mac_collisions'][:10]:
                self.stdout.write(f"  Строка {coll['row']}: MAC {coll['mac']} (IP: {coll['ip']})")
            if len(problems['mac_collisions']) > 10:
                self.stdout.write(f"  ... и ещё {len(problems['mac_collisions']) - 10}")

        if problems['org_not_found']:
            self.stdout.write(f"\n{self.style.WARNING('ОРГАНИЗАЦИИ НЕ НАЙДЕНЫ:')}")
            for prob in problems['org_not_found'][:10]:
                self.stdout.write(f"  Строка {prob['row']}: '{prob['org']}' (IP: {prob['ip']})")

        # Рекомендации
        if stats['mac_collision'] > 0:
            self.stdout.write(f"\n{self.style.WARNING('⚠️  ВНИМАНИЕ: Обнаружены коллизии MAC адресов!')}")
            self.stdout.write("Это могут быть прошитые модели принтеров.")
            self.stdout.write("Рекомендации:")
            self.stdout.write("  1. Проверьте, действительно ли это прошитые модели")
            self.stdout.write("  2. Если да - используйте --skip-collisions для их пропуска")
            self.stdout.write("  3. Или удалите MAC адреса из Excel для этих принтеров")

        if stats['org_not_found'] > 0:
            self.stdout.write(f"\n{self.style.WARNING('⚠️  Организации не найдены!')}")
            self.stdout.write("Используйте --auto-create-org для автоматического создания организаций")

        if dry_run:
            self.stdout.write(f"\n{self.style.SUCCESS('Для применения изменений запустите команду без --dry-run')}")
        else:
            self.stdout.write(f"\n{self.style.SUCCESS('Импорт завершен!')}")

            # Следующие шаги
            if stats['success'] > 0:
                self.stdout.write(f"\n{self.style.SUCCESS('СЛЕДУЮЩИЕ ШАГИ:')}")
                self.stdout.write("1. Запустите опрос принтеров:")
                self.stdout.write("   python manage.py run_polling")
                self.stdout.write("\n2. После опроса проставьте модели из справочника:")
                self.stdout.write("   python manage.py migrate_models_to_devicemodel --dry-run")
                self.stdout.write("   python manage.py migrate_models_to_devicemodel")
                self.stdout.write("\n3. Через 3 месяца добавьте устройства в contracts и свяжите:")
                self.stdout.write("   python manage.py link_devices_by_serial --dry-run")

    def _validate_ip(self, ip):
        """Простая валидация IP адреса"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except:
            return False
