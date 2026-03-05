"""
Management команда для миграции текстовых моделей в связи с DeviceModel
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from contracts.models import DeviceModel
from inventory.models import Printer


class Command(BaseCommand):
    help = "Мигрирует текстовые модели принтеров в связи с DeviceModel из справочника"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать изменения без применения",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Обновить даже если device_model уже заполнен",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        self.stdout.write(self.style.MIGRATE_HEADING("🔄 Миграция моделей принтеров в DeviceModel"))
        self.stdout.write("-" * 80)

        # Получаем принтеры с заполненным текстовым полем model
        printers_qs = Printer.objects.exclude(Q(model__isnull=True) | Q(model=""))

        if not force:
            # Пропускаем те, у которых device_model уже заполнен
            printers_qs = printers_qs.filter(device_model__isnull=True)

        total_printers = printers_qs.count()
        self.stdout.write(f"📊 Найдено принтеров для миграции: {total_printers}")

        if total_printers == 0:
            self.stdout.write(self.style.WARNING("⚠️  Нет принтеров для миграции"))
            return

        # Счётчики
        matched = 0
        updated = 0
        not_found = 0
        skipped = 0

        # Словарь для кэширования найденных моделей
        model_cache = {}

        for printer in printers_qs.select_related("device_model"):
            model_text = printer.model.strip()

            # Проверяем кэш
            if model_text in model_cache:
                device_model = model_cache[model_text]
            else:
                # Ищем DeviceModel по названию (только по name, без производителя)
                device_model = DeviceModel.objects.filter(name__iexact=model_text).first()

                # Если не нашли, пробуем искать в полном названии
                # (на случай если в текстовом поле есть производитель)
                if not device_model:
                    # Ищем в формате "Manufacturer Model"
                    for dm in DeviceModel.objects.select_related("manufacturer"):
                        full_name = f"{dm.manufacturer.name} {dm.name}"
                        if full_name.lower() == model_text.lower():
                            device_model = dm
                            break

                model_cache[model_text] = device_model

            if not device_model:
                not_found += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  Модель не найдена в справочнике: '{model_text}' " f"(IP: {printer.ip_address})"
                    )
                )
                continue

            matched += 1

            # Проверяем, нужно ли обновление
            if printer.device_model == device_model:
                skipped += 1
                continue

            # Выводим информацию об изменении
            old_value = str(printer.device_model) if printer.device_model else "(пусто)"
            new_value = str(device_model)

            style = self.style.SUCCESS if not dry_run else self.style.WARNING
            prefix = "✅" if not dry_run else "🔍"

            self.stdout.write(
                style(
                    f"{prefix} {printer.ip_address} | SN:{printer.serial_number}\n"
                    f"   Текст: '{model_text}'\n"
                    f"   Было: {old_value}\n"
                    f"   Стало: {new_value}"
                )
            )

            # Применяем изменение если не dry-run
            if not dry_run:
                printer.device_model = device_model
                printer.save(update_fields=["device_model"])

            updated += 1

        # Итоговая статистика
        self.stdout.write("-" * 80)
        self.stdout.write(self.style.MIGRATE_HEADING("📈 Результаты миграции:"))
        self.stdout.write(f"  Всего принтеров: {total_printers}")
        self.stdout.write(self.style.SUCCESS(f"  Найдено в справочнике: {matched}"))
        self.stdout.write(self.style.SUCCESS(f"  Обновлено: {updated}"))
        self.stdout.write(self.style.WARNING(f"  Пропущено (уже актуально): {skipped}"))

        if not_found:
            self.stdout.write(self.style.ERROR(f"  Не найдено в справочнике: {not_found}"))
            self.stdout.write(
                self.style.WARNING(
                    "\n💡 Совет: Добавьте отсутствующие модели в справочник contracts " "и запустите команду повторно"
                )
            )

        if dry_run and updated > 0:
            self.stdout.write(
                "\n"
                + self.style.WARNING(
                    "⚠️  Режим тестирования (--dry-run). " "Для применения изменений запустите без этого флага."
                )
            )
