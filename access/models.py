from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class EntityChangeLog(models.Model):
    """
    Универсальный лог изменений для любых моделей.
    Логирует создание, изменение и удаление записей.
    """

    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('update', 'Изменение'),
        ('delete', 'Удаление'),
    ]

    # Связь с любой моделью через GenericForeignKey
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Тип объекта"
    )
    object_id = models.PositiveIntegerField(verbose_name="ID объекта")
    content_object = GenericForeignKey('content_type', 'object_id')

    # Информация о действии
    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        verbose_name="Действие"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пользователь"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Время"
    )

    # Данные об изменениях
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Изменения",
        help_text="Словарь {поле: {old: старое, new: новое}}"
    )
    object_repr = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Представление объекта",
        help_text="Строковое представление объекта на момент изменения"
    )

    # Метаданные запроса
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="User Agent"
    )

    class Meta:
        verbose_name = "Лог изменений"
        verbose_name_plural = "Логи изменений"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        action_display = dict(self.ACTION_CHOICES).get(self.action, self.action)
        user_str = self.user.username if self.user else 'Система'
        return f"{action_display}: {self.object_repr} ({user_str}, {self.timestamp.strftime('%d.%m.%Y %H:%M')})"

    def get_changes_display(self):
        """Форматирует изменения для отображения"""
        if not self.changes:
            return []

        result = []
        for field, values in self.changes.items():
            old_val = values.get('old', '—')
            new_val = values.get('new', '—')
            field_label = values.get('label', field)
            result.append({
                'field': field,
                'label': field_label,
                'old': old_val if old_val not in (None, '') else '—',
                'new': new_val if new_val not in (None, '') else '—',
            })
        return result


class ChangeLogAccess(models.Model):
    """Proxy модель для управления правами доступа к истории изменений"""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_entity_changes", "Просмотр истории изменений"),
        ]
        app_label = "access"


class AllowedUser(models.Model):
    """Whitelist разрешенных пользователей для Keycloak"""
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Логин пользователя",
        help_text="Точное совпадение с preferred_username из Keycloak"
    )
    email = models.EmailField(
        blank=True,
        verbose_name="Email (опционально)",
        help_text="Для справки, не используется при проверке"
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ФИО (опционально)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Можно временно отключить доступ без удаления"
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Добавлен"
    )
    added_by = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Добавил"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )

    class Meta:
        verbose_name = "Разрешенный пользователь"
        verbose_name_plural = "Разрешенные пользователи"
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({'активен' if self.is_active else 'отключен'})"


class UserThemePreference(models.Model):
    """Хранит настройки темы пользователя для синхронизации между устройствами"""

    THEME_CHOICES = [
        ('light', 'Светлая'),
        ('dark', 'Тёмная'),
        ('system', 'Системная'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='theme_preference',
        verbose_name="Пользователь"
    )
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='light',
        verbose_name="Тема"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )

    class Meta:
        verbose_name = "Настройки темы пользователя"
        verbose_name_plural = "Настройки тем пользователей"

    def __str__(self):
        return f"{self.user.username}: {self.get_theme_display()}"
