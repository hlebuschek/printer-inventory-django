from django.core.management.base import BaseCommand

from contracts.services_okdesk_import import import_issues


class Command(BaseCommand):
    help = "Импортирует заявки Okdesk (с комментариями и файлами) в журнал заявок. Только чтение из Okdesk."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Импортировать не больше N открытых заявок")
        parser.add_argument("--closed", type=int, default=0, help="Дополнительно импортировать N последних закрытых")

    def handle(self, *args, **options):
        stats = import_issues(limit=options["limit"], closed_limit=options["closed"])
        self.stdout.write(
            self.style.SUCCESS(
                "Создано открытых: {open}, выполненных: {closed}, закрыто по синку: {completed}, "
                "сообщений: {comments}, актов: {acts}, ошибок: {errors}".format(**stats)
            )
        )
