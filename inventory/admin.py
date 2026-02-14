from django.contrib import admin
from django.utils.html import format_html
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from .models import Printer, InventoryTask, PageCounter, Organization, WebParsingRule, WebParsingTemplate, PrinterChangeLog


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = (
        'ip_address',
        'serial_number',
        'device_model_display',
        'model_text',
        'mac_address',
        'organization',
        'polling_method_display',
        'web_parsing_rules_count',
        'last_match_rule',
        'is_active_display',
        'last_updated'
    )
    list_filter = (
        'is_active',
        'organization',
        'last_match_rule',
        'polling_method',
        'device_model',
        'device_model__manufacturer',
    )
    search_fields = (
        'ip_address',
        'serial_number',
        'model',
        'mac_address',
        'organization__name',
        'device_model__name',
        'device_model__manufacturer__name',
    )
    autocomplete_fields = ('organization', 'device_model')
    list_select_related = ('organization', 'device_model', 'device_model__manufacturer')
    ordering = ('ip_address',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('ip_address', 'serial_number', 'mac_address')
        }),
        ('Модель устройства', {
            'fields': ('device_model', 'model'),
            'description': (
                '<strong>device_model</strong> — актуальная модель из справочника (используйте это поле)<br>'
                '<strong>model</strong> — устаревшее текстовое поле (оставлено для совместимости)'
            )
        }),
        ('Метод опроса', {
            'fields': ('polling_method', 'snmp_community', 'web_username', 'web_password'),
            'description': 'Выберите метод опроса: SNMP или веб-парсинг'
        }),
        ('Организация и настройки', {
            'fields': ('organization', 'last_match_rule')
        }),
        ('Статус и замена', {
            'fields': ('is_active', 'replaced_at', 'replaced_by'),
            'classes': ('collapse',),
            'description': 'Статус активности и информация о замене оборудования'
        }),
        ('Служебная информация', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('last_updated', 'replaced_at')

    def device_model_display(self, obj):
        """Отображение модели из справочника с цветовым кодированием"""
        if obj.device_model:
            return format_html(
                '<span style="color: green; font-weight: bold;" title="Модель из справочника">{}</span>',
                obj.device_model
            )
        return format_html(
            '<span style="color: orange;" title="Модель не привязана к справочнику">—</span>'
        )

    device_model_display.short_description = 'Модель (справочник)'
    device_model_display.admin_order_field = 'device_model__name'

    def model_text(self, obj):
        """Отображение старого текстового поля"""
        if obj.model:
            if obj.device_model and obj.model.strip() == obj.device_model.name:
                return format_html(
                    '<span style="color: gray; font-style: italic;" title="Совпадает со справочником">{}</span>',
                    obj.model
                )
            else:
                return format_html(
                    '<span style="color: red;" title="Не совпадает со справочником или модель не привязана">{}</span>',
                    obj.model
                )
        return format_html('<span style="color: lightgray;">—</span>')

    model_text.short_description = 'Модель (текст, устарело)'
    model_text.admin_order_field = 'model'

    def polling_method_display(self, obj):
        """Отображение метода опроса с иконками"""
        if obj.polling_method == 'WEB':
            return format_html(
                '<span style="color: #17a2b8;" title="Веб-парсинг">Web</span>'
            )
        return format_html(
            '<span style="color: #6c757d;" title="SNMP опрос">SNMP</span>'
        )

    polling_method_display.short_description = 'Метод опроса'
    polling_method_display.admin_order_field = 'polling_method'

    def web_parsing_rules_count(self, obj):
        """Количество правил веб-парсинга"""
        count = obj.web_parsing_rules.count()
        if count > 0:
            return format_html(
                '<a href="/admin/inventory/webparsingrule/?printer__id__exact={}" style="color: #28a745; font-weight: bold;" title="Просмотреть правила">{} правил(а)</a>',
                obj.id,
                count
            )
        return format_html('<span style="color: #6c757d;">—</span>')

    web_parsing_rules_count.short_description = 'Правила парсинга'

    def is_active_display(self, obj):
        """Отображение статуса активности"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745;" title="Активный принтер">✓</span>'
            )
        replaced_info = ""
        if obj.replaced_by:
            replaced_info = f" → {obj.replaced_by.ip_address}"
        return format_html(
            '<span style="color: #dc3545;" title="Неактивный (заменён{})">✗</span>',
            replaced_info
        )

    is_active_display.short_description = 'Активен'
    is_active_display.admin_order_field = 'is_active'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
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

        if db_field.name == 'device_model':
            from contracts.models import DeviceModel
            kwargs['queryset'] = DeviceModel.objects.select_related('manufacturer').order_by(
                'manufacturer__name', 'name'
            )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        """Оптимизируем запросы"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'organization',
            'device_model',
            'device_model__manufacturer'
        ).prefetch_related('web_parsing_rules')


# ═══════════════════════════════════════════════════════════════════════════
# ПРАВИЛА ВЕБ-ПАРСИНГА
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(WebParsingRule)
class WebParsingRuleAdmin(admin.ModelAdmin):
    list_display = (
        'printer_info',
        'field_name_display',
        'rule_type_display',
        'url_display',
        'xpath_preview',
        'created_at'
    )
    list_filter = (
        'field_name',
        'is_calculated',
        'protocol',
        'printer__device_model',
        'created_at'
    )
    search_fields = (
        'printer__ip_address',
        'printer__serial_number',
        'field_name',
        'xpath',
        'url_path'
    )
    list_select_related = ('printer', 'printer__device_model')
    ordering = ('printer', 'field_name')

    fieldsets = (
        ('Основная информация', {
            'fields': ('printer', 'field_name', 'is_calculated')
        }),
        ('URL и протокол', {
            'fields': ('protocol', 'url_path'),
            'classes': ('collapse',)
        }),
        ('Обычное правило', {
            'fields': ('xpath', 'regex_pattern', 'regex_replacement', 'actions_chain'),
            'classes': ('collapse',),
            'description': 'Для обычных правил парсинга'
        }),
        ('Вычисляемое поле', {
            'fields': ('source_rules', 'calculation_formula'),
            'classes': ('collapse',),
            'description': 'Для вычисляемых полей'
        }),
        ('Служебная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('created_at',)

    def printer_info(self, obj):
        """Информация о принтере"""
        return format_html(
            '<strong>{}</strong><br><small style="color: #6c757d;">{}</small>',
            obj.printer.ip_address,
            obj.printer.device_model or 'Без модели'
        )

    printer_info.short_description = 'Принтер'

    def field_name_display(self, obj):
        """Красивое отображение имени поля"""
        field_labels = {
            'counter': 'Общий счетчик',
            'counter_a4_bw': 'ЧБ A4',
            'counter_a3_bw': 'ЧБ A3',
            'counter_a4_color': 'Цвет A4',
            'counter_a3_color': 'Цвет A3',
            'serial_number': 'Серийный номер',
            'mac_address': 'MAC-адрес',
            'toner_black': 'Тонер Black',
            'toner_cyan': 'Тонер Cyan',
            'toner_magenta': 'Тонер Magenta',
            'toner_yellow': 'Тонер Yellow',
            'drum_black': 'Барабан Black',
            'drum_cyan': 'Барабан Cyan',
            'drum_magenta': 'Барабан Magenta',
            'drum_yellow': 'Барабан Yellow',
        }
        return field_labels.get(obj.field_name, obj.field_name)

    field_name_display.short_description = 'Поле'

    def rule_type_display(self, obj):
        """Тип правила"""
        if obj.is_calculated:
            return format_html(
                '<span style="background: #ffc107; color: #000; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">ВЫЧИСЛЯЕМОЕ</span>'
            )
        return format_html(
            '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">ПАРСИНГ</span>'
        )

    rule_type_display.short_description = 'Тип'

    def url_display(self, obj):
        """Полный URL"""
        if obj.is_calculated:
            return format_html('<span style="color: #6c757d;">—</span>')
        url = f"{obj.protocol}://{obj.printer.ip_address}{obj.url_path}"
        return format_html(
            '<a href="{}" target="_blank" style="font-size: 11px;">{}</a>',
            url,
            url[:50] + '...' if len(url) > 50 else url
        )

    url_display.short_description = 'URL'

    def xpath_preview(self, obj):
        """Превью XPath"""
        if obj.is_calculated:
            return format_html(
                '<code style="font-size: 10px; color: #6c757d;">{}</code>',
                obj.calculation_formula[:40] + '...' if len(obj.calculation_formula or '') > 40 else obj.calculation_formula
            )
        if obj.xpath:
            return format_html(
                '<code style="font-size: 10px;">{}</code>',
                obj.xpath[:40] + '...' if len(obj.xpath) > 40 else obj.xpath
            )
        return format_html('<span style="color: #6c757d;">—</span>')

    xpath_preview.short_description = 'XPath / Формула'


# ═══════════════════════════════════════════════════════════════════════════
# ШАБЛОНЫ ВЕБ-ПАРСИНГА
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(WebParsingTemplate)
class WebParsingTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name_display',
        'device_model',
        'rules_count_display',
        'usage_display',
        'visibility_display',
        'created_by',
        'created_at'
    )
    list_filter = (
        'is_public',
        'device_model__manufacturer',
        'device_model',
        'created_at',
        'created_by'
    )
    search_fields = (
        'name',
        'description',
        'device_model__name',
        'device_model__manufacturer__name',
        'created_by__username'
    )
    list_select_related = ('device_model', 'device_model__manufacturer', 'created_by')
    ordering = ('-created_at',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'device_model', 'description')
        }),
        ('Конфигурация правил', {
            'fields': ('rules_config',),
            'description': 'JSON конфигурация правил парсинга'
        }),
        ('Доступ и статистика', {
            'fields': ('is_public', 'usage_count', 'created_by'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('created_at', 'updated_at', 'usage_count')

    def name_display(self, obj):
        """Название с иконкой"""
        icon = '' if obj.is_public else ''
        return format_html(
            '{} <strong>{}</strong>',
            icon,
            obj.name
        )

    name_display.short_description = 'Название'
    name_display.admin_order_field = 'name'

    def rules_count_display(self, obj):
        """Количество правил в шаблоне"""
        try:
            count = len(obj.rules_config)
            calculated = sum(1 for r in obj.rules_config if r.get('is_calculated'))
            normal = count - calculated

            if calculated > 0:
                return format_html(
                    '<span style="color: #28a745; font-weight: bold;">{}</span> '
                    '<small style="color: #6c757d;">({} обычных, {} вычисляемых)</small>',
                    count,
                    normal,
                    calculated
                )
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{}</span> правил(а)',
                count
            )
        except:
            return format_html('<span style="color: #dc3545;">Ошибка</span>')

    rules_count_display.short_description = 'Правил'

    def usage_display(self, obj):
        """Статистика использования"""
        if obj.usage_count > 0:
            return format_html(
                '<span style="color: #007bff; font-weight: bold;" title="Применен {} раз">{}</span>',
                obj.usage_count,
                obj.usage_count
            )
        return format_html('<span style="color: #6c757d;">—</span>')

    usage_display.short_description = 'Использований'
    usage_display.admin_order_field = 'usage_count'

    def visibility_display(self, obj):
        """Видимость шаблона"""
        if obj.is_public:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">ПУБЛИЧНЫЙ</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">ПРИВАТНЫЙ</span>'
        )

    visibility_display.short_description = 'Видимость'
    visibility_display.admin_order_field = 'is_public'

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя"""
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ═══════════════════════════════════════════════════════════════════════════
# ОСТАЛЬНЫЕ АДМИНКИ (БЕЗ ИЗМЕНЕНИЙ)
# ═══════════════════════════════════════════════════════════════════════════

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
    list_filter = ('status', HistoricalInconsistencyFilter, 'match_rule', 'task_timestamp')
    search_fields = ('printer__ip_address', 'printer__serial_number', 'printer__mac_address')
    date_hierarchy = 'task_timestamp'
    list_select_related = ('printer',)

    # Оптимизация для редактирования задачи с большим количеством принтеров
    autocomplete_fields = ('printer',)

    # Ограничиваем количество записей на странице
    list_per_page = 100

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


@admin.register(PrinterChangeLog)
class PrinterChangeLogAdmin(admin.ModelAdmin):
    """Админка для логов изменений принтеров (замена, смена IP)"""
    list_display = (
        'printer_info',
        'action_display',
        'timestamp',
        'changes_summary',
        'related_printer_info',
        'triggered_by_display'
    )
    list_filter = (
        'action',
        'triggered_by',
        'timestamp',
        'printer__organization',
    )
    search_fields = (
        'printer__ip_address',
        'printer__serial_number',
        'related_printer__ip_address',
        'related_printer__serial_number',
        'comment',
    )
    list_select_related = (
        'printer',
        'printer__organization',
        'related_printer',
    )
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    list_per_page = 50

    fieldsets = (
        ('Основная информация', {
            'fields': ('printer', 'action', 'triggered_by', 'timestamp')
        }),
        ('Изменения', {
            'fields': ('old_values', 'new_values', 'comment')
        }),
        ('Связанный принтер', {
            'fields': ('related_printer',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('timestamp',)

    def printer_info(self, obj):
        """Информация о принтере"""
        status = "✓" if obj.printer.is_active else "✗"
        return format_html(
            '<span title="{}">{}</span> <strong>{}</strong><br><small style="color: #6c757d;">SN: {}</small>',
            'Активен' if obj.printer.is_active else 'Неактивен',
            status,
            obj.printer.ip_address,
            obj.printer.serial_number or '—'
        )

    printer_info.short_description = 'Принтер'

    def action_display(self, obj):
        """Красивое отображение действия"""
        colors = {
            'ip_change': '#17a2b8',
            'serial_update': '#ffc107',
            'mac_update': '#6f42c1',
            'deactivation': '#dc3545',
            'replacement': '#28a745',
            'activation': '#007bff',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_action_display()
        )

    action_display.short_description = 'Действие'
    action_display.admin_order_field = 'action'

    def changes_summary(self, obj):
        """Краткое описание изменений"""
        if obj.comment:
            return obj.comment[:60] + '...' if len(obj.comment) > 60 else obj.comment

        changes = []
        if obj.old_values.get('ip_address') and obj.new_values.get('ip_address'):
            changes.append(f"IP: {obj.old_values['ip_address']} → {obj.new_values['ip_address']}")
        if obj.old_values.get('serial_number') and obj.new_values.get('serial_number'):
            changes.append(f"SN: {obj.old_values['serial_number']} → {obj.new_values['serial_number']}")

        return ', '.join(changes) if changes else '—'

    changes_summary.short_description = 'Изменения'

    def related_printer_info(self, obj):
        """Информация о связанном принтере"""
        if not obj.related_printer:
            return format_html('<span style="color: #6c757d;">—</span>')

        status = "✓" if obj.related_printer.is_active else "✗"
        return format_html(
            '<span title="{}">{}</span> {}<br><small style="color: #6c757d;">SN: {}</small>',
            'Активен' if obj.related_printer.is_active else 'Неактивен',
            status,
            obj.related_printer.ip_address,
            obj.related_printer.serial_number or '—'
        )

    related_printer_info.short_description = 'Связанный принтер'

    def triggered_by_display(self, obj):
        """Источник изменения"""
        if obj.triggered_by == 'auto_poll':
            return format_html(
                '<span style="color: #17a2b8;" title="Автоматический опрос">⚙ Авто</span>'
            )
        return format_html(
            '<span style="color: #28a745;" title="Ручное изменение">👤 Вручную</span>'
        )

    triggered_by_display.short_description = 'Источник'


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

    # КРИТИЧНО ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ:
    # Используем raw_id_fields чтобы не загружать все InventoryTask в dropdown
    # При большом количестве задач (100k+) dropdown убивает производительность
    raw_id_fields = ('task',)

    # Ограничиваем количество записей на странице для ускорения загрузки
    list_per_page = 50