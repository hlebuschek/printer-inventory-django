from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class GLPISync(models.Model):
    """
    Лог синхронизации с GLPI.
    Хранит результаты проверки принтеров в GLPI.
    """

    STATUS_CHOICES = [
        ('NOT_FOUND', 'Не найден в GLPI'),
        ('FOUND_SINGLE', 'Найден (1 карточка)'),
        ('FOUND_MULTIPLE', 'Найдено несколько карточек'),
        ('ERROR', 'Ошибка при проверке'),
    ]

    # Связь с устройством из contracts
    contract_device = models.ForeignKey(
        'contracts.ContractDevice',
        on_delete=models.CASCADE,
        related_name='glpi_syncs',
        verbose_name='Устройство'
    )

    # Результат проверки
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name='Статус'
    )

    # Серийный номер который искали
    searched_serial = models.CharField(
        max_length=255,
        verbose_name='Искомый серийник'
    )

    # Найденные ID карточек в GLPI (JSON array)
    glpi_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name='ID в GLPI',
        help_text='Список ID найденных карточек в GLPI'
    )

    # Данные из GLPI (JSON)
    glpi_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Данные из GLPI',
        help_text='Полные данные из GLPI API'
    )

    # Состояние устройства в GLPI (states_id)
    glpi_state_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID состояния в GLPI',
        help_text='ID состояния устройства (например: в работе, сломан, в ремонте)'
    )

    glpi_state_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Состояние в GLPI',
        help_text='Название состояния устройства в GLPI'
    )

    # Сообщение об ошибке (если есть)
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Сообщение об ошибке'
    )

    # Метаданные
    checked_at = models.DateTimeField(
        default=timezone.now,  # Используем default вместо auto_now_add для возможности обновления
        verbose_name='Время проверки'
    )

    checked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Проверил'
    )

    class Meta:
        verbose_name = 'Синхронизация с GLPI'
        verbose_name_plural = 'Синхронизации с GLPI'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['contract_device', '-checked_at']),
            models.Index(fields=['status']),
            models.Index(fields=['searched_serial']),
        ]

    def __str__(self):
        return f"{self.contract_device} - {self.get_status_display()} ({self.checked_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def is_synced(self):
        """Успешно синхронизировано (найдена ровно 1 карточка)"""
        return self.status == 'FOUND_SINGLE'

    @property
    def has_conflict(self):
        """Найдено несколько карточек"""
        return self.status == 'FOUND_MULTIPLE'

    @property
    def glpi_count(self):
        """Количество найденных карточек"""
        return len(self.glpi_ids) if self.glpi_ids else 0


class IntegrationLog(models.Model):
    """
    Общий лог для всех интеграций.
    Полезен для отладки и мониторинга.
    """

    SYSTEM_CHOICES = [
        ('GLPI', 'GLPI'),
        ('OTHER', 'Другая система'),
    ]

    LEVEL_CHOICES = [
        ('DEBUG', 'Отладка'),
        ('INFO', 'Информация'),
        ('WARNING', 'Предупреждение'),
        ('ERROR', 'Ошибка'),
    ]

    system = models.CharField(
        max_length=50,
        choices=SYSTEM_CHOICES,
        verbose_name='Система'
    )

    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        default='INFO',
        verbose_name='Уровень'
    )

    message = models.TextField(
        verbose_name='Сообщение'
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Детали',
        help_text='Дополнительная информация в формате JSON'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Пользователь'
    )

    class Meta:
        verbose_name = 'Лог интеграции'
        verbose_name_plural = 'Логи интеграций'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['system', '-created_at']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        return f"[{self.system}] {self.level}: {self.message[:50]}"
