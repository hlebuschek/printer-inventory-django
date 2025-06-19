from django.db import models


class Printer(models.Model):
    ip_address     = models.GenericIPAddressField(unique=True, db_index=True, verbose_name='IP-адрес')
    serial_number  = models.CharField(max_length=100, db_index=True, verbose_name='Серийный номер')
    model          = models.CharField(max_length=200, blank=True, db_index=True, verbose_name='Модель')
    snmp_community = models.CharField(max_length=100, verbose_name='SNMP сообщество')
    last_updated   = models.DateTimeField(auto_now=True, db_index=True, verbose_name='Последнее обновление')

    class Meta:
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['model']),
            models.Index(fields=['last_updated']),
            models.Index(fields=['model', 'serial_number']),
        ]

    def __str__(self):
        return f"{self.ip_address} ({self.serial_number})"


class InventoryTask(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
        ('VALIDATION_ERROR', 'Ошибка валидации'),
    ]

    printer        = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        verbose_name='Принтер',
        db_index=True
    )
    task_timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата опроса')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True, verbose_name='Статус')
    error_message  = models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')

    class Meta:
        verbose_name = 'Задача инвентаризации'
        verbose_name_plural = 'Задачи инвентаризации'
        ordering = ['-task_timestamp']
        indexes = [
            models.Index(fields=['printer']),
            models.Index(fields=['status']),
            models.Index(fields=['task_timestamp']),
            models.Index(fields=['printer', 'task_timestamp']),
            models.Index(fields=['status', 'task_timestamp']),
        ]

    def __str__(self):
        return f"{self.printer.ip_address} @ {self.task_timestamp} — {self.status}"


class PageCounter(models.Model):
    """
    Счётчики страниц и уровни расходников (тонер/драм/статусы).
    """
    task         = models.ForeignKey(
        InventoryTask,
        on_delete=models.CASCADE,
        verbose_name='Задача',
        db_index=True
    )
    # Счётчики страниц
    bw_a3        = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='ЧБ A3')
    bw_a4        = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='ЧБ A4')
    color_a3     = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Цвет A3')
    color_a4     = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Цвет A4')
    total_pages  = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Всего страниц')

    # Новые поля: уровни расходников (процент или WARNING/OK)
    drum_black    = models.CharField(max_length=20, blank=True, verbose_name='DRUMBLACK')
    drum_cyan     = models.CharField(max_length=20, blank=True, verbose_name='DRUMCYAN')
    drum_magenta  = models.CharField(max_length=20, blank=True, verbose_name='DRUMMAGENTA')
    drum_yellow   = models.CharField(max_length=20, blank=True, verbose_name='DRUMYELLOW')

    toner_black   = models.CharField(max_length=20, blank=True, verbose_name='TONERBLACK')
    toner_cyan    = models.CharField(max_length=20, blank=True, verbose_name='TONERCYAN')
    toner_magenta = models.CharField(max_length=20, blank=True, verbose_name='TONERMAGENTA')
    toner_yellow  = models.CharField(max_length=20, blank=True, verbose_name='TONERYELLOW')

    fuser_kit     = models.CharField(
        max_length=20,
        choices=[('OK','OK'),('WARNING','WARNING')],
        blank=True,
        verbose_name='FUSERKIT'
    )
    transfer_kit  = models.CharField(
        max_length=20,
        choices=[('OK','OK'),('WARNING','WARNING')],
        blank=True,
        verbose_name='TRANSFERKIT'
    )
    waste_toner   = models.CharField(
        max_length=20,
        choices=[('OK','OK'),('WARNING','WARNING')],
        blank=True,
        verbose_name='WASTETONER'
    )

    recorded_at  = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Время записи')

    class Meta:
        verbose_name = 'Счётчики и расходники'
        verbose_name_plural = 'Счётчики и расходники'
        indexes = [
            models.Index(fields=['task']),
            models.Index(fields=['total_pages']),
            models.Index(fields=['recorded_at']),
        ]

    def __str__(self):
        return f"{self.task.printer.ip_address}: {self.total_pages} стр. @ {self.recorded_at}"