from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json


class SettingCategory(models.TextChoices):
    """Категории настроек"""
    KEYCLOAK = 'keycloak', 'Keycloak / OIDC'
    GLPI = 'glpi', 'GLPI Agent'
    REDIS = 'redis', 'Redis'
    CELERY = 'celery', 'Celery'
    SYSTEM = 'system', 'Системные'
    EMAIL = 'email', 'Email'


class SettingType(models.TextChoices):
    """Типы значений настроек"""
    STRING = 'string', 'Строка'
    INTEGER = 'integer', 'Целое число'
    BOOLEAN = 'boolean', 'Да/Нет'
    TEXT = 'text', 'Текст (многострочный)'
    PASSWORD = 'password', 'Пароль'
    URL = 'url', 'URL'
    JSON = 'json', 'JSON'


class AppSetting(models.Model):
    """
    Динамические настройки приложения.
    Значения кэшируются в Redis для быстрого доступа.
    """
    key = models.CharField(
        'Ключ',
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Уникальный ключ настройки (например: KEYCLOAK_SERVER_URL)'
    )

    value = models.TextField(
        'Значение',
        blank=True,
        help_text='Значение настройки'
    )

    category = models.CharField(
        'Категория',
        max_length=20,
        choices=SettingCategory.choices,
        default=SettingCategory.SYSTEM,
        db_index=True
    )

    setting_type = models.CharField(
        'Тип',
        max_length=20,
        choices=SettingType.choices,
        default=SettingType.STRING
    )

    description = models.TextField(
        'Описание',
        blank=True,
        help_text='Описание назначения настройки'
    )

    default_value = models.TextField(
        'Значение по умолчанию',
        blank=True,
        help_text='Значение, используемое если настройка не задана'
    )

    is_active = models.BooleanField(
        'Активна',
        default=True,
        help_text='Использовать эту настройку вместо .env'
    )

    is_secret = models.BooleanField(
        'Секретная',
        default=False,
        help_text='Не показывать значение в админке'
    )

    requires_restart = models.BooleanField(
        'Требует перезапуска',
        default=False,
        help_text='Изменение требует перезапуска сервера'
    )

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Кто обновил'
    )

    class Meta:
        verbose_name = 'Настройка приложения'
        verbose_name_plural = 'Настройки приложения'
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f"{self.key} ({self.get_category_display()})"

    def clean(self):
        """Валидация значения в зависимости от типа"""
        if not self.value and not self.default_value:
            return

        value_to_check = self.value or self.default_value

        try:
            if self.setting_type == SettingType.INTEGER:
                int(value_to_check)
            elif self.setting_type == SettingType.BOOLEAN:
                if value_to_check.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                    raise ValidationError('Допустимые значения: true/false, yes/no, 1/0')
            elif self.setting_type == SettingType.JSON:
                json.loads(value_to_check)
            elif self.setting_type == SettingType.URL:
                from django.core.validators import URLValidator
                validator = URLValidator()
                validator(value_to_check)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValidationError(f'Некорректное значение для типа {self.get_setting_type_display()}: {e}')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Сбрасываем кэш при сохранении
        self.clear_cache()

    def delete(self, *args, **kwargs):
        self.clear_cache()
        super().delete(*args, **kwargs)

    def clear_cache(self):
        """Очистка кэша настройки"""
        cache_key = f'app_setting_{self.key}'
        cache.delete(cache_key)
        # Также очищаем общий кэш всех настроек
        cache.delete('app_settings_all')

    def get_value(self):
        """Получить типизированное значение"""
        val = self.value if self.value else self.default_value

        if not val:
            return None

        if self.setting_type == SettingType.INTEGER:
            return int(val)
        elif self.setting_type == SettingType.BOOLEAN:
            return val.lower() in ('true', '1', 'yes')
        elif self.setting_type == SettingType.JSON:
            return json.loads(val)
        else:
            return val

    @classmethod
    def get(cls, key, default=None, use_cache=True):
        """
        Получить значение настройки по ключу.

        Args:
            key: Ключ настройки
            default: Значение по умолчанию
            use_cache: Использовать кэш Redis
        """
        cache_key = f'app_setting_{key}'

        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            setting = cls.objects.get(key=key, is_active=True)
            value = setting.get_value()

            if use_cache:
                # Кэшируем на 15 минут
                cache.set(cache_key, value, 60 * 15)

            return value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_all(cls, category=None, use_cache=True):
        """
        Получить все настройки или по категории.

        Returns:
            dict: {key: value}
        """
        cache_key = f'app_settings_all_{category}' if category else 'app_settings_all'

        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        qs = cls.objects.filter(is_active=True)
        if category:
            qs = qs.filter(category=category)

        settings_dict = {s.key: s.get_value() for s in qs}

        if use_cache:
            cache.set(cache_key, settings_dict, 60 * 15)

        return settings_dict

    @classmethod
    def clear_all_cache(cls):
        """Очистить весь кэш настроек"""
        # Получаем все ключи настроек
        for setting in cls.objects.all():
            setting.clear_cache()


class SettingHistory(models.Model):
    """История изменений настроек"""
    setting = models.ForeignKey(
        AppSetting,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Настройка'
    )
    old_value = models.TextField('Старое значение', blank=True)
    new_value = models.TextField('Новое значение', blank=True)
    changed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Кто изменил'
    )
    changed_at = models.DateTimeField('Когда изменено', auto_now_add=True)
    comment = models.TextField('Комментарий', blank=True)

    class Meta:
        verbose_name = 'История изменения настройки'
        verbose_name_plural = 'История изменений настроек'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.setting.key} - {self.changed_at.strftime('%Y-%m-%d %H:%M:%S')}"