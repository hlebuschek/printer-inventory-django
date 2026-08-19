# contracts/management/commands/fill_production_calendar.py
"""
Заполняет производственный календарь РФ постоянными праздниками на указанные годы.

Генерируются только даты, закреплённые в статье 112 ТК РФ, и предпраздничные
сокращённые дни. Переносы выходных устанавливаются отдельным постановлением
правительства на каждый год — их нужно вносить вручную через админку
(тип «Рабочий выходной» для перенесённой работы и «Нерабочий праздничный день»
для дня, на который перенесён отдых).

Примеры использования:

# Один год
python manage.py fill_production_calendar 2026

# Несколько лет
python manage.py fill_production_calendar 2026 2027

# Перезаписать уже внесённые дни
python manage.py fill_production_calendar 2026 --overwrite
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from contracts.models import ProductionCalendarDay

# Статья 112 ТК РФ: нерабочие праздничные дни (месяц, день).
FIXED_HOLIDAYS = [
    (1, 1, "Новогодние каникулы"),
    (1, 2, "Новогодние каникулы"),
    (1, 3, "Новогодние каникулы"),
    (1, 4, "Новогодние каникулы"),
    (1, 5, "Новогодние каникулы"),
    (1, 6, "Новогодние каникулы"),
    (1, 7, "Рождество Христово"),
    (1, 8, "Новогодние каникулы"),
    (2, 23, "День защитника Отечества"),
    (3, 8, "Международный женский день"),
    (5, 1, "Праздник Весны и Труда"),
    (5, 9, "День Победы"),
    (6, 12, "День России"),
    (11, 4, "День народного единства"),
]


class Command(BaseCommand):
    help = "Заполняет производственный календарь постоянными праздниками и предпраздничными днями"

    def add_arguments(self, parser):
        parser.add_argument("years", nargs="+", type=int, help="Годы для заполнения")
        parser.add_argument("--overwrite", action="store_true", help="Перезаписать уже внесённые дни")

    @transaction.atomic
    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        created = updated = skipped = 0

        for year in options["years"]:
            holidays = {date(year, month, day): note for month, day, note in FIXED_HOLIDAYS}

            # Рабочий день накануне праздника сокращается. 31 декабря — канун 1 января
            # следующего года, поэтому считается отдельно от списка праздников текущего.
            short_days = set()
            for holiday in list(holidays) + [date(year + 1, 1, 1)]:
                eve = holiday - timedelta(days=1)
                if eve.year != year or eve in holidays or eve.isoweekday() > 5:
                    continue
                short_days.add(eve)

            days = [(d, ProductionCalendarDay.HOLIDAY, note) for d, note in holidays.items()]
            days += [(d, ProductionCalendarDay.SHORT, "Предпраздничный день") for d in short_days]

            for day, kind, note in sorted(days):
                existing = ProductionCalendarDay.objects.filter(date=day).first()
                if existing and not overwrite:
                    skipped += 1
                    continue
                if existing:
                    existing.kind = kind
                    existing.note = note
                    existing.save(update_fields=["kind", "note"])
                    updated += 1
                else:
                    ProductionCalendarDay.objects.create(date=day, kind=kind, note=note)
                    created += 1

            self.stdout.write(f"{year}: праздников {len(holidays)}, предпраздничных {len(short_days)}")

        self.stdout.write(self.style.SUCCESS(f"Создано {created}, обновлено {updated}, пропущено {skipped}"))
        self.stdout.write(
            self.style.WARNING("Переносы выходных на эти годы нужно внести вручную — они задаются постановлением")
        )
