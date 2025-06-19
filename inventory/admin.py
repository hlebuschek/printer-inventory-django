from django.contrib import admin
from .models import Printer, InventoryTask, PageCounter


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'serial_number', 'model', 'last_updated')
    search_fields = ('ip_address', 'serial_number', 'model')


@admin.register(InventoryTask)
class InventoryTaskAdmin(admin.ModelAdmin):
    list_display = ('printer', 'task_timestamp', 'status', 'error_message')
    list_filter = ('status', 'task_timestamp', 'printer')
    search_fields = ('printer__ip_address', 'printer__serial_number')


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
    search_fields = ('task__printer__ip_address', 'task__printer__serial_number')