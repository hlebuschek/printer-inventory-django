from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class MonthlyReport(models.Model):
    month = models.DateField(_('Месяц'), help_text='Первый день месяца (для группировки)')  # Например, 2025-09-01
    order_number = models.PositiveIntegerField(_('№ п/п'), default=1)
    organization = models.CharField(_('Организация'), max_length=255)
    branch = models.CharField(_('Филиал'), max_length=255)
    city = models.CharField(_('Город'), max_length=255)
    address = models.CharField(_('Адрес'), max_length=255)
    equipment_model = models.CharField(_('Модель и наименование оборудования'), max_length=255)
    serial_number = models.CharField(_('Серийный номер оборудования'), max_length=100)
    inventory_number = models.CharField(_('Инв номер'), max_length=100)
    a4_bw_start = models.PositiveIntegerField(_('Показание счетчика А4 (ч/б) на начало периода'), default=0)
    a4_bw_end = models.PositiveIntegerField(_('Показание счетчика А4 (ч/б) на конец периода'), default=0)
    a4_color_start = models.PositiveIntegerField(_('Показание счетчика А4 (цветные) на начало периода'), default=0)
    a4_color_end = models.PositiveIntegerField(_('Показание счетчика А4 (цветные) на конец периода'), default=0)
    a3_bw_start = models.PositiveIntegerField(_('Показание счетчика А3 (ч/б) на начало периода'), default=0)
    a3_bw_end = models.PositiveIntegerField(_('Показание счетчика А3 (ч/б) на конец периода'), default=0)
    a3_color_start = models.PositiveIntegerField(_('Показание счетчика А3 (цветные) на начало периода'), default=0)
    a3_color_end = models.PositiveIntegerField(_('Показание счетчика А3 (цветные) на конец периода'), default=0)
    total_prints = models.PositiveIntegerField(_('Итого отпечатков шт.'), default=0)  # Можно вычислять автоматически
    normative_availability = models.FloatField(_('Нормативное время доступности (A)'), default=0.0)
    actual_downtime = models.FloatField(_('Фактическое время недоступности (D)'), default=0.0)
    k1 = models.FloatField(_('K1 = ((A - D)/A)*100%'), default=0.0)  # Вычисляемый
    non_overdue_requests = models.PositiveIntegerField(_('Количество не просроченных запросов (L)'), default=0)
    total_requests = models.PositiveIntegerField(_('Общее количество запросов (W)'), default=0)
    k2 = models.FloatField(_('K2 = (L/W)*100%'), default=0.0)  # Вычисляемый

    class Meta:
        ordering = ['month', 'order_number']
        verbose_name = _('Ежемесячный отчет')
        verbose_name_plural = _('Ежемесячные отчеты')

    def save(self, *args, **kwargs):
        # Автоматический расчет total_prints, k1, k2
        self.total_prints = (
            (self.a4_bw_end - self.a4_bw_start) +
            (self.a4_color_end - self.a4_color_start) +
            (self.a3_bw_end - self.a3_bw_start) +
            (self.a3_color_end - self.a3_color_start)
        )
        if self.normative_availability > 0:
            self.k1 = ((self.normative_availability - self.actual_downtime) / self.normative_availability) * 100
        if self.total_requests > 0:
            self.k2 = (self.non_overdue_requests / self.total_requests) * 100
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Ежемесячный отчёт')
        verbose_name_plural = _('Ежемесячные отчёты')
        permissions = [
            ('access_monthly_report', 'Доступ к модулю ежемесячных отчётов'),
            ('upload_monthly_report', 'Загрузка отчётов из Excel'),
        ]

class MonthControl(models.Model):
    month = models.DateField(unique=True)
    edit_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Настройки месяца"
        verbose_name_plural = "Настройки месяцев"

    @property
    def is_editable(self) -> bool:
        """Редактирование открыто, если задан edit_until и текущее время раньше него."""
        return bool(self.edit_until and timezone.now() < self.edit_until)

    def __str__(self):
        return f"{self.month} (до {self.edit_until or 'закрыт'})"