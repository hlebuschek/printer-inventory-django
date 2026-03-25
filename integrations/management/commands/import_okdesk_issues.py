"""
Импорт заявок Okdesk из SQLite БД.

Использование:
    python manage.py import_okdesk_issues /path/to/issues.db
"""

import sqlite3

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from integrations.models import OkdeskIssue


class Command(BaseCommand):
    help = "Импорт заявок из SQLite БД Okdesk"

    def add_arguments(self, parser):
        parser.add_argument("db_path", type=str, help="Путь к файлу issues.db")

    def handle(self, *args, **options):
        db_path = options["db_path"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM issues")
        rows = cursor.fetchall()
        conn.close()

        self.stdout.write(f"Найдено заявок в SQLite: {len(rows)}")

        created = 0
        updated = 0

        for row in rows:
            defaults = {
                "title": row["title"] or "",
                "created_at": parse_datetime(row["created_at"]) if row["created_at"] else None,
                "completed_at": parse_datetime(row["completed_at"]) if row["completed_at"] else None,
                "status_name": row["status_name"] or "",
                "priority_name": row["priority_name"] or "",
                "assignee_name": row["assignee_name"] or "",
                "company_name": row["company_name"] or "",
                "serial_numbers": row["serial_numbers"] or "",
                "is_overdue": bool(row["is_overdue"]),
            }

            _, is_created = OkdeskIssue.objects.update_or_create(
                issue_id=row["id"],
                defaults=defaults,
            )

            if is_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Импорт завершён: создано {created}, обновлено {updated}, всего {created + updated}"
            )
        )
