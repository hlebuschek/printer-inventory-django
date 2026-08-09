"""
Импорт устройств по договору из Excel — обёртка над contracts.services_import.

Логика та же, что и у веб-интерфейса (/contracts/import/): файлы разбираются
в сессию импорта, строки классифицируются, затем сессия применяется.

Примеры:
    python manage.py contracts_import_xlsx devices.xlsx --status "Активен" --provider amb --dry-run
    python manage.py contracts_import_xlsx devices.xlsx --status "Активен" --provider tonex --create-cities
    python manage.py contracts_import_xlsx a.xlsx b.xlsx --status "Активен" --provider amb --apply-conflicts
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from contracts.models import ContractStatus, ImportRow, ImportSession, ServiceProvider
from contracts.services_import import (
    CONFLICT_CLASSES,
    ImportFileError,
    analyze_file,
    apply_session,
    find_missing_devices,
    rows_to_apply,
    session_summary,
)


class Command(BaseCommand):
    help = "Импортирует устройства по договору из xlsx-файлов"

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="Пути к xlsx-файлам")
        parser.add_argument("--sheet", default=None, help="Имя листа (по умолчанию активный)")
        parser.add_argument("--status", required=True, help="Статус для загружаемых устройств")
        parser.add_argument("--provider", required=True, help="Код подрядчика, например amb или tonex")
        parser.add_argument("--create-cities", action="store_true", help="Создавать отсутствующие города")
        parser.add_argument("--apply-conflicts", action="store_true", help="Применять конфликтные строки")
        parser.add_argument("--dry-run", action="store_true", help="Только разбор и сводка, без записи")
        parser.add_argument("--user", default=None, help="Username для журнала изменений")

    def handle(self, *args, **options):
        status = ContractStatus.objects.filter(name__iexact=options["status"].strip()).first()
        if status is None:
            available = ", ".join(ContractStatus.objects.values_list("name", flat=True))
            raise CommandError(f"Статус «{options['status']}» не найден. Доступные: {available}")

        provider = ServiceProvider.objects.filter(code__iexact=options["provider"].strip()).first()
        if provider is None:
            available = ", ".join(ServiceProvider.objects.values_list("code", flat=True))
            raise CommandError(f"Подрядчик «{options['provider']}» не найден. Доступные: {available}")

        user = None
        if options["user"]:
            user = get_user_model().objects.filter(username=options["user"]).first()
            if user is None:
                raise CommandError(f"Пользователь «{options['user']}» не найден")

        session = ImportSession.objects.create(
            name=f"CLI: {', '.join(Path(p).name for p in options['paths'])}"[:255],
            target_status=status,
            service_provider=provider,
            created_by=user,
        )

        try:
            self._analyze(session, options)
            self._report_summary(session_summary(session))

            if options["apply_conflicts"]:
                session.rows.filter(classification__in=CONFLICT_CLASSES).update(decision=ImportRow.APPLY)

            if options["dry_run"]:
                self.stdout.write(self.style.WARNING("\n--dry-run: изменения не записаны"))
                session.delete()
                return

            self._apply(session, user, options)
        except Exception:
            if session.state != ImportSession.APPLIED:
                session.delete()
            raise

    def _analyze(self, session, options):
        for path in options["paths"]:
            file_path = Path(path)
            if not file_path.exists():
                raise CommandError(f"Файл не найден: {path}")

            with file_path.open("rb") as fh:
                try:
                    import_file = analyze_file(session, fh, file_path.name, sheet=options["sheet"])
                except ImportFileError as exc:
                    raise CommandError(str(exc))

            self.stdout.write(f"{file_path.name}: строк {import_file.rows_total}")

    def _report_summary(self, summary):
        labels = dict(ImportRow.CLASSIFICATION_CHOICES)
        self.stdout.write("")
        for code, count in summary["counts"].items():
            self.stdout.write(f"  {labels.get(code, code)}: {count}")

        for key, title in (
            ("unknown_organizations", "Организации не в справочнике"),
            ("unknown_models", "Модели не в справочнике"),
            ("new_cities", "Новые города"),
        ):
            if summary[key]:
                style = self.style.WARNING if key == "new_cities" else self.style.ERROR
                self.stdout.write(style(f"\n{title} ({len(summary[key])}):"))
                for name in summary[key]:
                    self.stdout.write(f"  {name}")

        if summary["pending_conflicts"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\nКонфликтных строк без решения: {summary['pending_conflicts']} — "
                    "применены не будут, см. --apply-conflicts"
                )
            )

    def _apply(self, session, user, options):
        if not rows_to_apply(session).count():
            raise CommandError("Нет строк, готовых к применению")

        try:
            result = apply_session(session, user=user, create_cities=options["create_cities"])
        except ImportFileError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nСоздано: {result['created']}, обновлено: {result['updated']}, "
                f"ошибок: {result['failed']} из {result['total']}"
            )
        )
        for message in result["errors"]:
            self.stdout.write(self.style.ERROR(f"  {message}"))

        missing = find_missing_devices(session).count()
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"\nВ файлах не найдено устройств из БД: {missing} "
                    f"(выгрузка: /contracts/api/import/sessions/{session.id}/missing/export/)"
                )
            )
