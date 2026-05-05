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
    build_contract_device_map,
    build_reference_serials,
    deduplicate_serials,
    find_serials_in_text,
    parse_html_table,
    relink_orphan_row,
    resolve_devices,
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
        parser.add_argument(
            "--issue-id",
            type=int,
            default=None,
            help="Обработать одну конкретную заявку по issue_id (для отладки)",
        )
        parser.add_argument(
            "--from-stored-serials",
            action="store_true",
            help="Не ходить в Okdesk API: только релинковать orphan-строки на ContractDevice "
            "по уже сохранённому полю serial_numbers. Быстрый путь для пост-миграционного "
            "переноса данных через CSV (см. import_okdesk_serials.py).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        from_stored = options.get("from_stored_serials", False)

        # Справочник серийников
        reference_serials, reference_lookup = build_reference_serials()
        contract_device_map = build_contract_device_map()
        self.stdout.write(f"Загружено эталонных серийников из ContractDevice: {len(reference_serials)}")

        if from_stored:
            self._run_from_stored_serials(
                contract_device_map=contract_device_map,
                dry_run=dry_run,
                limit=limit,
                issue_id=options.get("issue_id"),
            )
            return

        api_token = getattr(settings, "OKDESK_API_TOKEN", "")
        if not api_token:
            self.stderr.write(self.style.ERROR("OKDESK_API_TOKEN не настроен в .env"))
            return

        api_url = getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")

        # Заявки для обработки.
        # По умолчанию — orphan-строки (contract_device=NULL) без серийников.
        # --force — все заявки с device=NULL (включая те, у которых serial_numbers заполнен,
        # но в ContractDevice не нашёлся при прошлом проходе).
        if options.get("issue_id"):
            qs = OkdeskIssue.objects.filter(issue_id=options["issue_id"], contract_device__isnull=True)
        else:
            qs = OkdeskIssue.objects.filter(contract_device__isnull=True).order_by("issue_id")
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
                    matched = resolve_devices([s.strip() for s in result.split(",") if s.strip()], contract_device_map)

                    if not dry_run:
                        if not matched:
                            # Серийник найден, но в ContractDevice не нашёлся → остаёмся orphan,
                            # но обновляем текст serial_numbers для прозрачности.
                            issue.serial_numbers = result
                            issue.save(update_fields=["serial_numbers"])
                        else:
                            relink_orphan_row(issue, matched)

                    suffix = f" → {len(matched)} dev" if matched else " (нет в ContractDevice)"
                    self.stdout.write(f"  #{issue.issue_id}: {result}{suffix}")
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

    def _run_from_stored_serials(self, contract_device_map, dry_run, limit, issue_id):
        """
        Быстрый путь: ребиндинг orphan-строк по уже сохранённому полю serial_numbers,
        без обращения к Okdesk API. Используется после переноса данных через CSV.
        """
        qs = OkdeskIssue.objects.filter(contract_device__isnull=True).exclude(serial_numbers="").order_by("issue_id")
        if issue_id:
            qs = qs.filter(issue_id=issue_id)
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Orphan-строк с заполненным serial_numbers: {total}")
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нечего ребиндить"))
            return

        relinked = 0
        cloned = 0
        no_match = 0

        for issue in qs.iterator():
            serials_list = [s.strip() for s in (issue.serial_numbers or "").split(",") if s.strip()]
            matched = resolve_devices(serials_list, contract_device_map)

            if not matched:
                no_match += 1
                continue

            if not dry_run:
                cloned += relink_orphan_row(issue, matched)
            relinked += 1

            if (relinked + no_match) % 200 == 0:
                self.stdout.write(f"  ... обработано {relinked + no_match}/{total}")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Ребиндинг завершён:"))
        self.stdout.write(f"  Обработано:           {relinked + no_match}")
        self.stdout.write(f"  Привязано к device:   {relinked}")
        self.stdout.write(f"  Клонов создано:       {cloned}")
        self.stdout.write(f"  Нет в ContractDevice: {no_match}")
