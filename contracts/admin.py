from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms import BulkChangeServiceMonthForm, BulkChangeStatusAndServiceMonthForm, BulkChangeStatusForm
from .models import Cartridge, City, ContractDevice, ContractStatus, DeviceModel, DeviceModelCartridge, Manufacturer

# ─── Справочники ────────────────────────────────────────────────────────────────


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    search_fields = ["name"]


# ─── Картриджи ──────────────────────────────────────────────────────────────────


@admin.register(Cartridge)
class CartridgeAdmin(admin.ModelAdmin):
    list_display = ("name", "part_number", "color_badge", "capacity", "is_active", "compatible_count")
    list_filter = ("is_active", "color")
    list_editable = ("is_active",)
    search_fields = ("name", "part_number", "comment")

    fieldsets = (
        ("Основная информация", {"fields": ("name", "part_number", "color", "capacity", "is_active")}),
        ("Дополнительно", {"fields": ("comment",), "classes": ("collapse",)}),
    )

    def color_badge(self, obj):
        colors = {
            "black": "#000000",
            "cyan": "#00FFFF",
            "magenta": "#FF00FF",
            "yellow": "#FFFF00",
            "color": "#808080",
            "other": "#808080",
        }
        bg_color = colors.get(obj.color, "#808080")
        text_color = "#fff" if obj.color in ("black", "magenta") else "#000"

        return format_html(
            '<span style="background-color:{}; color:{}; padding:3px 8px; border-radius:3px; font-size:0.85em;">{}</span>',
            bg_color,
            text_color,
            obj.get_color_display(),
        )

    color_badge.short_description = "Цвет"

    def compatible_count(self, obj):
        count = obj.compatible_models.count()
        if count > 0:
            return format_html('<span style="color: #28a745; font-weight: bold;">{} моделей</span>', count)
        return "—"

    compatible_count.short_description = "Совместимых моделей"


class DeviceModelCartridgeInline(admin.TabularInline):
    model = DeviceModelCartridge
    extra = 1
    fields = ("cartridge", "is_primary", "comment")
    autocomplete_fields = ("cartridge",)
    verbose_name = "Картридж"
    verbose_name_plural = "Совместимые картриджи"


@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ("manufacturer", "name", "device_type", "has_network_port_badge", "cartridges_list")
    list_filter = ("device_type", "manufacturer", "has_network_port")
    search_fields = ("name", "manufacturer__name")
    inlines = [DeviceModelCartridgeInline]  # ДОБАВЛЯЕМ ИНЛАЙН

    def has_network_port_badge(self, obj):
        if obj.has_network_port:
            return format_html('<span style="color: #28a745; font-weight: bold;">✓ Да</span>')
        return format_html('<span style="color: #6c757d;">✗ Нет</span>')

    has_network_port_badge.short_description = "Сетевой порт"
    has_network_port_badge.admin_order_field = "has_network_port"

    def cartridges_list(self, obj):
        cartridges = obj.model_cartridges.select_related("cartridge").all()
        if not cartridges:
            return format_html('<span style="color: #dc3545;">Не указаны</span>')

        items = []
        for mc in cartridges:
            style = "font-weight: bold; color: #0d6efd;" if mc.is_primary else "color: #6c757d;"
            items.append(format_html('<span style="{}">{}</span>', style, mc.cartridge.name))

        return format_html(" • ".join(items))

    cartridges_list.short_description = "Картриджи"


# ─── Статусы с цветом и флагом активности ──────────────────────────────────────


class ContractStatusForm(forms.ModelForm):
    class Meta:
        model = ContractStatus
        fields = ["name", "color", "is_active"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}


@admin.register(ContractStatus)
class ContractStatusAdmin(admin.ModelAdmin):
    form = ContractStatusForm
    list_display = ("name", "is_active", "color_swatch", "device_count")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("name",)

    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:1.4em;height:1em;'
            'border:1px solid #ccc;background:{}"></span> {}',
            obj.color,
            obj.color,
        )

    color_swatch.short_description = "Цвет"

    def device_count(self, obj):
        """Показывает количество устройств с данным статусом"""
        count = obj.devices.count()
        if count > 0:
            url = f"/admin/contracts/contractdevice/?status__id__exact={obj.id}"
            return format_html('<a href="{}">{} устройств</a>', url, count)
        return "0 устройств"

    device_count.short_description = "Устройств"


# ─── Кастомные фильтры для устройств ────────────────────────────────────────────


class StatusColorFilter(SimpleListFilter):
    """Фильтр по статусам с цветовыми индикаторами"""

    title = "статус (с цветами)"
    parameter_name = "status_colored"

    def lookups(self, request, model_admin):
        statuses = ContractStatus.objects.all().order_by("name")
        return [
            (
                status.id,
                format_html(
                    '<span style="display:inline-block;width:12px;height:12px;'
                    "background:{};border:1px solid #ccc;border-radius:2px;"
                    'margin-right:5px;"></span>{}',
                    status.color,
                    status.name,
                ),
            )
            for status in statuses
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status_id=self.value())
        return queryset


class ServiceMonthFilter(SimpleListFilter):
    """Фильтр по наличию месяца обслуживания"""

    title = "месяц обслуживания"
    parameter_name = "has_service_month"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Есть месяц обслуживания"),
            ("no", "Нет месяца обслуживания"),
            ("this_year", "Этот год"),
            ("last_year", "Прошлый год"),
        ]

    def queryset(self, request, queryset):
        from datetime import datetime

        current_year = datetime.now().year

        if self.value() == "yes":
            return queryset.filter(service_start_month__isnull=False)
        elif self.value() == "no":
            return queryset.filter(service_start_month__isnull=True)
        elif self.value() == "this_year":
            return queryset.filter(service_start_month__year=current_year)
        elif self.value() == "last_year":
            return queryset.filter(service_start_month__year=current_year - 1)
        return queryset


class OrganizationQuickFilter(SimpleListFilter):
    """Быстрый фильтр по топ организациям"""

    title = "организация (топ)"
    parameter_name = "org_quick"

    def lookups(self, request, model_admin):
        from django.db.models import Count

        # Топ-10 организаций по количеству устройств
        top_orgs = (
            ContractDevice.objects.values("organization__name", "organization_id")
            .annotate(device_count=Count("id"))
            .order_by("-device_count")[:10]
        )

        return [(org["organization_id"], f"{org['organization__name']} ({org['device_count']})") for org in top_orgs]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(organization_id=self.value())
        return queryset


# ─── Устройства по договору ────────────────────────────────────────────────────


def _contrast(hexcolor: str) -> str:
    h = (hexcolor or "").lstrip("#")
    if len(h) != 6:
        return "#fff"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return "#000" if yiq > 140 else "#fff"


@admin.register(ContractDevice)
class ContractDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "city",
        "address",
        "room_number",
        "model",
        "serial_number",
        "service_start_month_display",
        "status_badge",
        "printer",
    )

    # Улучшенные фильтры
    list_filter = (
        StatusColorFilter,  # Статус с цветами
        ServiceMonthFilter,  # Месяц обслуживания
        OrganizationQuickFilter,  # Топ организации
        "city",
        "model__manufacturer",
        "model",
        "service_start_month",  # Стандартный фильтр по дате
    )

    # Расширенный поиск
    search_fields = (
        "serial_number",
        "address",
        "room_number",
        "comment",
        "organization__name",
        "city__name",
        "model__name",
        "model__manufacturer__name",
        "status__name",  # Поиск по названию статуса!
    )

    autocomplete_fields = ("organization", "city", "model", "printer", "status")
    date_hierarchy = "service_start_month"

    # Сортировка по умолчанию - сначала без статуса, потом по статусу
    ordering = ["status__name", "organization__name"]

    # Массовые действия
    actions = ["bulk_change_status", "bulk_change_service_month", "bulk_change_status_and_service_month"]

    fieldsets = (
        ("Местоположение", {"fields": ("organization", "city", "address", "room_number")}),
        ("Оборудование", {"fields": ("model", "serial_number")}),
        ("Статус и обслуживание", {"fields": ("status", "service_start_month", "comment")}),
        ("Связи", {"fields": ("printer",), "classes": ("collapse",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-change-status/",
                self.admin_site.admin_view(self.bulk_change_status_view),
                name="contracts_contractdevice_bulk_change_status",
            ),
            path(
                "bulk-change-service-month/",
                self.admin_site.admin_view(self.bulk_change_service_month_view),
                name="contracts_contractdevice_bulk_change_service_month",
            ),
            path(
                "bulk-change-status-and-service-month/",
                self.admin_site.admin_view(self.bulk_change_status_and_service_month_view),
                name="contracts_contractdevice_bulk_change_status_and_service_month",
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        """Оптимизируем запросы"""
        return (
            super()
            .get_queryset(request)
            .select_related("organization", "city", "model__manufacturer", "status", "printer")
        )

    def status_badge(self, obj):
        if not obj.status_id:
            return "—"
        fg = _contrast(obj.status.color)
        return format_html(
            '<span class="badge" style="background:{};color:{};' 'border-radius:9999px;padding:.35em .6em;">{}</span>',
            obj.status.color,
            fg,
            obj.status.name,
        )

    status_badge.short_description = "Статус"
    status_badge.admin_order_field = "status__name"  # Возможность сортировки

    def service_start_month_display(self, obj):
        """Отображение месяца обслуживания в админке"""
        if obj.service_start_month:
            return obj.service_start_month.strftime("%m.%Y")
        return "—"

    service_start_month_display.short_description = "Месяц обслуживания"
    service_start_month_display.admin_order_field = "service_start_month"

    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику в заголовок списка"""
        extra_context = extra_context or {}

        # Статистика по статусам
        from django.db.models import Count

        status_stats = (
            ContractDevice.objects.values("status__name", "status__color")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        extra_context["status_statistics"] = status_stats
        return super().changelist_view(request, extra_context)

    # ═══ МАССОВЫЕ ДЕЙСТВИЯ ═══════════════════════════════════════════════════════

    def bulk_change_status(self, request, queryset):
        """Массовое изменение статуса"""
        selected = list(queryset.values_list("id", flat=True))
        request.session["selected_devices"] = selected
        return HttpResponseRedirect("bulk-change-status/")

    bulk_change_status.short_description = "🔄 Изменить статус выбранных устройств"

    def bulk_change_service_month(self, request, queryset):
        """Массовое изменение месяца обслуживания"""
        selected = list(queryset.values_list("id", flat=True))
        request.session["selected_devices"] = selected
        return HttpResponseRedirect("bulk-change-service-month/")

    bulk_change_service_month.short_description = "📅 Изменить месяц обслуживания выбранных устройств"

    def bulk_change_status_and_service_month(self, request, queryset):
        """Массовое изменение статуса и месяца обслуживания"""
        selected = list(queryset.values_list("id", flat=True))
        request.session["selected_devices"] = selected
        return HttpResponseRedirect("bulk-change-status-and-service-month/")

    bulk_change_status_and_service_month.short_description = (
        "🔄📅 Изменить статус и месяц обслуживания выбранных устройств"
    )

    # ═══ ПРЕДСТАВЛЕНИЯ ДЛЯ МАССОВЫХ ОПЕРАЦИЙ ════════════════════════════════════

    def bulk_change_status_view(self, request):
        """Представление для массового изменения статуса"""
        selected_ids = request.session.get("selected_devices", [])
        if not selected_ids:
            messages.error(request, "Не выбраны устройства для изменения.")
            return redirect("admin:contracts_contractdevice_changelist")

        selected_devices = ContractDevice.objects.filter(id__in=selected_ids).select_related(
            "organization", "city", "model__manufacturer", "status"
        )

        if request.method == "POST":
            form = BulkChangeStatusForm(request.POST)
            if form.is_valid():
                new_status = form.cleaned_data["new_status"]

                try:
                    with transaction.atomic():
                        updated_count = selected_devices.update(status=new_status)

                    messages.success(
                        request, f'Статус успешно изменен для {updated_count} устройств на "{new_status.name}".'
                    )
                    # Очищаем сессию
                    request.session.pop("selected_devices", None)
                    return redirect("admin:contracts_contractdevice_changelist")

                except Exception as e:
                    messages.error(request, f"Ошибка при изменении статуса: {e}")
        else:
            form = BulkChangeStatusForm()

        context = {
            "title": "Массовое изменение статуса устройств",
            "form": form,
            "selected_devices": selected_devices,
            "selected_count": len(selected_ids),
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }

        return render(request, "admin/contracts/bulk_change_status.html", context)

    def bulk_change_service_month_view(self, request):
        """Представление для массового изменения месяца обслуживания"""
        selected_ids = request.session.get("selected_devices", [])
        if not selected_ids:
            messages.error(request, "Не выбраны устройства для изменения.")
            return redirect("admin:contracts_contractdevice_changelist")

        selected_devices = ContractDevice.objects.filter(id__in=selected_ids).select_related(
            "organization", "city", "model__manufacturer", "status"
        )

        if request.method == "POST":
            form = BulkChangeServiceMonthForm(request.POST)
            if form.is_valid():
                clear_month = form.cleaned_data["clear_service_month"]
                new_month = form.cleaned_data["new_service_month"]

                try:
                    with transaction.atomic():
                        if clear_month:
                            updated_count = selected_devices.update(service_start_month=None)
                            action_text = "очищен"
                        else:
                            updated_count = selected_devices.update(service_start_month=new_month)
                            action_text = f'установлен на "{new_month.strftime("%m.%Y")}"'

                    messages.success(request, f"Месяц обслуживания {action_text} для {updated_count} устройств.")
                    # Очищаем сессию
                    request.session.pop("selected_devices", None)
                    return redirect("admin:contracts_contractdevice_changelist")

                except Exception as e:
                    messages.error(request, f"Ошибка при изменении месяца обслуживания: {e}")
        else:
            form = BulkChangeServiceMonthForm()

        context = {
            "title": "Массовое изменение месяца обслуживания",
            "form": form,
            "selected_devices": selected_devices,
            "selected_count": len(selected_ids),
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }

        return render(request, "admin/contracts/bulk_change_service_month.html", context)

    def bulk_change_status_and_service_month_view(self, request):
        """Представление для одновременного изменения статуса и месяца обслуживания"""
        selected_ids = request.session.get("selected_devices", [])
        if not selected_ids:
            messages.error(request, "Не выбраны устройства для изменения.")
            return redirect("admin:contracts_contractdevice_changelist")

        selected_devices = ContractDevice.objects.filter(id__in=selected_ids).select_related(
            "organization", "city", "model__manufacturer", "status"
        )

        if request.method == "POST":
            form = BulkChangeStatusAndServiceMonthForm(request.POST)
            if form.is_valid():
                new_status = form.cleaned_data["new_status"]
                clear_month = form.cleaned_data["clear_service_month"]
                new_month = form.cleaned_data["new_service_month"]

                try:
                    with transaction.atomic():
                        updates = {}
                        actions = []

                        if new_status:
                            updates["status"] = new_status
                            actions.append(f'статус на "{new_status.name}"')

                        if clear_month:
                            updates["service_start_month"] = None
                            actions.append("месяц обслуживания очищен")
                        elif new_month:
                            updates["service_start_month"] = new_month
                            actions.append(f'месяц обслуживания на "{new_month.strftime("%m.%Y")}"')

                        updated_count = selected_devices.update(**updates)

                    action_text = ", ".join(actions)
                    messages.success(request, f"Для {updated_count} устройств изменено: {action_text}.")
                    # Очищаем сессию
                    request.session.pop("selected_devices", None)
                    return redirect("admin:contracts_contractdevice_changelist")

                except Exception as e:
                    messages.error(request, f"Ошибка при массовом изменении: {e}")
        else:
            form = BulkChangeStatusAndServiceMonthForm()

        context = {
            "title": "Массовое изменение статуса и месяца обслуживания",
            "form": form,
            "selected_devices": selected_devices,
            "selected_count": len(selected_ids),
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }

        return render(request, "admin/contracts/bulk_change_status_and_service_month.html", context)
