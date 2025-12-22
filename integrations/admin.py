from django.contrib import admin
from django.utils.html import format_html
from .models import GLPISync, IntegrationLog


@admin.register(GLPISync)
class GLPISyncAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'contract_device_link',
        'searched_serial',
        'status_display',
        'glpi_count_display',
        'checked_at',
        'checked_by'
    )
    list_filter = ('status', 'checked_at', 'checked_by')
    search_fields = (
        'searched_serial',
        'contract_device__serial_number',
        'contract_device__model__name',
        'contract_device__organization__name'
    )
    readonly_fields = ('checked_at',)
    list_select_related = ('contract_device', 'contract_device__model', 'contract_device__organization', 'checked_by')
    date_hierarchy = 'checked_at'
    list_per_page = 50

    fieldsets = (
        ('Устройство', {
            'fields': ('contract_device', 'searched_serial')
        }),
        ('Результат проверки', {
            'fields': ('status', 'glpi_ids', 'glpi_data', 'error_message')
        }),
        ('Метаданные', {
            'fields': ('checked_at', 'checked_by'),
            'classes': ('collapse',)
        }),
    )

    def contract_device_link(self, obj):
        """Ссылка на устройство в админке contracts"""
        if obj.contract_device:
            url = f"/admin/contracts/contractdevice/{obj.contract_device.id}/change/"
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                obj.contract_device
            )
        return '—'

    contract_device_link.short_description = 'Устройство'
    contract_device_link.admin_order_field = 'contract_device'

    def status_display(self, obj):
        """Красивое отображение статуса"""
        colors = {
            'NOT_FOUND': '#6c757d',
            'FOUND_SINGLE': '#28a745',
            'FOUND_MULTIPLE': '#ffc107',
            'ERROR': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')

        icons = {
            'NOT_FOUND': '❌',
            'FOUND_SINGLE': '✅',
            'FOUND_MULTIPLE': '⚠️',
            'ERROR': '❗',
        }
        icon = icons.get(obj.status, '?')

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )

    status_display.short_description = 'Статус'
    status_display.admin_order_field = 'status'

    def glpi_count_display(self, obj):
        """Количество найденных карточек"""
        count = obj.glpi_count

        if count == 0:
            return format_html('<span style="color: #6c757d;">0</span>')
        elif count == 1:
            return format_html('<span style="color: #28a745; font-weight: bold;">1</span>')
        else:
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;">{}</span>',
                count
            )

    glpi_count_display.short_description = 'Найдено в GLPI'


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'system',
        'level_display',
        'message_short',
        'created_at',
        'user'
    )
    list_filter = ('system', 'level', 'created_at', 'user')
    search_fields = ('message', 'details')
    readonly_fields = ('created_at',)
    list_select_related = ('user',)
    date_hierarchy = 'created_at'
    list_per_page = 100

    fieldsets = (
        (None, {
            'fields': ('system', 'level', 'message', 'details')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'user'),
            'classes': ('collapse',)
        }),
    )

    def message_short(self, obj):
        """Сокращённое сообщение"""
        max_length = 100
        if len(obj.message) > max_length:
            return obj.message[:max_length] + '...'
        return obj.message

    message_short.short_description = 'Сообщение'

    def level_display(self, obj):
        """Красивое отображение уровня"""
        colors = {
            'DEBUG': '#6c757d',
            'INFO': '#0dcaf0',
            'WARNING': '#ffc107',
            'ERROR': '#dc3545',
        }
        color = colors.get(obj.level, '#6c757d')

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_level_display()
        )

    level_display.short_description = 'Уровень'
    level_display.admin_order_field = 'level'
