from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import City, Manufacturer, DeviceModel, ContractDevice, ContractStatus

# ─── Справочники ────────────────────────────────────────────────────────────────

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ["name"]

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    search_fields = ["name"]

@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ("manufacturer", "name", "device_type")
    list_filter  = ("device_type", "manufacturer")
    search_fields = ("name", "manufacturer__name")

# ─── Статусы с цветом и флагом активности ──────────────────────────────────────

class ContractStatusForm(forms.ModelForm):
    class Meta:
        model = ContractStatus
        fields = ["name", "color", "is_active"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

@admin.register(ContractStatus)
class ContractStatusAdmin(admin.ModelAdmin):
    form = ContractStatusForm
    list_display  = ("name", "is_active", "color_swatch")
    list_editable = ("is_active",)
    list_filter   = ("is_active",)
    search_fields = ("name",)

    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:1.4em;height:1em;'
            'border:1px solid #ccc;background:{}"></span> {}',
            obj.color, obj.color
        )
    color_swatch.short_description = "Цвет"

# ─── Устройства по договору ────────────────────────────────────────────────────

def _contrast(hexcolor: str) -> str:
    h = (hexcolor or "").lstrip("#")
    if len(h) != 6:
        return "#fff"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    yiq = (r*299 + g*587 + b*114) / 1000
    return "#000" if yiq > 140 else "#fff"

@admin.register(ContractDevice)
class ContractDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id", "organization", "city", "address", "room_number",
        "model", "serial_number", "status_badge", "printer",
    )
    list_filter = ("organization", "city", "model__manufacturer", "model", "status")
    search_fields = ("serial_number", "address", "room_number", "comment")
    autocomplete_fields = ("organization", "city", "model", "printer", "status")

    def status_badge(self, obj):
        if not obj.status_id:
            return "—"
        fg = _contrast(obj.status.color)
        return format_html(
            '<span class="badge" style="background:{};color:{};'
            'border-radius:9999px;padding:.35em .6em;">{}</span>',
            obj.status.color, fg, obj.status.name
        )
    status_badge.short_description = "Статус"
