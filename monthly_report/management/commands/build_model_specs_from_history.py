from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, Q, Value, IntegerField, Case, When, Sum, ExpressionWrapper
from django.db.models.functions import Coalesce
from monthly_report.models import MonthlyReport
from monthly_report.models_modelspec import PrinterModelSpec, PaperFormat
from monthly_report.specs import SPEC_CACHE
from django.utils import timezone
from datetime import datetime
import re
from django.db.models import ExpressionWrapper, IntegerField, F, Value
from django.db.models.functions import Coalesce, Greatest

COUNTER_FIELDS = {
    "a4_bw_start","a4_bw_end","a4_color_start","a4_color_end",
    "a3_bw_start","a3_bw_end","a3_color_start","a3_color_end",
}

def norm_model_name(s: str) -> str:
    """Аккуратно нормализуем название модели: схлопываем лишние пробелы."""
    return " ".join((s or "").strip().split())

def delta(end_field: str, start_field: str):
    """max(0, coalesce(end,0) - coalesce(start,0)) как ORM-выражение."""
    return ExpressionWrapper(
        Greatest(
            Value(0),
            Coalesce(F(end_field), 0) - Coalesce(F(start_field), 0),
        ),
        output_field=IntegerField(),
    )

class Command(BaseCommand):
    help = (
        "1) Сканирует MonthlyReport и выводит для каждой модели: цветность и формат бумаги.\n"
        "2) Создаёт/обновляет PrinterModelSpec.\n"
        "3) (опц.) Переписывает существующие строки отчёта под правила модели и пересчитывает месяцы."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="По умолчанию DRY-RUN. С --apply изменения сохраняются.")
        parser.add_argument("--only-missing", action="store_true",
                            help="Обновлять только отсутствующие записи справочника.")
        parser.add_argument("--since", type=str, default="",
                            help="Фильтр по месяцу (YYYY-MM): учитывать отчёты начиная с этого месяца включительно.")
        parser.add_argument("--rewrite-existing", action="store_true",
                            help="После создания правил обнулить в MonthlyReport запрещённые полями и пересчитать месяцы.")
        parser.add_argument("--case-sensitive", action="store_true",
                            help="Сопоставлять название модели чувствительно к регистру (по умолчанию iexact).")

    def handle(self, *args, **opt):
        since = opt["since"].strip()
        month_filter = {}
        if since:
            m = re.fullmatch(r"(\d{4})-(\d{2})", since)
            if not m:
                self.stderr.write(self.style.ERROR("Неверный формат --since, ожидается YYYY-MM"))
                return
            y, mm = int(m.group(1)), int(m.group(2))
            month_filter = {"month__gte": datetime(y, mm, 1).date()}

        # список уникальных моделей
        base_qs = MonthlyReport.objects.exclude(equipment_model__isnull=True).exclude(equipment_model__exact="")
        if month_filter:
            base_qs = base_qs.filter(**month_filter)

        model_names = base_qs.values_list("equipment_model", flat=True).distinct()

        total = 0
        changed = 0
        dry = not opt["apply"]

        for raw_name in model_names:
            name = norm_model_name(raw_name)
            if not name:
                continue

            qs = MonthlyReport.objects
            if month_filter:
                qs = qs.filter(**month_filter)
            qs = qs.filter(equipment_model__iexact=name) if not opt["case_sensitive"] else qs.filter(equipment_model=name)

            # аннотируем дельты и агрегируем признаки
            agg = (
                qs.annotate(
                    a4_bw=delta("a4_bw_end", "a4_bw_start"),
                    a4_c =delta("a4_color_end", "a4_color_start"),
                    a3_bw=delta("a3_bw_end", "a3_bw_start"),
                    a3_c =delta("a3_color_end", "a3_color_start"),
                )
                .aggregate(
                    any_color=Sum(Case(When(Q(a4_c__gt=0) | Q(a3_c__gt=0), then=1), default=0, output_field=IntegerField())),
                    any_a4   =Sum(Case(When(Q(a4_bw__gt=0) | Q(a4_c__gt=0), then=1), default=0, output_field=IntegerField())),
                    any_a3   =Sum(Case(When(Q(a3_bw__gt=0) | Q(a3_c__gt=0), then=1), default=0, output_field=IntegerField())),
                )
            )

            any_color = (agg["any_color"] or 0) > 0
            any_a4    = (agg["any_a4"] or 0) > 0
            any_a3    = (agg["any_a3"] or 0) > 0

            if any_a3 and not any_a4:
                fmt = PaperFormat.A3_ONLY
            elif any_a4 and not any_a3:
                fmt = PaperFormat.A4_ONLY
            elif any_a4 and any_a3:
                fmt = PaperFormat.A4_A3
            else:
                fmt = PaperFormat.A4_A3  # данных нет → не жёстко ограничиваем

            enforce = True if (any_a4 or any_a3) else False

            total += 1

            spec, created = PrinterModelSpec.objects.get_or_create(
                model_name=name,
                defaults={"is_color": any_color, "paper_format": fmt, "enforce": enforce},
            )

            if opt["only_missing"] and not created:
                self.stdout.write(f"SKIP (exists): {name}")
                continue

            to_update = []
            if not created:
                if spec.is_color != any_color: spec.is_color = any_color; to_update.append("is_color")
                if spec.paper_format != fmt:   spec.paper_format = fmt;   to_update.append("paper_format")
                if spec.enforce != enforce:    spec.enforce = enforce;    to_update.append("enforce")

            if created:
                changed += 1
                self.stdout.write(self.style.SUCCESS(
                    f"{'[APPLY]' if opt['apply'] else '[DRY]'} CREATE {name} → color={any_color}, format={fmt}, enforce={enforce}"
                ))
                if dry:
                    # откатим создание в dry-run
                    spec.delete()
                else:
                    pass
            elif to_update:
                changed += 1
                self.stdout.write(self.style.WARNING(
                    f"{'[APPLY]' if opt['apply'] else '[DRY]'} UPDATE {name} → color={any_color}, format={fmt}, enforce={enforce}"
                ))
                if not dry:
                    spec.save(update_fields=to_update)
            else:
                self.stdout.write(f"OK {name} (без изменений)")

        if not dry:
            SPEC_CACHE.clear()

        # Переписать существующие строки под правила (обнулить запрещённые поля) и пересчитать месяцы
        if opt["rewrite_existing"]:
            if dry:
                self.stdout.write(self.style.WARNING("DRY-RUN: пропускаю перепись существующих строк (--apply не задан)."))
            else:
                self._rewrite_existing(month_filter, case_sensitive=opt["case_sensitive"])

        self.stdout.write(self.style.SUCCESS(
            f"Готово: моделей просмотрено={total}, изменений={changed}, режим={'APPLY' if opt['apply'] else 'DRY-RUN'}"
        ))

    @transaction.atomic
    def _rewrite_existing(self, month_filter: dict, case_sensitive: bool):
        from monthly_report.specs import get_spec_for_model_name, allowed_counter_fields
        from monthly_report.services import recompute_month

        changed_rows = 0
        months_touched = set()

        qs = MonthlyReport.objects.all()
        if month_filter:
            qs = qs.filter(**month_filter)

        # Идём батчами, чтобы не держать огромную транзакцию
        for row in qs.select_for_update(skip_locked=True).iterator(chunk_size=1000):
            spec = get_spec_for_model_name(row.equipment_model)
            allowed = allowed_counter_fields(spec)
            updated = []
            for f in COUNTER_FIELDS:
                if allowed and f not in allowed and getattr(row, f, 0):
                    setattr(row, f, 0)
                    updated.append(f)
            if updated:
                row.save(update_fields=updated)
                changed_rows += 1
                months_touched.add(row.month)

        for m in months_touched:
            recompute_month(m)

        self.stdout.write(self.style.SUCCESS(
            f"Переписано строк: {changed_rows}, месяцев пересчитано: {len(months_touched)}"
        ))
