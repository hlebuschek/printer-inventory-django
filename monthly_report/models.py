# monthly_report/models.py - обновленная версия с флагами ручного редактирования

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex
import json
from django.contrib.auth import get_user_model

User = get_user_model()


class MonthlyReport(models.Model):
    month = models.DateField(_('Месяц'), help_text='Первый день месяца (для группировки)')
    order_number = models.PositiveIntegerField(_('№ п/п'), default=1)
    organization = models.CharField(_('Организация'), max_length=255)
    branch = models.CharField(_('Филиал'), max_length=255)
    city = models.CharField(_('Город'), max_length=255)
    address = models.CharField(_('Адрес'), max_length=255)

    equipment_model = models.CharField(_('Модель и наименование оборудования'), max_length=255, db_index=True)
    serial_number = models.CharField(_('Серийный номер оборудования'), max_length=100, db_index=True)
    inventory_number = models.CharField(_('Инв номер'), max_length=100, db_index=True)

    # Основные поля счетчиков
    a4_bw_start = models.PositiveIntegerField(_('A4 ч/б начало'), default=0)
    a4_bw_end = models.PositiveIntegerField(_('A4 ч/б конец'), default=0)
    a4_color_start = models.PositiveIntegerField(_('A4 цвет начало'), default=0)
    a4_color_end = models.PositiveIntegerField(_('A4 цвет конец'), default=0)
    a3_bw_start = models.PositiveIntegerField(_('A3 ч/б начало'), default=0)
    a3_bw_end = models.PositiveIntegerField(_('A3 ч/б конец'), default=0)
    a3_color_start = models.PositiveIntegerField(_('A3 цвет начало'), default=0)
    a3_color_end = models.PositiveIntegerField(_('A3 цвет конец'), default=0)

    # total_prints вычисляется сервисом (recompute_group / recompute_month)
    # IntegerField для поддержки отрицательных значений (когда счетчик сбрасывается)
    total_prints = models.IntegerField(_('Итого отпечатков шт.'), default=0)

    normative_availability = models.FloatField(_('Нормативное время доступности (A)'), default=0.0)
    actual_downtime = models.FloatField(_('Фактическое время недоступности (D)'), default=0.0)
    k1 = models.FloatField(_('K1 = ((A - D)/A)*100%'), default=0.0)
    non_overdue_requests = models.PositiveIntegerField(_('Количество не просроченных запросов (L)'), default=0)
    total_requests = models.PositiveIntegerField(_('Общее количество запросов (W)'), default=0)
    k2 = models.FloatField(_('K2 = (L/W)*100%'), default=0.0)

    # Интеграция с inventory
    device_ip = models.GenericIPAddressField(_("IP-адрес (inventory)"), null=True, blank=True)
    inventory_last_ok = models.DateTimeField(_("Последний успешный опрос (inventory)"), null=True, blank=True)

    # Автоматически подтянутые значения из inventory (для справки)
    a4_bw_end_auto = models.PositiveIntegerField(default=0)
    a4_color_end_auto = models.PositiveIntegerField(default=0)
    a3_bw_end_auto = models.PositiveIntegerField(default=0)
    a3_color_end_auto = models.PositiveIntegerField(default=0)

    # НОВЫЕ ПОЛЯ: Флаги ручного редактирования конечных счетчиков
    # Если True, то поле не будет обновляться автоматически при синхронизации
    a4_bw_end_manual = models.BooleanField(_('A4 ч/б конец - ручное редактирование'), default=False)
    a4_color_end_manual = models.BooleanField(_('A4 цвет конец - ручное редактирование'), default=False)
    a3_bw_end_manual = models.BooleanField(_('A3 ч/б конец - ручное редактирование'), default=False)
    a3_color_end_manual = models.BooleanField(_('A3 цвет конец - ручное редактирование'), default=False)

    # когда мы последний раз авто-подливали из inventory
    inventory_autosync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['month', 'order_number']
        verbose_name = 'Ежемесячный отчёт'
        verbose_name_plural = 'Ежемесячные отчёты'
        permissions = [
            ('access_monthly_report', 'Доступ к модулю ежемесячных отчётов'),
            ('upload_monthly_report', 'Загрузка отчётов из Excel'),
            ('edit_counters_start', 'Право редактировать поля *_start'),
            ('edit_counters_end', 'Право редактировать поля *_end'),
            ('sync_from_inventory', 'Подтягивать IP/счётчики из Inventory'),
        ]
        indexes = [
            models.Index(fields=['month', 'serial_number', 'inventory_number'], name='mr_month_sn_inv'),
            models.Index(fields=['month', 'inventory_number'], name='mr_month_inv'),
            models.Index(fields=['month', '-total_prints'], name='mr_month_total_desc'),
            models.Index(fields=['month', 'order_number'], name='mr_month_ord'),
        ]

    def save(self, *args, **kwargs):
        # Не считаем total_prints здесь — его разложит сервис по группам.
        A = float(self.normative_availability or 0.0)
        D = max(0.0, float(self.actual_downtime or 0.0))
        W = int(self.total_requests or 0)
        L = int(self.non_overdue_requests or 0)

        self.k1 = ((A - D) / A * 100.0) if A > 0 else 0.0
        self.k1 = max(0.0, min(self.k1, 100.0))

        self.k2 = (L / W * 100.0) if W > 0 else 0.0
        self.k2 = max(0.0, min(self.k2, 100.0))

        super().save(*args, **kwargs)

    def is_field_manually_edited(self, field_name: str) -> bool:
        """
        Проверяет, было ли поле отредактировано вручную пользователем
        """
        manual_field_map = {
            'a4_bw_end': 'a4_bw_end_manual',
            'a4_color_end': 'a4_color_end_manual',
            'a3_bw_end': 'a3_bw_end_manual',
            'a3_color_end': 'a3_color_end_manual',
        }

        manual_field = manual_field_map.get(field_name)
        if manual_field:
            return getattr(self, manual_field, False)

        return False

    def mark_field_as_manually_edited(self, field_name: str):
        """
        Помечает поле как отредактированное вручную
        """
        manual_field_map = {
            'a4_bw_end': 'a4_bw_end_manual',
            'a4_color_end': 'a4_color_end_manual',
            'a3_bw_end': 'a3_bw_end_manual',
            'a3_color_end': 'a3_color_end_manual',
        }

        manual_field = manual_field_map.get(field_name)
        if manual_field:
            setattr(self, manual_field, True)

    def get_historical_average(self):
        """
        Возвращает среднее количество отпечатков за предыдущие месяцы
        для данного серийника
        """
        if not self.serial_number:
            return None

        result = MonthlyReport.objects.filter(
            serial_number=self.serial_number,
            month__lt=self.month
        ).aggregate(
            avg_prints=Avg('total_prints'),
            month_count=Count('id')
        )

        # Возвращаем среднее только если есть история (минимум 1 месяц)
        if result['month_count'] and result['month_count'] > 0:
            return {
                'average': result['avg_prints'],
                'months_count': result['month_count']
            }
        return None

    def check_anomaly(self, threshold=2000):
        """
        Проверяет, является ли текущее значение аномальным
        threshold: порог превышения среднего (по умолчанию 2000)
        """
        hist = self.get_historical_average()
        if not hist:
            return None

        avg = hist['average']
        difference = self.total_prints - avg

        return {
            'is_anomaly': difference > threshold,
            'average': round(avg, 0),
            'current': self.total_prints,
            'difference': round(difference, 0),
            'percentage': round((difference / avg * 100), 1) if avg > 0 else 0,
            'months_count': hist['months_count']
        }


# Остальные модели без изменений...
class MonthControl(models.Model):
    month = models.DateField(unique=True)
    edit_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Настройки месяца"
        verbose_name_plural = "Настройки месяцев"

    @property
    def is_editable(self) -> bool:
        return bool(self.edit_until and timezone.now() < self.edit_until)

    def __str__(self):
        return f"{self.month} (до {self.edit_until or 'закрыт'})"


class CounterChangeLog(models.Model):
    """
    Журнал изменений счетчиков с полной историей
    """
    monthly_report = models.ForeignKey(
        MonthlyReport,
        on_delete=models.CASCADE,
        related_name='change_logs',
        verbose_name='Запись отчета'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Пользователь'
    )

    field_name = models.CharField(
        'Поле',
        max_length=50,
        choices=[
            ('a4_bw_start', 'A4 ч/б начало'),
            ('a4_bw_end', 'A4 ч/б конец'),
            ('a4_color_start', 'A4 цвет начало'),
            ('a4_color_end', 'A4 цвет конец'),
            ('a3_bw_start', 'A3 ч/б начало'),
            ('a3_bw_end', 'A3 ч/б конец'),
            ('a3_color_start', 'A3 цвет начало'),
            ('a3_color_end', 'A3 цвет конец'),
        ]
    )

    old_value = models.PositiveIntegerField('Старое значение', null=True, blank=True)
    new_value = models.PositiveIntegerField('Новое значение', null=True, blank=True)

    timestamp = models.DateTimeField('Время изменения', default=timezone.now)
    ip_address = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    user_agent = models.TextField('User Agent', blank=True)

    change_source = models.CharField(
        'Источник',
        max_length=20,
        choices=[
            ('manual', 'Ручное редактирование'),
            ('excel_upload', 'Загрузка Excel'),
            ('auto_sync', 'Автосинхронизация'),
        ],
        default='manual'
    )

    comment = models.TextField('Комментарий', blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Лог изменений счетчика'
        verbose_name_plural = 'Логи изменений счетчиков'
        indexes = [
            models.Index(fields=['monthly_report', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['field_name', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user} изменил {self.field_name}: {self.old_value} → {self.new_value}"

    @property
    def change_delta(self):
        """Разница между новым и старым значением"""
        if self.old_value is not None and self.new_value is not None:
            return self.new_value - self.old_value
        return None

    def get_field_display_name(self):
        """Человекочитаемое название поля"""
        return dict(self._meta.get_field('field_name').choices).get(self.field_name, self.field_name)


class BulkChangeLog(models.Model):
    """
    Лог массовых операций (загрузка Excel, массовая синхронизация)
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    operation_type = models.CharField(
        'Тип операции',
        max_length=30,
        choices=[
            ('excel_upload', 'Загрузка Excel'),
            ('bulk_sync', 'Массовая синхронизация'),
            ('bulk_edit', 'Массовое редактирование'),
        ]
    )

    records_affected = models.PositiveIntegerField('Затронуто записей', default=0)
    fields_changed = models.JSONField('Измененные поля', default=list)
    operation_params = models.JSONField('Параметры', default=dict, blank=True)

    started_at = models.DateTimeField('Начало операции')
    finished_at = models.DateTimeField('Конец операции', null=True)

    success = models.BooleanField('Успешно', default=True)
    error_message = models.TextField('Ошибка', blank=True)

    ip_address = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    month = models.DateField('Месяц операции', null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Лог массовых операций'
        verbose_name_plural = 'Логи массовых операций'

    def __str__(self):
        return f"{self.get_operation_type_display()} от {self.started_at} ({self.records_affected} записей)"

    @property
    def duration(self):
        """Длительность операции"""
        if self.finished_at:
            return self.finished_at - self.started_at
        return None