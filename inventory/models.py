from django.db import models
from django.db.models.functions import Lower


class MatchRule(models.TextChoices):
    SN_MAC = 'SN_MAC', 'Серийник + MAC'
    MAC_ONLY = 'MAC_ONLY', 'Только MAC'
    SN_ONLY = 'SN_ONLY', 'Только серийник'


class Organization(models.Model):
    name = models.CharField("Название", max_length=200)
    code = models.CharField("Код/краткое имя", max_length=50, blank=True)
    active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="org_name_ci_unique",
                violation_error_message="Организация с таким названием уже существует.",
            )
        ]

    def __str__(self):
        return self.name


class Printer(models.Model):
    ip_address = models.GenericIPAddressField(unique=True, db_index=True, verbose_name='IP-адрес')
    serial_number = models.CharField(max_length=100, db_index=True, verbose_name='Серийный номер')

    # СТАРОЕ ПОЛЕ - оставляем для совместимости, но помечаем как устаревшее
    model = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        verbose_name='Модель (текст, устарело)',
        help_text='Устаревшее текстовое поле. Используйте device_model.'
    )

    # НОВОЕ ПОЛЕ - связь со справочником
    device_model = models.ForeignKey(
        'contracts.DeviceModel',
        verbose_name='Модель оборудования',
        on_delete=models.PROTECT,
        related_name='inventory_printers',
        null=True,
        blank=True,
        help_text='Модель из справочника contracts'
    )

    snmp_community = models.CharField(max_length=100, verbose_name='SNMP сообщество')
    last_updated = models.DateTimeField(auto_now=True, db_index=True, verbose_name='Последнее обновление')
    mac_address = models.CharField(max_length=17, null=True, blank=True, unique=True, db_index=True,
                                   verbose_name='MAC-адрес')
    organization = models.ForeignKey(
        "Organization",
        verbose_name="Организация",
        related_name="printers",
        null=True, blank=True,
        on_delete=models.PROTECT,
    )
    last_match_rule = models.CharField(
        max_length=10,
        choices=MatchRule.choices,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Последнее правило сопоставления',
    )

    class Meta:
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'
        indexes = [
            # Старые индексы (оставляем для совместимости)
            models.Index(fields=['ip_address']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['model']),
            models.Index(fields=['last_updated']),
            models.Index(fields=['mac_address']),
            models.Index(fields=['model', 'serial_number']),
            models.Index(fields=['last_match_rule']),

            # НОВЫЕ составные индексы для ускорения списка
            models.Index(
                fields=['organization', 'ip_address'],
                name='inv_printer_org_ip_idx'
            ),
            models.Index(
                fields=['last_match_rule', 'ip_address'],
                name='inv_printer_rule_ip_idx'
            ),
            # Индекс для нового поля device_model
            models.Index(
                fields=['device_model', 'ip_address'],
                name='inv_printer_devmodel_ip_idx'
            ),
        ]

    def __str__(self):
        return f"{self.ip_address} ({self.serial_number})"

    @property
    def model_display(self):
        """Получить название модели (из справочника или из старого поля)"""
        if self.device_model:
            return str(self.device_model)  # вернет "Manufacturer Model"
        return self.model  # fallback на старое текстовое поле


# Остальные модели без изменений...
class InventoryTask(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
        ('VALIDATION_ERROR', 'Ошибка валидации'),
    ]

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        verbose_name='Принтер',
        db_index=True
    )
    task_timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата опроса')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True, verbose_name='Статус')
    error_message = models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')
    match_rule = models.CharField(
        max_length=10,
        choices=MatchRule.choices,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Правило сопоставления',
    )

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
            models.Index(
                fields=['printer', 'status', '-task_timestamp'],
                name='inv_task_printer_status_ts_idx'
            ),
        ]

    def __str__(self):
        return f"{self.printer.ip_address} @ {self.task_timestamp} — {self.status}"


class PageCounter(models.Model):
    """
    Счётчики страниц и уровни расходников (тонер/драм/статусы).
    """
    task = models.ForeignKey(
        InventoryTask,
        on_delete=models.CASCADE,
        verbose_name='Задача',
        db_index=True
    )
    bw_a3 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='ЧБ A3')
    bw_a4 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='ЧБ A4')
    color_a3 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Цвет A3')
    color_a4 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Цвет A4')
    total_pages = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Всего страниц')
    drum_black = models.CharField(max_length=20, blank=True, verbose_name='DRUMBLACK')
    drum_cyan = models.CharField(max_length=20, blank=True, verbose_name='DRUMCYAN')
    drum_magenta = models.CharField(max_length=20, blank=True, verbose_name='DRUMMAGENTA')
    drum_yellow = models.CharField(max_length=20, blank=True, verbose_name='DRUMYELLOW')
    toner_black = models.CharField(max_length=20, blank=True, verbose_name='TONERBLACK')
    toner_cyan = models.CharField(max_length=20, blank=True, verbose_name='TONERCYAN')
    toner_magenta = models.CharField(max_length=20, blank=True, verbose_name='TONERMAGENTA')
    toner_yellow = models.CharField(max_length=20, blank=True, verbose_name='TONERYELLOW')
    fuser_kit = models.CharField(
        max_length=20,
        choices=[('OK', 'OK'), ('WARNING', 'WARNING')],
        blank=True,
        verbose_name='FUSERKIT'
    )
    transfer_kit = models.CharField(
        max_length=20,
        choices=[('OK', 'OK'), ('WARNING', 'WARNING')],
        blank=True,
        verbose_name='TRANSFERKIT'
    )
    waste_toner = models.CharField(
        max_length=20,
        choices=[('OK', 'OK'), ('WARNING', 'WARNING')],
        blank=True,
        verbose_name='WASTETONER'
    )
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Время записи')

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


class InventoryAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_inventory_app", "Can access Inventory app"),
            ("run_inventory", "Can run inventory scans"),
            ("export_printers", "Can export printers to Excel"),
            ("export_amb_report", "Can export AMB report"),
        ]
        app_label = "inventory"