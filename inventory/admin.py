from django.contrib import admin
from .models import Printer, InventoryTask, PageCounter

@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'serial_number', 'model', 'last_updated')
    search_fields = ('ip_address', 'serial_number', 'model')

@admin.register(InventoryTask)
class InventoryTaskAdmin(admin.ModelAdmin):
    list_display = ('printer', 'task_timestamp', 'status')
    list_filter = ('status',)

@admin.register(PageCounter)
class PageCounterAdmin(admin.ModelAdmin):
    list_display = ('task', 'bw_a4', 'color_a4', 'bw_a3', 'color_a3', 'total_pages', 'recorded_at')
    list_filter = ('recorded_at',)
