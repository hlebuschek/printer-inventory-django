"""Создаёт тестовую группу '5й Армии 2А' с принтерами из исходного письма.

Идемпотентна: повторный запуск обновит location/additional_info по IP.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Printer
from supplies_report.models import ReportGroup, ReportGroupItem

GROUP_NAME = "5й Армии 2А"
GROUP_LOCATION_LABEL = "г. Иркутск, ул. 5й Армии, 2А"

# (sort_order, ip, location_multiline, additional_info_multiline) — порядок и тексты как в письме.
ITEMS = [
    (1, "10.159.112.11", "5 этаж\nПринтпоинт", ""),
    (2, "10.159.112.16", "5 этаж\nкаб. 157.1", "Сотников А.А."),
    (3, "10.159.112.17", "5 этаж\nкаб. 183", "Трушков Д.А."),
    (4, "10.159.112.19", "5 этаж\nкаб. 170", "Казарян В.С.\nПриёмная Галанина И.В."),
    (5, "10.159.112.20", "5 этаж\nкаб. 159", "Чуваев А.А."),
    (6, "10.159.112.22", "5 этаж\nкаб. 144", "Шипилова Е.В."),
    (7, "10.159.112.36", "5 этаж\nкаб. 181", "Ярушина И.О.\nПриёмная Колмогорова В.В."),
    (8, "10.159.112.31", "5 этаж\nкаб. 174", "Рафеева Ю.В."),
    (9, "10.159.112.15", "4 этаж\nПринтпоинт", ""),
    (10, "10.159.112.21", "4 этаж\nПринтпоинт", ""),
    (11, "10.159.112.30", "4 этаж\nкаб. 177", "Толстоухова А.В.\nПриёмная Рафеевой Ю.В."),
    (12, "10.159.112.33", "3 этаж\nПринтпоинт", ""),
    (13, "10.159.112.26", "2 этаж\nПринтпоинт", ""),
]


class Command(BaseCommand):
    help = "Создаёт/обновляет ReportGroup '5й Армии 2А' с 13 принтерами из примера письма."

    @transaction.atomic
    def handle(self, *args, **options):
        group, created = ReportGroup.objects.get_or_create(
            name=GROUP_NAME,
            defaults={
                "location_label": GROUP_LOCATION_LABEL,
                "is_active": True,
            },
        )
        if not created and not group.location_label:
            group.location_label = GROUP_LOCATION_LABEL
            group.save(update_fields=["location_label"])

        self.stdout.write(
            self.style.SUCCESS(f"Группа {'создана' if created else 'найдена'}: id={group.id} name={group.name!r}")
        )

        missing: list[str] = []
        linked = 0
        for sort_order, ip, location, additional in ITEMS:
            try:
                printer = Printer.objects.get(ip_address=ip, is_active=True)
            except Printer.DoesNotExist:
                missing.append(ip)
                continue
            except Printer.MultipleObjectsReturned:
                printer = Printer.objects.filter(ip_address=ip, is_active=True).order_by("-last_updated").first()

            ReportGroupItem.objects.update_or_create(
                group=group,
                printer=printer,
                defaults={
                    "location": location,
                    "additional_info": additional,
                    "sort_order": sort_order,
                },
            )
            linked += 1

        self.stdout.write(self.style.SUCCESS(f"Привязано принтеров: {linked}"))
        if missing:
            self.stdout.write(
                self.style.WARNING("Не найдены активные принтеры по IP — пропущены:\n  " + "\n  ".join(missing))
            )
            self.stdout.write("Подсказка: заведите принтеры в inventory или запустите команду снова после опроса.")
