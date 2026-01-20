from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.models import User
from .models import AllowedUser, UserThemePreference


@admin.register(AllowedUser)
class AllowedUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'full_name',
        'colored_status',
        'has_django_user',
        'added_at',
        'added_by'
    )
    list_filter = ('is_active', 'added_at')
    search_fields = ('username', 'email', 'full_name', 'notes')
    readonly_fields = ('added_at',)
    ordering = ('-is_active', 'username')

    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'is_active')
        }),
        ('Дополнительная информация', {
            'fields': ('email', 'full_name', 'notes')
        }),
        ('Системная информация', {
            'fields': ('added_at', 'added_by'),
            'classes': ('collapse',)
        }),
    )

    def colored_status(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Активен</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Отключен</span>'
        )

    colored_status.short_description = 'Статус'

    def has_django_user(self, obj):
        django_user = User.objects.filter(username__iexact=obj.username).first()
        if django_user:
            if django_user.is_active:
                return format_html('<span style="color: green;">✓ Да</span>')
            else:
                return format_html('<span style="color: orange;">⚠ Неактивен</span>')
        return format_html('<span style="color: gray;">✗ Нет</span>')

    has_django_user.short_description = 'Django пользователь'

    def save_model(self, request, obj, form, change):
        if not change:  # Новый объект
            obj.added_by = request.user.username
        super().save_model(request, obj, form, change)

        # Синхронизируем статус Django пользователя
        django_user = User.objects.filter(username__iexact=obj.username).first()
        if django_user and not django_user.is_superuser:
            django_user.is_active = obj.is_active
            django_user.save()

    actions = ['activate_users', 'deactivate_users']

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)

        # Активируем Django пользователей
        for allowed_user in queryset:
            django_user = User.objects.filter(
                username__iexact=allowed_user.username
            ).first()
            if django_user and not django_user.is_superuser:
                django_user.is_active = True
                django_user.save()

        self.message_user(request, f'Активировано {updated} пользователей')

    activate_users.short_description = 'Активировать выбранных пользователей'

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)

        # Деактивируем Django пользователей
        for allowed_user in queryset:
            django_user = User.objects.filter(
                username__iexact=allowed_user.username
            ).first()
            if django_user and not django_user.is_superuser:
                django_user.is_active = False
                django_user.save()

        self.message_user(request, f'Деактивировано {updated} пользователей')

    deactivate_users.short_description = 'Деактивировать выбранных пользователей'


@admin.register(UserThemePreference)
class UserThemePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'updated_at')
    list_filter = ('theme', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)
    ordering = ('-updated_at',)