from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AppSetting, SettingHistory, SettingCategory


class SettingHistoryInline(admin.TabularInline):
    model = SettingHistory
    extra = 0
    can_delete = False
    readonly_fields = ['old_value', 'new_value', 'changed_by', 'changed_at', 'comment']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = [
        'key', 'category_badge', 'type_badge', 'value_preview',
        'is_active', 'requires_restart_badge', 'updated_at'
    ]
    list_filter = ['category', 'setting_type', 'is_active', 'requires_restart', 'is_secret']
    search_fields = ['key', 'description', 'value']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
    inlines = [SettingHistoryInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('key', 'category', 'setting_type', 'description')
        }),
        ('Значение', {
            'fields': ('value', 'default_value')
        }),
        ('Настройки', {
            'fields': ('is_active', 'is_secret', 'requires_restart')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def category_badge(self, obj):
        colors = {
            'keycloak': 'primary',
            'glpi': 'success',
            'redis': 'danger',
            'celery': 'warning',
            'system': 'secondary',
            'email': 'info',
        }
        color = colors.get(obj.category, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_category_display()
        )

    category_badge.short_description = 'Категория'

    def type_badge(self, obj):
        return format_html(
            '<span class="badge bg-light text-dark">{}</span>',
            obj.get_setting_type_display()
        )

    type_badge.short_description = 'Тип'

    def value_preview(self, obj):
        if obj.is_secret:
            return format_html('<i class="text-muted">● ● ● ● ● ● ● ●</i>')

        value = obj.value or obj.default_value
        if not value:
            return format_html('<i class="text-muted">Не задано</i>')

        if len(value) > 50:
            return format_html(
                '<span title="{}">{}</span>',
                value,
                value[:47] + '...'
            )
        return value

    value_preview.short_description = 'Значение'

    def requires_restart_badge(self, obj):
        if obj.requires_restart:
            return format_html(
                '<span class="badge bg-warning">⚠️ Требует перезапуска</span>'
            )
        return ''

    requires_restart_badge.short_description = 'Перезапуск'

    def save_model(self, request, obj, form, change):
        # Сохраняем историю
        if change:
            try:
                old_obj = AppSetting.objects.get(pk=obj.pk)
                if old_obj.value != obj.value:
                    SettingHistory.objects.create(
                        setting=obj,
                        old_value=old_obj.value,
                        new_value=obj.value,
                        changed_by=request.user,
                        comment=f'Изменено через админку'
                    )
            except AppSetting.DoesNotExist:
                pass

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['clear_cache_action', 'activate_settings', 'deactivate_settings']

    def clear_cache_action(self, request, queryset):
        for setting in queryset:
            setting.clear_cache()
        self.message_user(request, f'Кэш очищен для {queryset.count()} настроек')

    clear_cache_action.short_description = 'Очистить кэш выбранных настроек'

    def activate_settings(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'Активировано {queryset.count()} настроек')

    activate_settings.short_description = 'Активировать выбранные настройки'

    def deactivate_settings(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано {queryset.count()} настроек')

    deactivate_settings.short_description = 'Деактивировать выбранные настройки'


@admin.register(SettingHistory)
class SettingHistoryAdmin(admin.ModelAdmin):
    list_display = ['setting', 'changed_by', 'changed_at', 'value_change']
    list_filter = ['changed_at', 'changed_by']
    search_fields = ['setting__key', 'old_value', 'new_value', 'comment']
    readonly_fields = ['setting', 'old_value', 'new_value', 'changed_by', 'changed_at']

    def value_change(self, obj):
        return format_html(
            '<span class="text-danger">{}</span> → <span class="text-success">{}</span>',
            obj.old_value[:50] if obj.old_value else '—',
            obj.new_value[:50] if obj.new_value else '—'
        )

    value_change.short_description = 'Изменение'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False