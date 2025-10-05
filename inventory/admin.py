from django.contrib import admin
from django.utils.html import format_html
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from .models import Printer, InventoryTask, PageCounter, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'serial_number', 'model', 'mac_address',
                    'organization', 'last_match_rule', 'last_updated')
    list_filter = ('organization', 'last_match_rule')
    search_fields = ('ip_address', 'serial_number', 'model', 'mac_address', 'organization__name')
    autocomplete_fields = ('organization',)
    list_select_related = ('organization',)
    ordering = ('ip_address',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Показываем только активные организации и отключаем «плюсики»
        if db_field.name == 'organization':
            kwargs['queryset'] = Organization.objects.filter(active=True).order_by('name')
            field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            if hasattr(field.widget, 'can_add_related'):
                field.widget.can_add_related = False
            if hasattr(field.widget, 'can_change_related'):
                field.widget.can_change_related = False
            if hasattr(field.widget, 'can_delete_related'):
                field.widget.can_delete_related = False
            return field
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HistoricalInconsistencyFilter(admin.SimpleListFilter):
    title = 'Исторические несоответствия'
    parameter_name = 'historical'

    def lookups(self, request, model_admin):
        return (
            ('recent', 'За последний день'),
            ('week', 'За последнюю неделю'),
            ('month', 'За последний месяц'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'recent':
            return queryset.filter(
                status='HISTORICAL_INCONSISTENCY',
                task_timestamp__gte=timezone.now() - timedelta(days=1)
            )
        elif self.value() == 'week':
            return queryset.filter(
                status='HISTORICAL_INCONSISTENCY',
                task_timestamp__gte=timezone.now() - timedelta(weeks=1)
            )
        elif self.value() == 'month':
            return queryset.filter(
                status='HISTORICAL_INCONSISTENCY',
                task_timestamp__gte=timezone.now() - timedelta(days=30)
            )
        return queryset


@admin.register(InventoryTask)
class InventoryTaskAdmin(admin.ModelAdmin):
    list_display = ('printer', 'task_timestamp', 'colored_status', 'match_rule', 'short_error')
    list_filter = ('status', HistoricalInconsistencyFilter, 'match_rule', 'task_timestamp', 'printer')
    search_fields = ('printer__ip_address', 'printer__serial_number', 'printer__mac_address')
    date_hierarchy = 'task_timestamp'
    list_select_related = ('printer',)

    def colored_status(self, obj):
        colors = {
            'SUCCESS': 'green',
            'FAILED': 'red',
            'VALIDATION_ERROR': 'orange',
            'HISTORICAL_INCONSISTENCY': 'purple',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )

    colored_status.short_description = 'Статус'
    colored_status.admin_order_field = 'status'

    def short_error(self, obj):
        if not obj.error_message:
            return ''
        msg = obj.error_message
        return (msg[:80] + '…') if len(msg) > 80 else msg

    short_error.short_description = "Ошибка"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        # Статистика по статусам
        status_stats = InventoryTask.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')

        extra_context['status_stats'] = status_stats
        return super().changelist_view(request, extra_context)


@admin.register(PageCounter)
class PageCounterAdmin(admin.ModelAdmin):
    list_display = (
        'task', 'recorded_at',
        'bw_a3', 'bw_a4', 'color_a3', 'color_a4', 'total_pages',
        'drum_black', 'drum_cyan', 'drum_magenta', 'drum_yellow',
        'toner_black', 'toner_cyan', 'toner_magenta', 'toner_yellow',
        'fuser_kit', 'transfer_kit', 'waste_toner',
    )
    list_filter = ('recorded_at', 'task__printer', 'task__printer__organization')
    search_fields = ('task__printer__ip_address', 'task__printer__serial_number', 'task__printer__mac_address')
    list_select_related = ('task', 'task__printer')