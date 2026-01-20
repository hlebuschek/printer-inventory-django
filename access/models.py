from django.db import models
from django.conf import settings


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
        default='system',
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
