from django.contrib import admin

from .models import ReportGroup, ReportGroupItem


class ReportGroupItemInline(admin.TabularInline):
    model = ReportGroupItem
    extra = 0
    fields = ("sort_order", "printer", "location", "additional_info")
    autocomplete_fields = ("printer",)


@admin.register(ReportGroup)
class ReportGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "location_label", "is_active", "stale_threshold_hours", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "location_label", "to_emails", "cc_emails")
    inlines = [ReportGroupItemInline]
    fieldsets = (
        (None, {"fields": ("name", "location_label", "is_active")}),
        (
            "Письмо",
            {
                "fields": (
                    "subject_template",
                    "body_intro",
                    "body_signature",
                    "from_email",
                    "to_emails",
                    "cc_emails",
                )
            },
        ),
        ("Данные", {"fields": ("stale_threshold_hours",)}),
        (
            "Автоотправка по расписанию",
            {
                "fields": (
                    "auto_send_enabled",
                    "auto_send_time",
                    "auto_send_weekdays",
                    "last_sent_at",
                    "last_send_error",
                ),
            },
        ),
    )
    readonly_fields = ("last_sent_at", "last_send_error")


@admin.register(ReportGroupItem)
class ReportGroupItemAdmin(admin.ModelAdmin):
    list_display = ("group", "sort_order", "printer", "location", "additional_info")
    list_filter = ("group",)
    search_fields = ("printer__ip_address", "printer__serial_number", "location", "additional_info")
    autocomplete_fields = ("printer",)
    ordering = ("group", "sort_order")
