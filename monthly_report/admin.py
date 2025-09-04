# monthly_report/admin.py
from django.contrib import admin
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
import csv

from .models import MonthlyReport


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
            # save() пересчитает total_prints/k1/k2 по вашей логике модели
            obj.save()
            count += 1
        self.message_user(request, _(f"Пересчитано записей: {count}"))
