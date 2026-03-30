"""
Обогащение заявок Okdesk серийными номерами.

Для каждой заявки без serial_numbers:
1. Запрашивает полное описание заявки из Okdesk API
2. Парсит HTML-таблицу в описании, ищет колонку «Серийный номер»
3. Если не нашёл — ищет серийники из ContractDevice по тексту (title + description)
4. Если не нашёл — ищет в Excel-вложениях заявки
5. Обновляет поле serial_numbers в OkdeskIssue

Использование:
    python manage.py enrich_okdesk_serials              # только заявки без серийника
    python manage.py enrich_okdesk_serials --force       # все заявки заново
    python manage.py enrich_okdesk_serials --dry-run     # без сохранения
"""

import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.models import OkdeskIssue
from integrations.okdesk_enrichment import (
    build_reference_serials,
    deduplicate_serials,
    find_serials_in_text,
    parse_html_table,
    search_excel_attachments,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Обогащение заявок Okdesk серийными номерами из описаний"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписать серийники для всех заявок (не только пустых)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не сохранять изменения, только показать что будет найдено",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Ограничить количество обрабатываемых заявок (0 = все)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        api_token = getattr(settings, "OKDESK_API_TOKEN", "")
        if not api_token:
            self.stderr.write(self.style.ERROR("OKDESK_API_TOKEN не настроен в .env"))
            return

        api_url = getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")

        # Справочник серийников
        reference_serials, reference_lookup = build_reference_serials()
        self.stdout.write(f"Загружено эталонных серийников из ContractDevice: {len(reference_serials)}")

        # Заявки для обработки
        qs = OkdeskIssue.objects.all().order_by("issue_id")
        if not force:
            qs = qs.filter(serial_numbers="")

        total = qs.count()
        if limit:
            qs = qs[:limit]
            total = min(total, limit)

        self.stdout.write(f"Заявок для обработки: {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нечего обрабатывать"))
            return

        stats = {
            "processed": 0,
            "found_in_table": 0,
            "found_in_text": 0,
            "found_in_excel": 0,
            "not_found": 0,
            "errors": 0,
        }

        for issue in qs.iterator():
            stats["processed"] += 1

            try:
                # Запрашиваем полные данные заявки
                resp = requests.get(
                    f"{api_url}/issues/{issue.issue_id}/",
                    params={"api_token": api_token},
                    verify=settings.OKDESK_VERIFY_SSL,
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                description = data.get("description", "") or ""
                title = data.get("title", "") or ""
                attachments = data.get("attachments") or []

                final_serials = []

                # Шаг 1: Парсим HTML-таблицу в описании
                if description:
                    table_serials = parse_html_table(description, reference_lookup)
                    if table_serials:
                        final_serials = table_serials
                        stats["found_in_table"] += 1

                # Шаг 2: Если не нашли — ищем по тексту
                if not final_serials:
                    search_text = title + " " + description
                    found = find_serials_in_text(search_text, reference_serials)
                    if found:
                        final_serials = found
                        stats["found_in_text"] += 1

                # Шаг 3: Если не нашли — ищем в Excel-вложениях
                if not final_serials and attachments:
                    excel_serials = search_excel_attachments(issue.issue_id, attachments, api_token, reference_lookup)
                    if excel_serials:
                        final_serials = excel_serials
                        stats["found_in_excel"] += 1

                # Сохраняем
                if final_serials:
                    result = deduplicate_serials(final_serials)

                    if not dry_run:
                        issue.serial_numbers = result
                        issue.save(update_fields=["serial_numbers"])

                    self.stdout.write(f"  #{issue.issue_id}: {result}")
                else:
                    stats["not_found"] += 1
                    if stats["processed"] <= 20 or stats["processed"] % 100 == 0:
                        self.stdout.write(self.style.WARNING(f"  #{issue.issue_id}: серийник не найден"))

                # Прогресс
                if stats["processed"] % 50 == 0:
                    self.stdout.write(
                        f"  ... обработано {stats['processed']}/{total} "
                        f"(таблица: {stats['found_in_table']}, текст: {stats['found_in_text']}, "
                        f"excel: {stats['found_in_excel']}, не найдено: {stats['not_found']})"
                    )

                # Rate limiting
                time.sleep(0.15)

            except requests.RequestException as e:
                stats["errors"] += 1
                self.stderr.write(self.style.ERROR(f"  #{issue.issue_id}: ошибка API — {e}"))
                time.sleep(1)
            except Exception as e:
                stats["errors"] += 1
                self.stderr.write(self.style.ERROR(f"  #{issue.issue_id}: ошибка — {e}"))

        # Итоги
        self.stdout.write("")
        self.stdout.write("=" * 60)
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Обогащение завершено:"))
        self.stdout.write(f"  Обработано:                {stats['processed']}")
        self.stdout.write(f"  Найдено в таблице:         {stats['found_in_table']}")
        self.stdout.write(f"  Найдено поиском по тексту: {stats['found_in_text']}")
        self.stdout.write(f"  Найдено в Excel-вложениях: {stats['found_in_excel']}")
        self.stdout.write(f"  Не найдено:                {stats['not_found']}")
        self.stdout.write(f"  Ошибок:                    {stats['errors']}")
