"""
Ручная синхронизация справочника оборудования Okdesk (OkdeskEquipment).

Выполняет ту же работу, что и ежедневная Celery-задача sync_okdesk_equipment
(beat 03:30), но синхронно — удобно для первичного наполнения на проде.

Примеры использования:
  python manage.py sync_okdesk_equipment
"""

from django.core.management.base import BaseCommand

from integrations.tasks import sync_okdesk_equipment


class Command(BaseCommand):
    help = "Синхронизирует справочник оборудования Okdesk в локальную таблицу OkdeskEquipment"

    def handle(self, *args, **options):
        result = sync_okdesk_equipment.apply(throw=True).result
        for name, info in result["instances"].items():
            if info.get("ok"):
                self.stdout.write(
                    self.style.SUCCESS(f"{name}: {info['synced']} позиций, удалено устаревших: {info['deleted']}")
                )
            else:
                self.stdout.write(self.style.WARNING(f"{name}: пропущен — {info.get('error')}"))
        if not result["ok"]:
            self.stdout.write(self.style.ERROR("Часть инстансов завершилась с ошибкой"))
