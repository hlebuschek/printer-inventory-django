from django.contrib import admin
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import models
from datetime import datetime
import calendar
import csv

from .models import MonthlyReport, MonthControl
from .models_modelspec import PrinterModelSpec
from .models import CounterChangeLog, BulkChangeLog

@admin.register(PrinterModelSpec)
class PrinterModelSpecAdmin(admin.ModelAdmin):
    list_display = ("model_name", "is_color", "paper_format", "enforce", "updated_at")
    list_filter  = ("is_color", "paper_format", "enforce")
    search_fields = ("model_name",)

@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    # Навигация по датам (по полю month)
    date_hierarchy = "month"

    # Колонки списка
    list_display = (
        "month_fmt",
        "organization",
        "branch",
        "city",
        "equipment_model",
        "serial_number",
        "inventory_number",
        "total_prints",
        "k1_display",
        "k2_display",
    )

    # Фильтры и поиск
    list_filter = ("month", "organization", "city", "branch", "equipment_model")
    search_fields = (
        "organization",
        "branch",
        "city",
        "address",
        "equipment_model",
        "serial_number",
        "inventory_number",
    )

    # Порядок и пагинация
    ordering = ("-month", "organization", "branch", "city", "equipment_model", "serial_number")
    list_per_page = 50

    # Поля, считаемые автоматически (не редактируем вручную)
    readonly_fields = ("total_prints", "k1", "k2")

    # Группировка полей в форме
    fieldsets = (
        (_("Общая информация"), {
            "fields": (
                "month",
                "organization",
                "branch",
                "city",
                "address",
                "equipment_model",
                "serial_number",
                "inventory_number",
            )
        }),
        (_("Показания счётчиков A4"), {
            "fields": ("a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end")
        }),
        (_("Показания счётчиков A3"), {
            "fields": ("a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end")
        }),
        (_("Итоги печати"), {"fields": ("total_prints",)}),
        (_("SLA / заявки"), {
            "fields": ("normative_availability", "actual_downtime", "total_requests", "non_overdue_requests", "k1", "k2")
        }),
    )

    # Действия
    actions = ("export_as_csv", "recalculate_metrics")

    # ----- Представления колонок -----

    @admin.display(description=_("Месяц"))
    def month_fmt(self, obj):
        return obj.month.strftime("%Y-%m")

    @admin.display(description=_("K1 (доступность)"))
    def k1_display(self, obj):
        return "" if obj.k1 is None else f"{obj.k1:.1f}%"

    @admin.display(description=_("K2 (сроки заявок)"))
    def k2_display(self, obj):
        return "" if obj.k2 is None else f"{obj.k2:.1f}%"

    # ----- Actions -----

    @admin.action(description=_("Экспортировать выбранные в CSV"))
    def export_as_csv(self, request, queryset):
        fields = [
            "month", "organization", "branch", "city", "address",
            "equipment_model", "serial_number", "inventory_number",
            "a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end",
            "a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end",
            "total_prints",
            "normative_availability", "actual_downtime",
            "total_requests", "non_overdue_requests",
            "k1", "k2",
        ]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="monthly_report.csv"'
        writer = csv.writer(response, delimiter=";")
        writer.writerow(fields)
        for obj in queryset:
            row = []
            for f in fields:
                val = getattr(obj, f, "")
                if f == "month" and val:
                    val = val.strftime("%Y-%m-%d")
                row.append(val)
            writer.writerow(row)
        return response

    @admin.action(description=_("Пересчитать показатели (total_prints, k1, k2)"))
    def recalculate_metrics(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.save()  # пересчёт по логике модели/сигналов
            count += 1
        self.message_user(request, _(f"Пересчитано записей: {count}"))


# ---- Админка MonthControl ----

class EditableNowFilter(admin.SimpleListFilter):
    title = "Статус редактирования"
    parameter_name = "editable"

    def lookups(self, request, model_admin):
        return (
            ("open", "Открыт"),
            ("closed", "Закрыт"),
        )

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "open":
            return qs.filter(edit_until__gt=now)
        if self.value() == "closed":
            return qs.filter(models.Q(edit_until__lte=now) | models.Q(edit_until__isnull=True))
        return qs


@admin.action(description="Открыть до конца месяца")
def open_until_month_end(modeladmin, request, queryset):
    tz = timezone.get_current_timezone()
    updates = []
    for mc in queryset:
        m = mc.month
        last = calendar.monthrange(m.year, m.month)[1]
        end_dt = timezone.make_aware(datetime(m.year, m.month, last, 23, 59, 59), tz)
        mc.edit_until = end_dt
        updates.append(mc)
    if updates:
        MonthControl.objects.bulk_update(updates, ["edit_until"])


@admin.action(description="Закрыть редактирование")
def close_editing(modeladmin, request, queryset):
    queryset.update(edit_until=None)


@admin.register(MonthControl)
class MonthControlAdmin(admin.ModelAdmin):
    list_display = ("month", "is_editable_icon", "edit_until")
    list_filter = (EditableNowFilter, "month", "edit_until")
    search_fields = ("month",)
    ordering = ("-month",)
    actions = (open_until_month_end, close_editing)

    def is_editable_icon(self, obj):
        return obj.is_editable  # свойство модели
    is_editable_icon.boolean = True
    is_editable_icon.short_description = "Открыт?"

@admin.register(CounterChangeLog)
class CounterChangeLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'monthly_report', 'field_name', 'old_value', 'new_value', 'change_source')
    list_filter = ('change_source', 'field_name', 'timestamp')
    search_fields = ('user__username', 'monthly_report__organization')
    readonly_fields = ('timestamp',)

@admin.register(BulkChangeLog)
class BulkChangeLogAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'user', 'operation_type', 'records_affected', 'success')
    list_filter = ('operation_type', 'success', 'started_at')
    readonly_fields = ('started_at', 'finished_at')