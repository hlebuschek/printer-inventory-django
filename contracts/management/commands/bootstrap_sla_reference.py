# contracts/management/commands/bootstrap_sla_reference.py
"""
Заполняет справочники для расчёта показателей качества услуги (K1/K2).

Создаёт график работы по умолчанию, заводит отсутствующие города из Таблицы №2
технического задания и проставляет всем городам часовой пояс и норматив
устранения инцидента.

Источник истины — договор, поэтому команда идемпотентна и при каждом запуске
переписывает значения из ТЗ. Ручные правки в админке будут перетёрты.

Примеры использования:

# Показать, что будет изменено
python manage.py bootstrap_sla_reference --dry-run

# Заполнить справочники
python manage.py bootstrap_sla_reference
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from contracts.models import City, WorkSchedule

DEFAULT_SCHEDULE_NAME = "Стандартный 5/2, 08:00-17:00"

# Таблица №2 ТЗ: города присутствия сервисной службы — 8 рабочих часов, остальные — 16.
SLA_8H_CITIES = [
    "Абакан",
    "Ангарск",
    "Ачинск",
    "Братск",
    "Железногорск-Илимский",
    "Иркутск",
    "Листвянка",
    "Саяногорск",
    "Саянск",
    "Тайшет",
    "Усолье-Сибирское",
    "Усть-Илимск",
    "Черемхово",
    "Шелехов",
]

# Города Хакасии, Тывы и Красноярского края лежат в UTC+7, остальные обслуживаемые — в UTC+8.
KRASNOYARSK_CITIES = ["Абакан", "Ачинск", "Ирбейское", "Каа-Хем", "Саяногорск", "Чадан"]


class Command(BaseCommand):
    help = "Создаёт график по умолчанию, заводит города из ТЗ и заполняет часовой пояс и норматив SLA"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Показать изменения без записи в БД")

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        schedule = WorkSchedule.objects.filter(is_default=True).first()
        if schedule:
            self.stdout.write(f"График по умолчанию уже задан: {schedule.name}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Создаю график по умолчанию: {DEFAULT_SCHEDULE_NAME}"))
            if not dry_run:
                WorkSchedule.objects.create(
                    name=DEFAULT_SCHEDULE_NAME,
                    work_start=time(8, 0),
                    work_end=time(17, 0),
                    weekdays="12345",
                    short_day_minutes=60,
                    is_default=True,
                )

        sla_8h = {name.lower() for name in SLA_8H_CITIES}
        krasnoyarsk = {name.lower() for name in KRASNOYARSK_CITIES}

        existing = {name.lower() for name in City.objects.values_list("name", flat=True)}
        created = 0
        for name in SLA_8H_CITIES:
            if name.lower() in existing:
                continue
            tz = "Asia/Krasnoyarsk" if name.lower() in krasnoyarsk else "Asia/Irkutsk"
            self.stdout.write(self.style.SUCCESS(f"  Создаю город из ТЗ: {name} (SLA 8 ч, ТЗ {tz})"))
            created += 1
            if not dry_run:
                City.objects.create(name=name, timezone=tz, sla_standard_hours=8)

        self.stdout.write(self.style.SUCCESS(f"Городов создано: {created}"))

        updated = 0
        for city in City.objects.all():
            key = city.name.lower()
            hours = 8 if key in sla_8h else 16
            tz = "Asia/Krasnoyarsk" if key in krasnoyarsk else "Asia/Irkutsk"

            if city.sla_standard_hours == hours and city.timezone == tz:
                continue

            self.stdout.write(f"  {city.name}: SLA {city.sla_standard_hours} → {hours} ч, ТЗ {city.timezone} → {tz}")
            updated += 1
            if not dry_run:
                city.sla_standard_hours = hours
                city.timezone = tz
                city.save(update_fields=["sla_standard_hours", "timezone"])

        self.stdout.write(self.style.SUCCESS(f"Городов обновлено: {updated}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Режим --dry-run: изменения откачены"))
            transaction.set_rollback(True)
