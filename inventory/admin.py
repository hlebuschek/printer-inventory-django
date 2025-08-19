from django.contrib import admin
from .models import Printer, InventoryTask, PageCounter, Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("name",)

@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'serial_number', 'model', 'mac_address', 'organization', 'last_updated')
    list_filter = ('organization',)  # фильтр по справочнику
    search_fields = ('ip_address', 'serial_number', 'model', 'mac_address', 'organization__name')
    autocomplete_fields = ('organization',)     # выпадающий поиск вместо длинного select
    list_select_related = ('organization',)     # чтобы не ловить N+1 в списке

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # показываем только активные организации и отключаем «плюсики»
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

@admin.register(InventoryTask)
class InventoryTaskAdmin(admin.ModelAdmin):
    list_display = ('printer', 'task_timestamp', 'status', 'error_message')
    list_filter = ('status', 'task_timestamp', 'printer')
    search_fields = ('printer__ip_address', 'printer__serial_number', 'printer__mac_address')

@admin.register(PageCounter)
class PageCounterAdmin(admin.ModelAdmin):
    list_display = (
        'task', 'recorded_at',
        'bw_a3', 'bw_a4', 'color_a3', 'color_a4', 'total_pages',
        'drum_black', 'drum_cyan', 'drum_magenta', 'drum_yellow',
        'toner_black', 'toner_cyan', 'toner_magenta', 'toner_yellow',
        'fuser_kit', 'transfer_kit', 'waste_toner',
    )
    list_filter = ('recorded_at', 'task__printer')
    search_fields = ('task__printer__ip_address', 'task__printer__serial_number', 'task__printer__mac_address')
