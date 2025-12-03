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


class PollingMethod(models.TextChoices):
    SNMP = 'SNMP', 'SNMP (GLPI Agent)'
    WEB = 'WEB', 'Web Parsing'


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

    # Новые поля для веб-парсинга
    polling_method = models.CharField(
        max_length=10,
        choices=PollingMethod.choices,
        default=PollingMethod.SNMP,
        verbose_name='Метод опроса'
    )

    web_username = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Web логин',
        help_text='Для веб-парсинга (если требуется аутентификация)'
    )

    web_password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Web пароль',
        help_text='Для веб-парсинга (если требуется аутентификация)'
    )

    class Meta:
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['model']),
            models.Index(fields=['last_updated']),
            models.Index(fields=['mac_address']),
            models.Index(fields=['model', 'serial_number']),
            models.Index(fields=['last_match_rule']),
            models.Index(fields=['organization', 'ip_address'], name='inv_printer_org_ip_idx'),
            models.Index(fields=['last_match_rule', 'ip_address'], name='inv_printer_rule_ip_idx'),
            models.Index(fields=['device_model', 'ip_address'], name='inv_printer_devmodel_ip_idx'),
        ]

    def __str__(self):
        return f"{self.ip_address} ({self.serial_number})"

    @property
    def model_display(self):
        """Получить название модели (из справочника или из старого поля)"""
        if self.device_model:
            return str(self.device_model)
        return self.model


class InventoryTask(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
        ('VALIDATION_ERROR', 'Ошибка валидации'),
        ('HISTORICAL_INCONSISTENCY', 'Исторические данные не согласованы'),
    ]

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        verbose_name='Принтер',
        db_index=True
    )
    task_timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата опроса')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, db_index=True, verbose_name='Статус')
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
            models.Index(fields=['printer', 'status', '-task_timestamp'], name='inv_task_printer_status_ts_idx'),
        ]

    def __str__(self):
        return f"{self.printer.ip_address} @ {self.task_timestamp} — {self.status}"


class PageCounter(models.Model):
    """Счётчики страниц и уровни расходников (тонер/драм/статусы)."""
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
    fuser_kit = models.CharField(max_length=20, choices=[('OK', 'OK'), ('WARNING', 'WARNING')], blank=True, verbose_name='FUSERKIT')
    transfer_kit = models.CharField(max_length=20, choices=[('OK', 'OK'), ('WARNING', 'WARNING')], blank=True, verbose_name='TRANSFERKIT')
    waste_toner = models.CharField(max_length=20, choices=[('OK', 'OK'), ('WARNING', 'WARNING')], blank=True, verbose_name='WASTETONER')
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
            ("manage_web_parsing", "Can manage web parsing rules"),
            ("view_web_parsing", "Can view web parsing rules"),
            ("can_create_public_templates", "Can create public parsing templates"),
        ]
        app_label = "inventory"


class WebParsingRule(models.Model):
    """Правила парсинга веб-страницы принтера"""

    FIELD_CHOICES = [
        ('serial_number', 'Серийный номер'),
        ('mac_address', 'MAC-адрес'),
        ('counter', 'Общий счетчик'),
        ('counter_a4_bw', 'ЧБ A4'),
        ('counter_a3_bw', 'ЧБ A3'),
        ('counter_a4_color', 'Цвет A4'),
        ('counter_a3_color', 'Цвет A3'),
        ('toner_black', 'Тонер черный'),
        ('toner_cyan', 'Тонер голубой'),
        ('toner_magenta', 'Тонер пурпурный'),
        ('toner_yellow', 'Тонер желтый'),
        ('drum_black', 'Барабан черный'),
        ('drum_cyan', 'Барабан голубой'),
        ('drum_magenta', 'Барабан пурпурный'),
        ('drum_yellow', 'Барабан желтый'),
    ]

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        related_name='web_parsing_rules',
        verbose_name='Принтер'
    )

    protocol = models.CharField(
        max_length=10,
        default='http',
        choices=[('http', 'HTTP'), ('https', 'HTTPS')],
        verbose_name='Протокол'
    )

    url_path = models.CharField(
        max_length=500,
        verbose_name='URL путь',
        help_text='Например: /status.htm или /eng/general/information.cgi'
    )

    field_name = models.CharField(
        max_length=50,
        choices=FIELD_CHOICES,
        verbose_name='Поле'
    )

    xpath = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='XPath выражение',
        help_text='Например: //td[contains(text(),"Serial")]/following-sibling::td/text()'
    )

    regex_pattern = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Regex паттерн',
        help_text='Для обработки извлеченного значения'
    )

    regex_replacement = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Regex замена'
    )

    is_calculated = models.BooleanField(default=False, verbose_name='Вычисляемое поле')
    source_rules = models.TextField(blank=True, verbose_name='Правила-источники', help_text='JSON список ID правил для вычисления')
    calculation_formula = models.TextField(blank=True, verbose_name='Формула вычисления', help_text='Например: rule_1 + rule_2 * 2')
    actions_chain = models.TextField(blank=True, verbose_name='Цепочка действий', help_text='JSON список действий перед парсингом')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Правило веб-парсинга'
        verbose_name_plural = 'Правила веб-парсинга'
        ordering = ['printer', 'field_name']

    def __str__(self):
        return f"{self.printer.ip_address} - {self.get_field_name_display()}"



class WebParsingTemplate(models.Model):
    """Шаблон правил веб-парсинга для переиспользования"""

    name = models.CharField(
        max_length=200,
        verbose_name='Название шаблона',
        help_text='Например: "Ricoh MP C2004 - стандартная настройка"'
    )

    device_model = models.ForeignKey(
        'contracts.DeviceModel',
        on_delete=models.CASCADE,
        related_name='parsing_templates',
        verbose_name='Модель оборудования',
        help_text='К какой модели относится этот шаблон'
    )

    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Комментарии по настройке'
    )

    # JSON с правилами
    rules_config = models.JSONField(
        verbose_name='Конфигурация правил',
        help_text='JSON массив с правилами парсинга'
    )

    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создал'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    is_public = models.BooleanField(
        default=False,
        verbose_name='Публичный',
        help_text='Доступен всем пользователям'
    )

    usage_count = models.IntegerField(
        default=0,
        verbose_name='Количество применений'
    )

    class Meta:
        verbose_name = 'Шаблон веб-парсинга'
        verbose_name_plural = 'Шаблоны веб-парсинга'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device_model', 'is_public']),
        ]

    def __str__(self):
        return f"{self.name} ({self.device_model})"
