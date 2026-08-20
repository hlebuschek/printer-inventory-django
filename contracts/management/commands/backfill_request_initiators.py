from django.core.management.base import BaseCommand

from contracts.models import ServiceRequest
from contracts.services_okdesk_import import resolve_initiator
from integrations.models import OkdeskIssue


class Command(BaseCommand):
    help = (
        "Проставляет инициатора заявкам журнала, импортированным из Okdesk: "
        "сопоставляет автора заявки в зеркале с пользователем по ФИО. Okdesk не опрашивается."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Показать результат, ничего не сохраняя")

    def handle(self, *args, **options):
        pending = ServiceRequest.objects.filter(initiator__isnull=True).exclude(external_number="")
        authors = dict(OkdeskIssue.objects.exclude(author_name="").values_list("issue_id", "author_name"))

        resolved = {}
        matched, unmatched = 0, {}
        for service_request in pending:
            author = authors.get(_as_issue_id(service_request.external_number))
            if not author:
                continue
            if author not in resolved:
                resolved[author] = resolve_initiator(author)
            user = resolved[author]
            if user is None:
                unmatched[author] = unmatched.get(author, 0) + 1
                continue
            if not options["dry_run"]:
                service_request.initiator = user
                service_request.save(update_fields=["initiator", "updated_at"])
            matched += 1

        verb = "Сопоставили бы" if options["dry_run"] else "Сопоставлено"
        self.stdout.write(self.style.SUCCESS(f"{verb} заявок: {matched} из {pending.count()}"))
        for author, count in sorted(unmatched.items(), key=lambda item: -item[1]):
            self.stdout.write(f"  не найден пользователь: {author} ({count})")


def _as_issue_id(external_number):
    return int(external_number) if external_number.isdigit() else None
