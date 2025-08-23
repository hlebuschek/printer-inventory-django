from django.core.management.base import BaseCommand
from inventory.models import Printer, MatchRule
import csv

class Command(BaseCommand):
    help = "Список принтеров, у которых последний успешный импорт прошёл ТОЛЬКО по MAC. Можно выгрузить в CSV."

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, default='', help='Путь к CSV-файлу для выгрузки')

    def handle(self, *args, **opts):
        qs = Printer.objects.filter(last_match_rule=MatchRule.MAC_ONLY).order_by('ip_address')
        if not qs.exists():
            self.stdout.write(self.style.WARNING("Таких принтеров не найдено."))
            return
        self.stdout.write(self.style.SUCCESS(f"Найдено: {qs.count()}"))
        rows = [(p.ip_address, p.serial_number, p.mac_address or '', p.model or '', p.organization.name if p.organization else '') for p in qs]
        if opts['csv']:
            with open(opts['csv'], 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(['IP', 'Серийник', 'MAC', 'Модель', 'Организация'])
                w.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"CSV сохранён: {opts['csv']}"))
        else:
            for r in rows:
                self.stdout.write(" | ".join(r))
