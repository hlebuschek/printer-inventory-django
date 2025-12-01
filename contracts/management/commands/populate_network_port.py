# contracts/management/commands/populate_network_port.py
"""
Команда для автоматического заполнения поля has_network_port в моделях DeviceModel.

Проходит по всем моделям устройств и проверяет, есть ли в inventory (Printer)
устройства с этой моделью. Если есть, значит модель имеет сетевой порт.

Примеры использования:

# Анализ без изменений (dry-run)
python manage.py populate_network_port --dry-run

# Обновление has_network_port для всех моделей
python manage.py populate_network_port

# Только для конкретного производителя
python manage.py populate_network_port --manufacturer "HP"

# С детальным выводом
python manage.py populate_network_port --verbose
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from contracts.models import DeviceModel
from inventory.models import Printer


class Command(BaseCommand):
    help = (
        "Автоматически заполняет поле has_network_port для моделей DeviceModel, "
        "проверяя наличие устройств в inventory (Printer)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать результаты анализа, не сохранять изменения",
        )
        parser.add_argument(
            "--manufacturer",
            type=str,
            help="Обработать только модели указанного производителя",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Показать детальную информацию по каждой модели",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        manufacturer_filter = opts["manufacturer"]
        verbose = opts["verbose"]

        self.stdout.write(
            self.style.SUCCESS("=== Заполнение has_network_port для моделей DeviceModel ===")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Режим DRY-RUN: изменения не будут сохранены"))

        # Базовый queryset моделей
        models_qs = DeviceModel.objects.select_related('manufacturer').all()

        if manufacturer_filter:
            models_qs = models_qs.filter(manufacturer__name__icontains=manufacturer_filter)
            self.stdout.write(f"Фильтр по производителю: {manufacturer_filter}")

        total_models = models_qs.count()
        self.stdout.write(f"Всего моделей для обработки: {total_models}")

        # Счетчики
        updated_count = 0
        already_marked_count = 0
        no_change_count = 0

        with transaction.atomic():
            for model in models_qs:
                # Проверяем, есть ли принтеры с этой моделью в inventory
                printers_count = Printer.objects.filter(device_model=model).count()

                # Определяем должно ли быть True
                should_have_port = printers_count > 0

                # Текущее значение
                current_value = model.has_network_port

                if verbose:
                    self.stdout.write(f"\n{model.manufacturer.name} {model.name}:")
                    self.stdout.write(f"  - Принтеров в inventory: {printers_count}")
                    self.stdout.write(f"  - Текущее значение has_network_port: {current_value}")
                    self.stdout.write(f"  - Должно быть: {should_have_port}")

                if should_have_port and not current_value:
                    # Нужно установить True
                    if not dry_run:
                        model.has_network_port = True
                        model.save(update_fields=['has_network_port'])

                    updated_count += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS("  → Обновлено: has_network_port = True"))
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ {model.manufacturer.name} {model.name}: установлен сетевой порт ({printers_count} принтеров)")
                        )

                elif should_have_port and current_value:
                    # Уже корректно установлено
                    already_marked_count += 1
                    if verbose:
                        self.stdout.write(self.style.NOTICE("  → Без изменений (уже True)"))

                elif not should_have_port and current_value:
                    # Сетевой порт установлен, но принтеров нет - оставляем как есть
                    # (может быть установлено вручную)
                    no_change_count += 1
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING("  → Без изменений (установлено вручную, принтеров нет)")
                        )

                else:
                    # Не установлен и не должен быть
                    no_change_count += 1
                    if verbose:
                        self.stdout.write(self.style.NOTICE("  → Без изменений (False)"))

            if dry_run:
                # Откатываем транзакцию при dry-run
                transaction.set_rollback(True)

        # Итоговая статистика
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Итоги:"))
        self.stdout.write(f"Всего обработано моделей: {total_models}")
        self.stdout.write(self.style.SUCCESS(f"Обновлено (установлен сетевой порт): {updated_count}"))
        self.stdout.write(f"Уже было установлено корректно: {already_marked_count}")
        self.stdout.write(f"Без изменений: {no_change_count}")

        if dry_run:
            self.stdout.write("\n" + self.style.WARNING(
                "Это был режим DRY-RUN. Для сохранения изменений запустите без --dry-run"
            ))
        else:
            self.stdout.write("\n" + self.style.SUCCESS("Изменения успешно сохранены!"))
