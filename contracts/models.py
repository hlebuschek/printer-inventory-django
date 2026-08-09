from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from inventory.models import Organization, Printer

# ─── Справочники ───────────────────────────────────────────────────────────────


class City(models.Model):
    name = models.CharField("Город", max_length=128, unique=True)

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="city_name_ci_unique")]

    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    name = models.CharField("Производитель", max_length=128, unique=True)

    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="mfr_name_ci_unique")]

    def __str__(self):
        return self.name


class DeviceModel(models.Model):
    manufacturer = models.ForeignKey(
        Manufacturer, verbose_name="Производитель", on_delete=models.PROTECT, related_name="models"
    )
    name = models.CharField("Модель", max_length=128)
    DEVICE_TYPES = [("printer", "Принтер/МФУ"), ("scanner", "Сканер"), ("other", "Другое")]
    device_type = models.CharField("Тип устройства", max_length=16, choices=DEVICE_TYPES, default="printer")
    has_network_port = models.BooleanField(
        "Наличие сетевого порта", default=False, db_index=True, help_text="Устройство имеет встроенный сетевой порт"
    )

    class Meta:
        verbose_name = "Модель оборудования"
        verbose_name_plural = "Модели оборудования"
        unique_together = [("manufacturer", "name")]
        indexes = [models.Index(fields=["manufacturer", "name"])]
        ordering = ["manufacturer__name", "name"]

    def __str__(self):
        return f"{self.manufacturer} {self.name}"


# ─── Справочник картриджей ─────────────────────────────────────────────────────


class Cartridge(models.Model):
    """Картридж для принтера"""

    name = models.CharField("Название картриджа", max_length=128)
    part_number = models.CharField("Артикул", max_length=64, blank=True, help_text="Заводской артикул")
    color = models.CharField(
        "Цвет",
        max_length=16,
        choices=[
            ("black", "Черный"),
            ("cyan", "Голубой"),
            ("magenta", "Пурпурный"),
            ("yellow", "Желтый"),
            ("color", "Цветной"),
            ("other", "Другой"),
        ],
        default="black",
    )
    capacity = models.CharField("Ресурс", max_length=64, blank=True, help_text="Например: 3000 стр.")
    is_active = models.BooleanField("Активен", default=True, db_index=True)
    comment = models.TextField("Комментарий", blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Картридж"
        verbose_name_plural = "Картриджи"
        ordering = ["name", "part_number"]
        constraints = [
            models.UniqueConstraint(Lower("name"), Lower("part_number"), name="cartridge_name_part_unique_ci")
        ]

    def __str__(self):
        parts = [self.name]
        if self.part_number:
            parts.append(f"({self.part_number})")
        if self.color and self.color != "black":
            parts.append(f"- {self.get_color_display()}")
        return " ".join(parts)


class DeviceModelCartridge(models.Model):
    """Связь модели устройства с картриджами (Many-to-Many с дополнительными полями)"""

    device_model = models.ForeignKey(
        DeviceModel, verbose_name="Модель устройства", on_delete=models.CASCADE, related_name="model_cartridges"
    )
    cartridge = models.ForeignKey(
        Cartridge, verbose_name="Картридж", on_delete=models.CASCADE, related_name="compatible_models"
    )
    is_primary = models.BooleanField(
        "Основной", default=False, help_text="Основной/рекомендуемый картридж для этой модели"
    )
    comment = models.CharField("Примечание", max_length=255, blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Совместимость картриджа"
        verbose_name_plural = "Совместимость картриджей"
        unique_together = [("device_model", "cartridge")]
        ordering = ["-is_primary", "cartridge__name"]

    def __str__(self):
        primary = " [основной]" if self.is_primary else ""
        return f"{self.device_model} → {self.cartridge}{primary}"


# ─── Статусы ───────────────────────────────────────────────────────────────────


class ContractStatus(models.Model):
    name = models.CharField("Название", max_length=128, unique=True)
    color = models.CharField(
        "Цвет",
        max_length=7,
        default="#6c757d",
        validators=[RegexValidator(r"^#([0-9a-fA-F]{6})$", "HEX вида #1E90FF")],
        help_text="HEX цвет бейджа, например #0d6efd",
    )
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Статус устройства"
        verbose_name_plural = "Статусы устройства"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ─── Подрядчики ────────────────────────────────────────────────────────────────


class ServiceProvider(models.Model):
    """Организация, обслуживающая устройство по договору. У каждой свой канал приёма заявок."""

    OKDESK = "okdesk"
    NONE = "none"
    ISSUE_TRACKER_CHOICES = [
        (OKDESK, "Okdesk"),
        (NONE, "Интеграция не подключена"),
    ]

    name = models.CharField("Подрядчик", max_length=128, unique=True)
    code = models.SlugField("Код", max_length=32, unique=True, help_text="Латиницей, например amb или tonex")
    issue_tracker = models.CharField(
        "Приём заявок",
        max_length=16,
        choices=ISSUE_TRACKER_CHOICES,
        default=NONE,
        help_text="Через какую интеграцию подаются заявки по устройствам этого подрядчика",
    )
    support_email = models.EmailField(
        "Почта сервис-деска",
        blank=True,
        help_text="Адрес получателя для письма-заявки. Пусто — письмо по устройствам подрядчика не формируется",
    )
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Подрядчик"
        verbose_name_plural = "Подрядчики"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="provider_name_ci_unique")]

    def __str__(self):
        return self.name


# ─── Устройства по договору ───────────────────────────────────────────────────


class ContractDevice(models.Model):
    # координаты
    organization = models.ForeignKey(
        Organization, verbose_name="Организация", on_delete=models.PROTECT, related_name="contract_devices"
    )
    city = models.ForeignKey(City, verbose_name="Город", on_delete=models.PROTECT, related_name="contract_devices")
    address = models.CharField("Адрес", max_length=255)
    room_number = models.CharField("№ кабинета", max_length=128, blank=True)

    # оборудование
    model = models.ForeignKey(
        DeviceModel, verbose_name="Модель оборудования", on_delete=models.PROTECT, related_name="devices"
    )
    serial_number = models.CharField("Серийный номер", max_length=128, blank=True)

    # статус и обслуживание
    status = models.ForeignKey(ContractStatus, verbose_name="Статус", on_delete=models.PROTECT, related_name="devices")
    service_provider = models.ForeignKey(
        ServiceProvider,
        verbose_name="Подрядчик",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="devices",
        help_text="Кто обслуживает устройство по договору",
    )
    service_start_month = models.DateField(
        "Месяц принятия на обслуживание", null=True, blank=True, help_text="Месяц и год начала обслуживания устройства"
    )
    comment = models.TextField("Комментарий", blank=True)

    # связь 1:1 с опрашиваемым принтером
    printer = models.OneToOneField(
        Printer,
        verbose_name="Связанный принтер (опрос)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract_device",
        help_text="Связанный объект из опроса (если есть)",
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Устройство по договору"
        verbose_name_plural = "Устройства по договору"
        ordering = ["organization__name", "city__name", "address", "room_number"]
        indexes = [
            models.Index(fields=["organization"]),
            models.Index(fields=["city"]),
            models.Index(fields=["status"]),
            models.Index(fields=["serial_number"]),
            models.Index(fields=["service_start_month"]),
        ]
        constraints = [
            # серийник уникален в рамках организации (если заполнен), без учёта регистра
            models.UniqueConstraint(
                Lower("serial_number"),
                "organization",
                condition=Q(serial_number__isnull=False) & ~Q(serial_number=""),
                name="uq_contractdevice_org_sn_ci",
            )
        ]

    def __str__(self):
        base = f"{self.organization} • {self.city} • {self.address}"
        return f"{base} • {self.model} • SN:{self.serial_number or '—'}"

    @property
    def service_start_month_display(self):
        """Отформатированное отображение месяца принятия на обслуживание"""
        if self.service_start_month:
            return self.service_start_month.strftime("%m.%Y")
        return ""

    @property
    def okdesk_enabled(self):
        """Можно ли подать заявку по устройству через Okdesk.

        Устройства без подрядчика остались только в исторических данных: форма
        создания требует его выбрать, импорт проставляет из сессии.
        """
        if not self.service_provider_id:
            return True
        return self.service_provider.issue_tracker == ServiceProvider.OKDESK

    @property
    def support_email(self):
        """Куда уходит письмо-заявка. Пусто — у подрядчика адрес не настроен."""
        if not self.service_provider_id:
            return ""
        return self.service_provider.support_email


class ContractsAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_contracts_app", "Can access Contracts app"),
            ("export_contracts", "Can export contracts to Excel"),
            ("import_contracts", "Can bulk import contract devices"),
        ]
        app_label = "contracts"


# ─── Массовый импорт устройств ────────────────────────────────────────────────


class ImportSession(models.Model):
    """
    Пачка загрузок: пользователь добавляет несколько файлов, разбирает превью
    и применяет всё одним решением. Живёт после применения — по ней считаются
    устройства, не попавшие ни в один файл.
    """

    DRAFT = "draft"
    APPLIED = "applied"
    STATE_CHOICES = [(DRAFT, "Черновик"), (APPLIED, "Применена")]

    name = models.CharField("Название", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Создал",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract_import_sessions",
    )
    target_status = models.ForeignKey(
        ContractStatus,
        verbose_name="Статус для загружаемых устройств",
        on_delete=models.PROTECT,
        related_name="import_sessions",
    )
    service_provider = models.ForeignKey(
        ServiceProvider,
        verbose_name="Подрядчик для загружаемых устройств",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="import_sessions",
    )
    state = models.CharField("Состояние", max_length=16, choices=STATE_CHOICES, default=DRAFT, db_index=True)
    stats = models.JSONField("Итоги применения", default=dict, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    applied_at = models.DateTimeField("Применена", null=True, blank=True)

    class Meta:
        verbose_name = "Сессия импорта"
        verbose_name_plural = "Сессии импорта"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or 'Импорт'} от {self.created_at:%d.%m.%Y %H:%M}"


class ImportFile(models.Model):
    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="files")
    original_name = models.CharField("Имя файла", max_length=255)
    sheet_name = models.CharField("Лист", max_length=255, blank=True)
    rows_total = models.PositiveIntegerField("Строк разобрано", default=0)
    uploaded_at = models.DateTimeField("Загружен", auto_now_add=True)

    class Meta:
        verbose_name = "Файл импорта"
        verbose_name_plural = "Файлы импорта"
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name


class ImportRow(models.Model):
    NEW = "new"
    MATCH = "match"
    MOVED = "moved"
    DUP_IN_FILE = "dup_in_file"
    ERROR = "error"
    CLASSIFICATION_CHOICES = [
        (NEW, "Новое устройство"),
        (MATCH, "Обновление"),
        (MOVED, "Серийник за другой организацией"),
        (DUP_IN_FILE, "Дубль серийника в пачке"),
        (ERROR, "Ошибка"),
    ]

    PENDING = "pending"
    APPLY = "apply"
    SKIP = "skip"
    DECISION_CHOICES = [(PENDING, "Не решено"), (APPLY, "Применить"), (SKIP, "Пропустить")]

    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="rows")
    file = models.ForeignKey(ImportFile, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField("Строка в файле")

    raw = models.JSONField("Значения из файла", default=dict)
    sn_lower = models.CharField("Серийник (нормализованный)", max_length=128, blank=True)
    resolved = models.JSONField("Найденные справочники", default=dict, blank=True)

    classification = models.CharField("Класс", max_length=16, choices=CLASSIFICATION_CHOICES, default=NEW)
    errors = models.JSONField("Ошибки", default=list, blank=True)
    warnings = models.JSONField("Предупреждения", default=list, blank=True)
    matched_device = models.ForeignKey(
        ContractDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    decision = models.CharField("Решение", max_length=16, choices=DECISION_CHOICES, default=PENDING)
    applied_device = models.ForeignKey(
        ContractDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name="import_rows"
    )
    apply_error = models.TextField("Ошибка применения", blank=True)

    class Meta:
        verbose_name = "Строка импорта"
        verbose_name_plural = "Строки импорта"
        ordering = ["file_id", "row_number"]
        indexes = [
            models.Index(fields=["session", "classification"]),
            models.Index(fields=["session", "decision"]),
            models.Index(fields=["session", "sn_lower"]),
        ]

    def __str__(self):
        return f"строка {self.row_number}: {self.raw.get('serial') or '—'}"


class AutoPollCandidate(models.Model):
    """
    Устройство из сессии импорта, которое у нас не опрашивается, но имеет сетевой порт
    по справочнику. Проверяется в GLPI: если там свежие данные — принтер можно завести
    в опрос автоматически.
    """

    GLPI_ACTIVE = "glpi_active"
    GLPI_STALE = "glpi_stale"
    NOT_FOUND = "not_found"
    NO_IP = "no_ip"
    IP_CONFLICT = "ip_conflict"
    ERROR = "error"
    STATUS_CHOICES = [
        (GLPI_ACTIVE, "Есть в GLPI, опрашивается"),
        (GLPI_STALE, "Есть в GLPI, данные устарели"),
        (NOT_FOUND, "Нет в GLPI"),
        (NO_IP, "В GLPI без IP"),
        (IP_CONFLICT, "IP занят другим принтером"),
        (ERROR, "Ошибка проверки"),
    ]

    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="autopoll_candidates")
    contract_device = models.ForeignKey(
        ContractDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name="autopoll_candidates"
    )
    serial_number = models.CharField("Серийный номер", max_length=128)

    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, db_index=True)
    glpi_printer_id = models.PositiveIntegerField("ID в GLPI", null=True, blank=True)
    glpi_name = models.CharField("Имя в GLPI", max_length=255, blank=True)
    glpi_ip = models.GenericIPAddressField("IP из GLPI", protocol="IPv4", null=True, blank=True)
    glpi_counter = models.PositiveIntegerField("Счётчик в GLPI", null=True, blank=True)
    glpi_date = models.DateTimeField("Последний опрос в GLPI", null=True, blank=True)

    verify_ok = models.BooleanField("Пробный опрос удался", null=True, blank=True)
    verify_message = models.TextField("Результат пробного опроса", blank=True)
    verified_at = models.DateTimeField("Когда пробовали опросить", null=True, blank=True)

    created_printer = models.ForeignKey(
        Printer, null=True, blank=True, on_delete=models.SET_NULL, related_name="autopoll_candidates"
    )
    error = models.TextField("Ошибка", blank=True)
    checked_at = models.DateTimeField("Проверен", auto_now=True)

    class Meta:
        verbose_name = "Кандидат на автоопрос"
        verbose_name_plural = "Кандидаты на автоопрос"
        ordering = ["serial_number"]
        constraints = [
            models.UniqueConstraint(fields=["session", "serial_number"], name="uniq_autopoll_session_serial"),
        ]

    def __str__(self):
        return f"{self.serial_number} ({self.get_status_display()})"
