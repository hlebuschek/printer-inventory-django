from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class MatchRule(models.TextChoices):
    SN_MAC = "SN_MAC", "Серийник + MAC"
    MAC_ONLY = "MAC_ONLY", "Только MAC"
    SN_ONLY = "SN_ONLY", "Только серийник"


class Organization(models.Model):
    name = models.CharField("Название", max_length=200)
    code = models.CharField("Код/краткое имя", max_length=50, blank=True)
    active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
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
    SNMP = "SNMP", "SNMP (GLPI Agent)"
    WEB = "WEB", "Web Parsing"
    USB_API = "USB_API", "USB Agent (API)"
    HYBRID = "HYBRID", "Совмещённый (SNMP + Web)"


class ConnectionType(models.TextChoices):
    NETWORK = "NETWORK", "Сетевой"
    USB = "USB", "USB"


class DataSource(models.TextChoices):
    SNMP_LOCAL = "SNMP_LOCAL", "SNMP (локальный GLPI)"
    WEB_SCRAPING = "WEB_SCRAPING", "Web Parsing"
    USB_AGENT = "USB_AGENT", "USB Agent API"


class Printer(models.Model):
    # IP-адрес теперь не unique напрямую - уникальность контролируется через constraints для is_active=True
    ip_address = models.GenericIPAddressField(db_index=True, verbose_name="IP-адрес")
    serial_number = models.CharField(max_length=100, db_index=True, verbose_name="Серийный номер")

    # СТАРОЕ ПОЛЕ - оставляем для совместимости, но помечаем как устаревшее
    model = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        verbose_name="Модель (текст, устарело)",
        help_text="Устаревшее текстовое поле. Используйте device_model.",
    )

    # НОВОЕ ПОЛЕ - связь со справочником
    device_model = models.ForeignKey(
        "contracts.DeviceModel",
        verbose_name="Модель оборудования",
        on_delete=models.PROTECT,
        related_name="inventory_printers",
        null=True,
        blank=True,
        help_text="Модель из справочника contracts",
    )

    snmp_community = models.CharField(max_length=100, verbose_name="SNMP сообщество")
    last_updated = models.DateTimeField(auto_now=True, db_index=True, verbose_name="Последнее обновление")
    # MAC-адрес теперь не unique напрямую - уникальность контролируется через constraints для is_active=True
    mac_address = models.CharField(max_length=17, null=True, blank=True, db_index=True, verbose_name="MAC-адрес")
    organization = models.ForeignKey(
        "Organization",
        verbose_name="Организация",
        related_name="printers",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    last_match_rule = models.CharField(
        max_length=10,
        choices=MatchRule.choices,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Последнее правило сопоставления",
    )

    # Новые поля для веб-парсинга
    polling_method = models.CharField(
        max_length=10, choices=PollingMethod.choices, default=PollingMethod.SNMP, verbose_name="Метод опроса"
    )

    connection_type = models.CharField(
        max_length=10,
        choices=ConnectionType.choices,
        default=ConnectionType.NETWORK,
        db_index=True,
        verbose_name="Тип подключения",
        help_text="NETWORK для SNMP/Web, USB для принтеров через локальный агент",
    )

    usb_identifier = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        verbose_name="USB DeviceInstanceId",
        help_text="Заполняется только для USB-принтеров",
    )

    web_username = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Web логин",
        help_text="Для веб-парсинга (если требуется аутентификация)",
    )

    web_password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Web пароль",
        help_text="Для веб-парсинга (если требуется аутентификация)",
    )

    # Поля для отслеживания статуса и замены оборудования
    is_active = models.BooleanField(
        "Активен", default=True, db_index=True, help_text="Неактивные принтеры - это замененное или снятое оборудование"
    )
    replaced_at = models.DateTimeField(
        "Дата замены", null=True, blank=True, help_text="Когда принтер был заменён другим оборудованием"
    )
    replaced_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replaced_printers",
        verbose_name="Заменён на",
        help_text="Принтер, который заменил данный",
    )

    class Meta:
        verbose_name = "Принтер"
        verbose_name_plural = "Принтеры"
        indexes = [
            models.Index(fields=["ip_address"]),
            models.Index(fields=["serial_number"]),
            models.Index(fields=["model"]),
            models.Index(fields=["last_updated"]),
            models.Index(fields=["mac_address"]),
            models.Index(fields=["model", "serial_number"]),
            models.Index(fields=["last_match_rule"]),
            models.Index(fields=["organization", "ip_address"], name="inv_printer_org_ip_idx"),
            models.Index(fields=["last_match_rule", "ip_address"], name="inv_printer_rule_ip_idx"),
            models.Index(fields=["device_model", "ip_address"], name="inv_printer_devmodel_ip_idx"),
            models.Index(fields=["is_active", "ip_address"], name="inv_printer_active_ip_idx"),
        ]
        constraints = [
            # IP-адрес уникален только среди АКТИВНЫХ СЕТЕВЫХ принтеров
            # (USB-принтеры используют placeholder IP и не должны конфликтовать)
            models.UniqueConstraint(
                fields=["ip_address"],
                condition=Q(is_active=True) & Q(connection_type="NETWORK"),
                name="unique_active_ip",
            ),
            # MAC-адрес уникален только среди АКТИВНЫХ принтеров (если заполнен)
            models.UniqueConstraint(
                fields=["mac_address"],
                condition=Q(is_active=True) & ~Q(mac_address=None) & ~Q(mac_address=""),
                name="unique_active_mac",
            ),
            # Серийник уникален среди активных USB-принтеров — защита от
            # race-condition при авто-создании из reading'ов USB-агента.
            models.UniqueConstraint(
                fields=["serial_number"],
                condition=Q(is_active=True) & Q(connection_type="USB"),
                name="unique_active_usb_serial",
            ),
        ]

    def __str__(self):
        if self.connection_type == ConnectionType.USB:
            return f"USB {self.serial_number}"
        return f"{self.ip_address} ({self.serial_number})"

    @property
    def model_display(self):
        """Получить название модели (из справочника или из старого поля)"""
        if self.device_model:
            return str(self.device_model)
        return self.model


class InventoryTask(models.Model):
    STATUS_CHOICES = [
        ("SUCCESS", "Успешно"),
        ("FAILED", "Ошибка"),
        ("VALIDATION_ERROR", "Ошибка валидации"),
        ("HISTORICAL_INCONSISTENCY", "Исторические данные не согласованы"),
    ]

    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, verbose_name="Принтер", db_index=True)
    task_timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата опроса")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, db_index=True, verbose_name="Статус")
    error_message = models.TextField(blank=True, null=True, verbose_name="Сообщение об ошибке")
    match_rule = models.CharField(
        max_length=10,
        choices=MatchRule.choices,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Правило сопоставления",
    )
    data_source = models.CharField(
        max_length=20,
        choices=DataSource.choices,
        default=DataSource.SNMP_LOCAL,
        db_index=True,
        verbose_name="Источник данных",
    )
    agent_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name="ID агента",
        help_text="Заполняется только для USB-агентов",
    )

    class Meta:
        verbose_name = "Задача инвентаризации"
        verbose_name_plural = "Задачи инвентаризации"
        ordering = ["-task_timestamp"]
        indexes = [
            models.Index(fields=["printer"]),
            models.Index(fields=["status"]),
            models.Index(fields=["task_timestamp"]),
            models.Index(fields=["printer", "task_timestamp"]),
            models.Index(fields=["status", "task_timestamp"]),
            models.Index(fields=["printer", "status", "-task_timestamp"], name="inv_task_printer_status_ts_idx"),
            models.Index(fields=["data_source"], name="inv_task_data_source_idx"),
        ]

    def __str__(self):
        return f"{self.printer.ip_address} @ {self.task_timestamp} — {self.status}"


class PageCounter(models.Model):
    """Счётчики страниц и уровни расходников (тонер/драм/статусы)."""

    task = models.ForeignKey(InventoryTask, on_delete=models.CASCADE, verbose_name="Задача", db_index=True)
    bw_a3 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="ЧБ A3")
    bw_a4 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="ЧБ A4")
    color_a3 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="Цвет A3")
    color_a4 = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="Цвет A4")
    total_pages = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="Всего страниц")
    drum_black = models.CharField(max_length=20, blank=True, verbose_name="DRUMBLACK")
    drum_cyan = models.CharField(max_length=20, blank=True, verbose_name="DRUMCYAN")
    drum_magenta = models.CharField(max_length=20, blank=True, verbose_name="DRUMMAGENTA")
    drum_yellow = models.CharField(max_length=20, blank=True, verbose_name="DRUMYELLOW")
    toner_black = models.CharField(max_length=20, blank=True, verbose_name="TONERBLACK")
    toner_cyan = models.CharField(max_length=20, blank=True, verbose_name="TONERCYAN")
    toner_magenta = models.CharField(max_length=20, blank=True, verbose_name="TONERMAGENTA")
    toner_yellow = models.CharField(max_length=20, blank=True, verbose_name="TONERYELLOW")
    fuser_kit = models.CharField(
        max_length=20, choices=[("OK", "OK"), ("WARNING", "WARNING")], blank=True, verbose_name="FUSERKIT"
    )
    transfer_kit = models.CharField(
        max_length=20, choices=[("OK", "OK"), ("WARNING", "WARNING")], blank=True, verbose_name="TRANSFERKIT"
    )
    waste_toner = models.CharField(
        max_length=20, choices=[("OK", "OK"), ("WARNING", "WARNING")], blank=True, verbose_name="WASTETONER"
    )
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Время записи")

    class Meta:
        verbose_name = "Счётчики и расходники"
        verbose_name_plural = "Счётчики и расходники"
        indexes = [
            models.Index(fields=["task"]),
            models.Index(fields=["total_pages"]),
            models.Index(fields=["recorded_at"]),
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
            ("view_api_docs", "Can view API documentation"),
            ("manage_network_scan", "Can manage network scanning"),
        ]
        app_label = "inventory"


class WebParsingRule(models.Model):
    """Правила парсинга веб-страницы принтера"""

    FIELD_CHOICES = [
        ("serial_number", "Серийный номер"),
        ("mac_address", "MAC-адрес"),
        ("counter", "Общий счетчик"),
        ("counter_a4_bw", "ЧБ A4"),
        ("counter_a3_bw", "ЧБ A3"),
        ("counter_a4_color", "Цвет A4"),
        ("counter_a3_color", "Цвет A3"),
        ("toner_black", "Тонер черный"),
        ("toner_cyan", "Тонер голубой"),
        ("toner_magenta", "Тонер пурпурный"),
        ("toner_yellow", "Тонер желтый"),
        ("drum_black", "Барабан черный"),
        ("drum_cyan", "Барабан голубой"),
        ("drum_magenta", "Барабан пурпурный"),
        ("drum_yellow", "Барабан желтый"),
        ("variable_1", "Переменная 1"),
        ("variable_2", "Переменная 2"),
        ("variable_3", "Переменная 3"),
        ("variable_4", "Переменная 4"),
        ("variable_5", "Переменная 5"),
    ]

    printer = models.ForeignKey(
        Printer, on_delete=models.CASCADE, related_name="web_parsing_rules", verbose_name="Принтер"
    )

    protocol = models.CharField(
        max_length=10, default="http", choices=[("http", "HTTP"), ("https", "HTTPS")], verbose_name="Протокол"
    )

    url_path = models.CharField(
        max_length=500, verbose_name="URL путь", help_text="Например: /status.htm или /eng/general/information.cgi"
    )

    field_name = models.CharField(max_length=50, choices=FIELD_CHOICES, verbose_name="Поле")

    xpath = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="XPath выражение",
        help_text='Например: //td[contains(text(),"Serial")]/following-sibling::td/text()',
    )

    regex_pattern = models.CharField(
        max_length=500, blank=True, verbose_name="Regex паттерн", help_text="Для обработки извлеченного значения"
    )

    regex_replacement = models.CharField(max_length=500, blank=True, verbose_name="Regex замена")

    is_calculated = models.BooleanField(default=False, verbose_name="Вычисляемое поле")
    source_rules = models.TextField(
        blank=True, verbose_name="Правила-источники", help_text="JSON список ID правил для вычисления"
    )
    calculation_formula = models.TextField(
        blank=True, verbose_name="Формула вычисления", help_text="Например: rule_1 + rule_2 * 2"
    )
    actions_chain = models.TextField(
        blank=True, verbose_name="Цепочка действий", help_text="JSON список действий перед парсингом"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Правило веб-парсинга"
        verbose_name_plural = "Правила веб-парсинга"
        ordering = ["printer", "field_name"]

    def __str__(self):
        return f"{self.printer.ip_address} - {self.get_field_name_display()}"


class WebParsingTemplate(models.Model):
    """Шаблон правил веб-парсинга для переиспользования"""

    name = models.CharField(
        max_length=200, verbose_name="Название шаблона", help_text='Например: "Ricoh MP C2004 - стандартная настройка"'
    )

    device_model = models.ForeignKey(
        "contracts.DeviceModel",
        on_delete=models.CASCADE,
        related_name="parsing_templates",
        verbose_name="Модель оборудования",
        help_text="К какой модели относится этот шаблон",
    )

    description = models.TextField(blank=True, verbose_name="Описание", help_text="Комментарии по настройке")

    # JSON с правилами
    rules_config = models.JSONField(verbose_name="Конфигурация правил", help_text="JSON массив с правилами парсинга")

    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Создал")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    is_public = models.BooleanField(default=False, verbose_name="Публичный", help_text="Доступен всем пользователям")

    usage_count = models.IntegerField(default=0, verbose_name="Количество применений")

    class Meta:
        verbose_name = "Шаблон веб-парсинга"
        verbose_name_plural = "Шаблоны веб-парсинга"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device_model", "is_public"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.device_model})"


class PrinterChangeLog(models.Model):
    """Лог изменений принтера (замена оборудования, смена IP, деактивация)"""

    ACTION_CHOICES = [
        ("ip_change", "Смена IP-адреса"),
        ("serial_update", "Обновление серийника"),
        ("mac_update", "Обновление MAC-адреса"),
        ("deactivation", "Деактивация"),
        ("replacement", "Замена оборудования"),
        ("activation", "Активация"),
    ]

    TRIGGERED_BY_CHOICES = [
        ("auto_poll", "Автоопрос"),
        ("manual", "Вручную"),
        ("net_scan", "Сканирование сети"),
    ]

    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, related_name="change_logs", verbose_name="Принтер")
    action = models.CharField("Действие", max_length=20, choices=ACTION_CHOICES, db_index=True)
    timestamp = models.DateTimeField("Время", auto_now_add=True, db_index=True)

    old_values = models.JSONField("Старые значения", default=dict, blank=True)
    new_values = models.JSONField("Новые значения", default=dict, blank=True)

    related_printer = models.ForeignKey(
        Printer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="related_changes",
        verbose_name="Связанный принтер",
    )

    comment = models.TextField("Комментарий", blank=True)
    triggered_by = models.CharField("Источник", max_length=20, choices=TRIGGERED_BY_CHOICES, default="auto_poll")

    class Meta:
        verbose_name = "Лог изменений принтера"
        verbose_name_plural = "Логи изменений принтеров"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["printer", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["related_printer", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.printer} - {self.get_action_display()} @ {self.timestamp}"


class USBAgent(models.Model):
    """USB-агент для опроса локальных принтеров через PrinterCollector."""

    agent_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="ID агента")
    # Хранится SHA-256 hex от plaintext-токена. Plaintext знает только агент.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Хэш токена доступа")
    hostname = models.CharField(max_length=200, blank=True, verbose_name="Имя компьютера")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    agent_version = models.CharField(max_length=20, blank=True, default="", verbose_name="Версия агента")

    class Meta:
        verbose_name = "USB-агент"
        verbose_name_plural = "USB-агенты"
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.agent_id} ({self.hostname})"


class ScanNetwork(models.Model):
    """Сеть (VLAN), которую периодически сканируем glpi-netdiscovery в поисках принтеров."""

    name = models.CharField("Название", max_length=200)
    cidr = models.CharField("Сеть (CIDR)", max_length=43, unique=True, help_text="Например 10.20.30.0/24")
    vlan_id = models.PositiveSmallIntegerField("VLAN", null=True, blank=True)
    organizations = models.ManyToManyField(
        "Organization",
        verbose_name="Организации в сети",
        related_name="scan_networks",
        blank=True,
        help_text=(
            "Необязательно. Организация принтера берётся из договора по серийнику, поэтому в одной сети "
            "могут быть разные организации. Список нужен, только если один серийник есть в договорах "
            "у нескольких организаций — тогда выбираем ту, что указана здесь."
        ),
    )
    snmp_community = models.CharField("SNMP community", max_length=100, default="public")
    is_enabled = models.BooleanField("Сканировать по расписанию", default=True, db_index=True)
    scan_interval_hours = models.PositiveSmallIntegerField("Интервал сканирования, ч", default=24)
    comment = models.TextField("Комментарий", blank=True)

    last_scan_at = models.DateTimeField("Последнее сканирование", null=True, blank=True)

    # Сверка найденных устройств с GLPI (по кнопке, отдельной задачей)
    glpi_check_started_at = models.DateTimeField("Сверка с GLPI: начало", null=True, blank=True)
    glpi_check_finished_at = models.DateTimeField("Сверка с GLPI: окончание", null=True, blank=True)
    glpi_check_total = models.PositiveIntegerField("Сверка с GLPI: устройств", default=0)
    glpi_check_done = models.PositiveIntegerField("Сверка с GLPI: проверено", default=0)
    glpi_check_error = models.TextField("Сверка с GLPI: ошибка", blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Сеть для сканирования"
        verbose_name_plural = "Сети для сканирования"
        ordering = ["name"]

    def __str__(self):
        vlan = f" VLAN {self.vlan_id}" if self.vlan_id else ""
        return f"{self.name} ({self.cidr}{vlan})"


class NetworkScanRun(models.Model):
    """Один прогон сканирования сети. Большие сети идут кусками по /24 — отдельной Celery-задачей на кусок."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    STATUS_CHOICES = [(RUNNING, "Выполняется"), (SUCCESS, "Завершено"), (ERROR, "Ошибка")]

    network = models.ForeignKey(ScanNetwork, on_delete=models.CASCADE, related_name="runs", verbose_name="Сеть")
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES, default=RUNNING, db_index=True)
    started_at = models.DateTimeField("Начало", auto_now_add=True)
    finished_at = models.DateTimeField("Окончание", null=True, blank=True)
    chunks_total = models.PositiveIntegerField("Кусков всего", default=0)
    chunks_done = models.PositiveIntegerField("Кусков готово", default=0)
    stats = models.JSONField("Счётчики", default=dict, blank=True)
    error = models.TextField("Ошибки", blank=True)
    triggered_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Запустил"
    )

    class Meta:
        verbose_name = "Прогон сканирования сети"
        verbose_name_plural = "Прогоны сканирования сетей"
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["network", "-started_at"])]

    def __str__(self):
        return f"{self.network.cidr} @ {self.started_at:%Y-%m-%d %H:%M} — {self.get_status_display()}"


class DiscoveredDevice(models.Model):
    """
    Устройство, найденное сканированием сети, и итог сверки с опросом и договорами.
    Одна запись на устройство в сети: повторные сканы обновляют её, а не плодят новые.
    """

    OK = "ok"
    IP_CHANGED = "ip_changed"
    IP_CHANGE_PENDING = "ip_pending"
    ADDED = "added"
    NOT_IN_CONTRACT = "not_in_contract"
    CONFLICT = "conflict"
    MISSING = "missing"
    DUPLICATE_SERIAL = "duplicate_serial"
    STATUS_CHOICES = [
        (OK, "Опрашивается, IP совпадает"),
        (IP_CHANGED, "IP сменился — обновлён"),
        (IP_CHANGE_PENDING, "IP сменился — нужна проверка"),
        (ADDED, "Из договора — заведён в опрос"),
        (NOT_IN_CONTRACT, "Нет в договоре"),
        (CONFLICT, "Конфликт"),
        (MISSING, "Не отвечает"),
        (DUPLICATE_SERIAL, "Одинаковый серийник"),
    ]

    # Итог сверки с GLPI
    GLPI_ACTIVE = "active"
    GLPI_OTHER_IP = "other_ip"
    GLPI_STALE = "stale"
    GLPI_NOT_FOUND = "not_found"
    GLPI_MULTIPLE = "multiple"
    GLPI_ERROR = "error"
    GLPI_STATUS_CHOICES = [
        (GLPI_ACTIVE, "Опрашивается в GLPI"),
        (GLPI_OTHER_IP, "В GLPI другой IP"),
        (GLPI_STALE, "Счётчик в GLPI не обновляется"),
        (GLPI_NOT_FOUND, "Нет в GLPI"),
        (GLPI_MULTIPLE, "Несколько карточек в GLPI"),
        (GLPI_ERROR, "Ошибка проверки GLPI"),
    ]
    # всё, кроме «опрашивается»: в GLPI с устройством проблема
    GLPI_PROBLEMS = [GLPI_OTHER_IP, GLPI_STALE, GLPI_NOT_FOUND, GLPI_MULTIPLE]

    network = models.ForeignKey(ScanNetwork, on_delete=models.CASCADE, related_name="devices", verbose_name="Сеть")
    identity = models.CharField("Ключ", max_length=150, help_text="sn:<серийник> или mac:<MAC>")
    ip_address = models.GenericIPAddressField("IP-адрес", protocol="IPv4", null=True, blank=True)
    serial_number = models.CharField("Серийный номер", max_length=128, blank=True)
    mac_address = models.CharField("MAC-адрес", max_length=17, blank=True)
    manufacturer = models.CharField("Производитель", max_length=200, blank=True)
    model = models.CharField("Модель", max_length=200, blank=True)
    device_type = models.CharField("Тип", max_length=50, blank=True)
    snmp_name = models.CharField("SNMP-имя", max_length=200, blank=True)

    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, db_index=True)
    message = models.TextField("Пояснение", blank=True)
    printer = models.ForeignKey(
        Printer, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Принтер"
    )
    contract_device = models.ForeignKey(
        "contracts.ContractDevice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Устройство по договору",
    )
    is_ignored = models.BooleanField("Скрыто", default=False, db_index=True)
    missed_scans = models.PositiveSmallIntegerField("Пропущено сканов подряд", default=0)

    glpi_status = models.CharField(
        "GLPI", max_length=20, choices=GLPI_STATUS_CHOICES, blank=True, db_index=True, help_text="Пусто — не сверялось"
    )
    glpi_message = models.TextField("GLPI: пояснение", blank=True)
    glpi_printer_id = models.PositiveIntegerField("GLPI: ID карточки", null=True, blank=True)
    glpi_name = models.CharField("GLPI: имя", max_length=255, blank=True)
    glpi_entity = models.CharField("GLPI: сущность", max_length=500, blank=True)
    glpi_ip = models.CharField("GLPI: IP", max_length=100, blank=True)
    glpi_last_inventory = models.DateTimeField("GLPI: последний опрос", null=True, blank=True)
    glpi_counter = models.PositiveIntegerField("GLPI: счётчик", null=True, blank=True)
    glpi_checked_at = models.DateTimeField("GLPI: сверено", null=True, blank=True)

    first_seen = models.DateTimeField("Впервые найдено", auto_now_add=True)
    last_seen = models.DateTimeField("Последний раз отвечало", null=True, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Найденное устройство"
        verbose_name_plural = "Найденные устройства"
        ordering = ["network", "ip_address"]
        constraints = [
            models.UniqueConstraint(fields=["network", "identity"], name="uniq_discovered_network_identity"),
        ]
        indexes = [models.Index(fields=["network", "status"])]

    def __str__(self):
        return f"{self.ip_address} {self.serial_number or self.mac_address} ({self.get_status_display()})"
