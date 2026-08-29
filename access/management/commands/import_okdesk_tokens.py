"""
Импорт API-токенов Okdesk из CSV-файла.

Формат CSV (с заголовком или без):
    username,token
    ivanov,abc123def456
    petrov,xyz789ghi012

Использование:
    python manage.py import_okdesk_tokens /path/to/tokens.csv
    python manage.py import_okdesk_tokens /path/to/tokens.csv --delimiter ";"
"""

import csv

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from access.models import UserOkdeskToken
from integrations.models import OkdeskInstance

User = get_user_model()


class Command(BaseCommand):
    help = "Импорт API-токенов Okdesk из CSV-файла (username,token)"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Путь к CSV-файлу с токенами")
        parser.add_argument(
            "--delimiter",
            default=",",
            help="Разделитель CSV (по умолчанию запятая)",
        )
        parser.add_argument(
            "--skip-header",
            action="store_true",
            help="Пропустить первую строку (заголовок)",
        )
        parser.add_argument(
            "--provider",
            default=None,
            help="Код подрядчика (ServiceProvider.code), к чьему инстансу Okdesk относятся токены. "
            "Обязателен, если активных инстансов больше одного.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_file"]
        delimiter = options["delimiter"]
        skip_header = options["skip_header"]
        instance = self._resolve_instance(options.get("provider"))
        self.stdout.write(f"Инстанс Okdesk: {instance}")

        created = 0
        updated = 0
        skipped = 0
        errors = []

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)

            for i, row in enumerate(reader, start=1):
                if i == 1 and skip_header:
                    continue

                # Автоопределение заголовка
                if i == 1 and len(row) >= 2:
                    first_col = row[0].strip().lower()
                    if first_col in ("username", "user", "логин", "пользователь"):
                        self.stdout.write(f"Пропущен заголовок: {row}")
                        continue

                if len(row) < 2:
                    errors.append(f"Строка {i}: недостаточно колонок ({row})")
                    continue

                username = row[0].strip()
                token = row[1].strip()

                if not username or not token:
                    errors.append(f"Строка {i}: пустой username или token")
                    continue

                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    errors.append(f"Строка {i}: пользователь '{username}' не найден")
                    skipped += 1
                    continue

                obj, is_new = UserOkdeskToken.objects.get_or_create(
                    user=user, instance=instance, defaults={"encrypted_token": ""}
                )
                obj.set_token(token)
                obj.save()

                if is_new:
                    created += 1
                else:
                    updated += 1

                self.stdout.write(f"  {'Создан' if is_new else 'Обновлён'}: {username}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Создано: {created}, обновлено: {updated}, пропущено: {skipped}"))

        if errors:
            self.stdout.write(self.style.WARNING(f"\nОшибки ({len(errors)}):"))
            for err in errors:
                self.stderr.write(f"  {err}")

    def _resolve_instance(self, provider_code):
        qs = OkdeskInstance.objects.filter(is_active=True).select_related("service_provider")
        if provider_code:
            instance = qs.filter(service_provider__code=provider_code).first()
            if instance is None:
                raise CommandError(f"Активный инстанс Okdesk для подрядчика «{provider_code}» не найден")
            return instance
        instances = list(qs)
        if not instances:
            raise CommandError("Нет активных инстансов Okdesk")
        if len(instances) > 1:
            codes = ", ".join(i.service_provider.code for i in instances)
            raise CommandError(f"Несколько активных инстансов ({codes}) — укажите --provider <code>")
        return instances[0]
