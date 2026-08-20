from datetime import time
from pathlib import PurePosixPath
from uuid import uuid4

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from inventory.models import Organization, Printer

# ─── Справочники ───────────────────────────────────────────────────────────────


class WorkSchedule(models.Model):
    """График работы объекта. Задаёт рабочие часы, в которых считаются нормативы SLA."""

    name = models.CharField("Название", max_length=128, unique=True)
    work_start = models.TimeField("Начало рабочего дня", default=time(8, 0))
    work_end = models.TimeField("Конец рабочего дня", default=time(17, 0))
    weekdays = models.CharField(
        "Рабочие дни недели",
        max_length=7,
        default="12345",
        validators=[RegexValidator(r"^[1-7]{1,7}$", "Цифры 1-7 без разделителей: 1 — понедельник, 7 — воскресенье")],
        help_text="Цифры дней недели без разделителей: 1 — понедельник, 7 — воскресенье. Например, 12345",
    )
    short_day_minutes = models.PositiveSmallIntegerField(
        "Сокращение предпраздничного дня, мин",
        default=60,
        help_text="На сколько минут раньше заканчивается рабочий день накануне праздника",
    )
    is_default = models.BooleanField(
        "График по умолчанию",
        default=False,
        help_text="Применяется, когда график не задан ни для устройства, ни для города",
    )

    class Meta:
        verbose_name = "График работы"
        verbose_name_plural = "Графики работы"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["is_default"], condition=Q(is_default=True), name="single_default_schedule")
        ]

    def __str__(self):
        return self.name

    @property
    def weekday_set(self):
        return {int(d) for d in self.weekdays}

    @classmethod
    def default(cls):
        return cls.objects.filter(is_default=True).first()

    def hours_for_weekday(self, weekday):
        """Начало и конец рабочего дня для дня недели с учётом исключений."""
        for exception in self.day_exceptions.all():
            if exception.weekday == weekday:
                return exception.work_start, exception.work_end
        return self.work_start, self.work_end


class WorkScheduleDay(models.Model):
    """День недели, который работает не по общему времени графика.

    Нужен для реальных объектов вида «пн-чт до 17:15, пятница до 16:00»:
    в графике задаётся основное время, а короткий день выносится сюда.
    """

    WEEKDAYS = [
        (1, "Понедельник"),
        (2, "Вторник"),
        (3, "Среда"),
        (4, "Четверг"),
        (5, "Пятница"),
        (6, "Суббота"),
        (7, "Воскресенье"),
    ]

    schedule = models.ForeignKey(
        WorkSchedule, verbose_name="График", on_delete=models.CASCADE, related_name="day_exceptions"
    )
    weekday = models.PositiveSmallIntegerField("День недели", choices=WEEKDAYS)
    work_start = models.TimeField("Начало рабочего дня")
    work_end = models.TimeField("Конец рабочего дня")

    class Meta:
        verbose_name = "Особый день графика"
        verbose_name_plural = "Особые дни графика"
        ordering = ["schedule", "weekday"]
        constraints = [
            models.UniqueConstraint(fields=["schedule", "weekday"], name="uniq_schedule_weekday"),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()}: {self.work_start:%H:%M}-{self.work_end:%H:%M}"


class ProductionCalendarDay(models.Model):
    """Отклонение от обычного графика по производственному календарю РФ."""

    HOLIDAY = "holiday"
    SHORT = "short"
    WORKING_WEEKEND = "working"
    KINDS = [
        (HOLIDAY, "Нерабочий праздничный день"),
        (SHORT, "Предпраздничный сокращённый день"),
        (WORKING_WEEKEND, "Рабочий выходной (перенос)"),
    ]

    date = models.DateField("Дата", unique=True)
    kind = models.CharField("Тип дня", max_length=16, choices=KINDS, db_index=True)
    note = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "День производственного календаря"
        verbose_name_plural = "Производственный календарь"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%d.%m.%Y} — {self.get_kind_display()}"


class City(models.Model):
    # Часовой пояс нужен, чтобы нормативные сроки считались по местному времени объекта,
    # а не по времени сервера: обслуживаемые города лежат в поясах от Москвы до Иркутска.
    TIMEZONES = [
        ("Europe/Kaliningrad", "Калининград (UTC+2)"),
        ("Europe/Moscow", "Москва (UTC+3)"),
        ("Europe/Samara", "Самара (UTC+4)"),
        ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
        ("Asia/Omsk", "Омск (UTC+6)"),
        ("Asia/Krasnoyarsk", "Красноярск (UTC+7)"),
        ("Asia/Irkutsk", "Иркутск (UTC+8)"),
        ("Asia/Yakutsk", "Якутск (UTC+9)"),
        ("Asia/Vladivostok", "Владивосток (UTC+10)"),
        ("Asia/Magadan", "Магадан (UTC+11)"),
        ("Asia/Kamchatka", "Камчатка (UTC+12)"),
    ]

    name = models.CharField("Город", max_length=128, unique=True)
    timezone = models.CharField("Часовой пояс", max_length=32, choices=TIMEZONES, default="Asia/Irkutsk")
    sla_standard_hours = models.PositiveSmallIntegerField(
        "Норматив устранения инцидента, рабочих часов",
        default=16,
        help_text="По ТЗ: 8 часов для городов присутствия сервисной службы, 16 — для остальных",
    )
    work_schedule = models.ForeignKey(
        WorkSchedule,
        verbose_name="График работы",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cities",
    )

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
    EMAIL = "email"
    JOURNAL = "journal"
    NONE = "none"
    ISSUE_TRACKER_CHOICES = [
        (OKDESK, "Okdesk (API)"),
        (EMAIL, "Письмо на почту сервис-деска"),
        (JOURNAL, "Только журнал — подрядчику не отправляем"),
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
    collects_urgency = models.BooleanField(
        "Спрашивать срочность",
        default=True,
        help_text=(
            "Подрядчик принимает срочность и обещает по ней норматив: поле показывается при подаче заявки "
            "и уходит ему в теле. Выключено — не спрашиваем и не передаём"
        ),
    )
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Подрядчик"
        verbose_name_plural = "Подрядчики"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="provider_name_ci_unique")]

    def __str__(self):
        return self.name


# ─── Договоры ──────────────────────────────────────────────────────────────────


class Contract(models.Model):
    """Договор на покопийную печать. Цена отпечатка своя у каждого договора."""

    number = models.CharField("Номер договора", max_length=64, unique=True)
    name = models.CharField("Название", max_length=255, blank=True)
    provider = models.ForeignKey(
        ServiceProvider,
        verbose_name="Подрядчик",
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    valid_from = models.DateField("Действует с", null=True, blank=True)
    valid_to = models.DateField("Действует по", null=True, blank=True)

    price_a4_bw = models.DecimalField(
        "Цена отпечатка A4 ч/б, ₽", max_digits=10, decimal_places=4, default=0, validators=[MinValueValidator(0)]
    )
    price_a4_color = models.DecimalField(
        "Цена отпечатка A4 цвет, ₽", max_digits=10, decimal_places=4, default=0, validators=[MinValueValidator(0)]
    )
    price_a3_bw = models.DecimalField(
        "Цена отпечатка A3 ч/б, ₽", max_digits=10, decimal_places=4, default=0, validators=[MinValueValidator(0)]
    )
    price_a3_color = models.DecimalField(
        "Цена отпечатка A3 цвет, ₽", max_digits=10, decimal_places=4, default=0, validators=[MinValueValidator(0)]
    )
    vat_rate = models.DecimalField(
        "Ставка НДС, %",
        max_digits=5,
        decimal_places=2,
        default=20,
        validators=[MinValueValidator(0)],
        help_text="0 — подрядчик работает без НДС",
    )

    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Договор"
        verbose_name_plural = "Договоры"
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} • {self.name}" if self.name else self.number


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
    contract = models.ForeignKey(
        Contract,
        verbose_name="Договор",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="devices",
        help_text="По какому договору обслуживается устройство — от него зависит цена отпечатка",
    )
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
    work_schedule = models.ForeignKey(
        WorkSchedule,
        verbose_name="График работы",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devices",
        help_text="Переопределяет график города, если объект работает по особому расписанию",
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
            models.Index(fields=["contract"]),
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
    def effective_work_schedule(self):
        """График работы устройства: своё расписание → расписание города → график по умолчанию."""
        return self.resolve_work_schedule()

    def resolve_work_schedule(self, default=None):
        """То же, но с готовым графиком по умолчанию: при пересчёте месяца устройств тысячи,
        и запрос умолчания на каждое из них превращается в N+1."""
        return self.work_schedule or self.city.work_schedule or default or WorkSchedule.default()

    @property
    def can_create_request(self):
        """Есть ли у подрядчика устройства канал подачи заявок (Okdesk API или почта).

        Устройства без подрядчика остались только в исторических данных: форма
        создания требует его выбрать, импорт проставляет из сессии.
        """
        if not self.service_provider_id:
            return True
        return self.service_provider.issue_tracker != ServiceProvider.NONE

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
    contract = models.ForeignKey(
        Contract,
        verbose_name="Договор для загружаемых устройств",
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


# ─── Журнал заявок ────────────────────────────────────────────────────────────


def service_act_upload_to(instance, filename):
    """Имя файла собираем сами: пользовательское в путь не пускаем, номер заявки уникален."""
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()[:10]
    return f"service-acts/{instance.registered_at:%Y}/{instance.number}{suffix}"


class ServiceRequest(models.Model):
    """Заявка подрядчику — наш собственный учёт для показателей K1/K2.

    Отдельно от OkdeskIssue: та таблица зеркалит Okdesk и перезаписывается синхронизацией,
    а с сентября 2026 заявки уходят новому подрядчику почтой, где чужих номеров и сроков нет.
    Нормативный срок считаем сами по графику объекта, а не берём из системы подрядчика.
    """

    OPEN = "open"
    RESTORED = "restored"
    CLOSED = "closed"
    REJECTED = "rejected"
    STATUSES = [
        (OPEN, "Открыта"),
        (RESTORED, "Ждёт акта"),
        (CLOSED, "Выполнена"),
        (REJECTED, "Отклонена"),
    ]

    device = models.ForeignKey(
        ContractDevice, verbose_name="Оборудование", on_delete=models.PROTECT, related_name="service_requests"
    )
    service_provider = models.ForeignKey(
        ServiceProvider,
        verbose_name="Подрядчик",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
        help_text="Кто обслуживал устройство на момент подачи заявки",
    )
    external_number = models.CharField(
        "Номер у подрядчика",
        max_length=64,
        blank=True,
        help_text="Номер обращения в системе подрядчика: id заявки Okdesk или номер из ответного письма",
    )

    description = models.TextField("Описание заявки")
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Инициатор",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
    )
    initiator_contacts = models.TextField(
        "Контактные данные",
        blank=True,
        help_text="Телефон инициатора и контактных лиц на объекте свободным текстом",
    )

    registered_at = models.DateTimeField("Зарегистрирована", db_index=True)

    # Два независимых признака: заявка может влиять на K2, не останавливая печать
    # (посторонний шум, угроза инцидента), и наоборот — простой по причине вне SLA.
    stops_printing = models.BooleanField(
        "Печать остановлена", default=True, help_text="Простой идёт в показатель доступности K1"
    )
    counts_in_sla = models.BooleanField(
        "Учитывать в K2", default=True, help_text="Заявка об инциденте с нормативным сроком устранения"
    )
    is_critical = models.BooleanField(
        "Критичный инцидент", default=False, help_text="Норматив устранения 4 рабочих часа вместо городского"
    )

    # Снимок условий на момент подачи: график объекта и норматив города могут поменяться,
    # но пересчитывать закрытый период задним числом нельзя.
    sla_hours = models.PositiveSmallIntegerField("Норматив устранения, рабочих часов", null=True, blank=True)
    schedule_snapshot = models.ForeignKey(
        WorkSchedule,
        verbose_name="График на момент подачи",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
    )
    deadline_at = models.DateTimeField("Нормативный срок", null=True, blank=True, db_index=True)

    restored_at = models.DateTimeField("Работоспособность восстановлена", null=True, blank=True)
    closed_at = models.DateTimeField(
        "Выполнена",
        null=True,
        blank=True,
        help_text="По ТЗ заявка выполнена только после получения скана технического акта",
    )
    status = models.CharField("Статус", max_length=16, choices=STATUSES, default=OPEN, db_index=True)

    act_number = models.CharField("Номер технического акта", max_length=64, blank=True)
    act_scan = models.FileField(
        "Скан технического акта",
        upload_to=service_act_upload_to,
        blank=True,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "tif", "tiff"])],
        help_text="Приложение к письму подрядчика о восстановлении работоспособности (п. 6.6.4 ТЗ)",
    )
    closing_message = models.ForeignKey(
        "ServiceRequestMessage",
        verbose_name="Письмо о восстановлении",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_requests",
        help_text="Заполнено, если заявку закрыло формальное письмо подрядчика, а не человек",
    )

    # Учёт у нас контрольный: по п. 6.5.2 ТЗ фактическое время фиксирует Исполнитель,
    # поэтому его цифры храним рядом со своими, а не вместо них.
    provider_restored_at = models.DateTimeField(
        "Восстановлено по данным подрядчика",
        null=True,
        blank=True,
        help_text="Время из письма или технического акта подрядчика",
    )
    provider_downtime_hours = models.DecimalField(
        "Простой по данным подрядчика, рабочих часов",
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )

    reopened_from = models.ForeignKey(
        "self",
        verbose_name="Переоткрытие заявки",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reopens",
        help_text="При повторном обращении по тем же основаниям срок считается от первого письма",
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Заявка подрядчику"
        verbose_name_plural = "Журнал заявок"
        ordering = ["-registered_at"]
        indexes = [
            models.Index(fields=["device", "-registered_at"]),
            models.Index(fields=["status", "deadline_at"]),
        ]
        permissions = [
            ("create_service_request", "Может подавать заявки подрядчику"),
            ("close_service_request", "Может отмечать восстановление и загружать технический акт"),
            ("export_service_requests", "Может выгружать журнал заявок в Excel"),
        ]

    def __str__(self):
        return f"{self.number} • {self.device.serial_number or self.device.model}"

    @property
    def number(self):
        """Наш номер заявки. Выводится из года и id, поэтому стабилен и не требует счётчика."""
        if not self.pk:
            return "б/н"
        return f"{self.registered_at:%Y}-{self.pk:05d}"

    @property
    def urgency_label(self):
        """Человекочитаемая срочность по флагам — уходит подрядчику в теле заявки."""
        if not self.stops_printing and not self.counts_in_sla:
            return "Плановая (в резерв) — срок не нормируется"
        if self.is_critical:
            base = "КРИТИЧНАЯ — печать остановлена"
        elif self.stops_printing:
            base = "Обычная — печать остановлена"
        else:
            base = "Печать работает"
        hours = self.sla_hours
        if hours is None and self.device.city_id:
            hours = self.resolve_sla_hours()
        return f"{base}, норматив {hours} раб. ч" if hours else base

    def resolve_sla_hours(self):
        """Норматив устранения: 4 часа для критичных, иначе норматив города по Таблице №2 ТЗ."""
        return 4 if self.is_critical else self.device.city.sla_standard_hours

    def recalculate_deadline(self):
        """Пересчитывает нормативный срок и снимок условий по графику объекта."""
        from .services_working_hours import calculator_for_device

        # По п.6.6.1 ТЗ при повторном обращении по тем же основаниям
        # срок отсчитывается от первого письма, а не от переоткрытия.
        if self.reopened_from_id:
            origin = self.reopened_from
            self.sla_hours = origin.sla_hours
            self.schedule_snapshot = origin.schedule_snapshot
            self.deadline_at = origin.deadline_at
            return

        calculator = calculator_for_device(self.device)
        self.sla_hours = self.resolve_sla_hours()
        self.schedule_snapshot = calculator.schedule
        self.deadline_at = calculator.add_working_hours(self.registered_at, self.sla_hours)

    def save(self, *args, **kwargs):
        if self.deadline_at is None and self.registered_at:
            self.recalculate_deadline()

        if self.status != self.REJECTED:
            if self.closed_at:
                self.status = self.CLOSED
            elif self.restored_at:
                self.status = self.RESTORED
            else:
                self.status = self.OPEN

        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Просрочена ли заявка. Открытая заявка просрочена, как только срок прошёл."""
        if self.deadline_at is None or self.status == self.REJECTED:
            return False
        return (self.closed_at or timezone.now()) > self.deadline_at

    @property
    def restoration_discrepancy_hours(self):
        """На сколько часов наша отметка восстановления расходится с данными подрядчика.

        Положительное значение — подрядчик считает, что восстановил раньше, чем увидели мы.
        """
        if not self.restored_at or not self.provider_restored_at:
            return None
        return round((self.restored_at - self.provider_restored_at).total_seconds() / 3600, 2)

    def downtime_hours(self, until=None, since=None, calculator=None):
        """Время недоступности печати в рабочих часах — вклад заявки в показатель D.

        `since`/`until` обрезают простой окном отчётного периода: заявка, открытая
        в конце месяца и закрытая в следующем, должна дать каждому месяцу только
        свою часть, иначе один простой уменьшит K1 дважды.
        """
        if not self.stops_printing:
            return 0.0

        from .services_working_hours import WorkingTimeCalculator

        end = self.restored_at or timezone.now()
        if until is not None:
            end = min(end, until)
        start = max(self.registered_at, since) if since is not None else self.registered_at

        if calculator is None:
            schedule = self.schedule_snapshot or self.device.effective_work_schedule
            if schedule is None:
                return 0.0
            calculator = WorkingTimeCalculator(schedule, self.device.city.timezone)

        return calculator.working_hours_between(start, end)


# ─── Переписка по заявке ───────────────────────────────────────────────────────


def service_mail_upload_to(instance, filename):
    """Вложение кладём под id письма со случайным именем: имя из письма в путь не пускаем."""
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()[:10]
    return f"service-mail/{instance.message_id}/{uuid4().hex}{suffix}"


class ServiceRequestMessage(models.Model):
    """Сообщение по заявке: наше исходящее или ответ подрядчика.

    Хранится как есть, без разбора смысла: реальная переписка ведётся живой речью
    («завтра приедет мастер», «картридж получен, закройте»), и надёжно вывести из неё
    статус нельзя. Цифры отчёта меняет человек или формальное письмо по п. 6.6.4 ТЗ.

    Канал доставки — как у подачи заявки: сегодня почта, у подрядчика с API это будут
    комментарии его системы. Лента, права и интерфейс от канала не зависят, поэтому
    почтовые заголовки лежат отдельными полями и у других каналов просто пустые.

    Сообщение без узнанной заявки остаётся с пустым `service_request` — такие видны
    отдельным списком и привязываются вручную, иначе ответ подрядчика теряется.
    """

    OUTGOING = "out"
    INCOMING = "in"
    DIRECTIONS = [(OUTGOING, "Исходящее"), (INCOMING, "Входящее")]

    service_request = models.ForeignKey(
        ServiceRequest,
        verbose_name="Заявка",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    channel = models.CharField(
        "Канал",
        max_length=16,
        choices=ServiceProvider.ISSUE_TRACKER_CHOICES,
        default=ServiceProvider.EMAIL,
        db_index=True,
    )
    direction = models.CharField("Направление", max_length=3, choices=DIRECTIONS, db_index=True)

    external_id = models.CharField(
        "Идентификатор у источника",
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Message-ID письма или id комментария в системе подрядчика",
    )
    # Заголовок треда нужен, чтобы узнать ответ, когда подрядчик пишет
    # со своей темой без нашего номера заявки. Только для почты.
    in_reply_to = models.CharField("In-Reply-To", max_length=255, blank=True)

    subject = models.CharField("Тема", max_length=500, blank=True)
    from_email = models.CharField("От кого", max_length=320, blank=True)
    to_emails = models.CharField("Кому", max_length=1000, blank=True)
    body_text = models.TextField("Текст сообщения", blank=True)

    sent_at = models.DateTimeField("Дата сообщения", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("Получено системой", auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение по заявке"
        verbose_name_plural = "Переписка по заявкам"
        ordering = ["sent_at", "id"]
        indexes = [models.Index(fields=["service_request", "sent_at"])]
        constraints = [
            # Приём может забрать одно сообщение дважды (сбой при пометке прочитанным),
            # а дубль в ленте выглядит как ещё один ответ подрядчика.
            models.UniqueConstraint(
                fields=["channel", "external_id"],
                condition=~Q(external_id=""),
                name="uniq_service_message_external_id",
            )
        ]

    def __str__(self):
        return f"{self.get_direction_display()}: {self.subject or 'без темы'}"


class ServiceRequestAttachment(models.Model):
    """Вложение сообщения. Скан техакта попадает сюда же, но в заявку его переносит человек."""

    message = models.ForeignKey(
        ServiceRequestMessage, verbose_name="Письмо", on_delete=models.CASCADE, related_name="attachments"
    )
    # Пустой файл — вложение Okdesk, от которого доступны только метаданные: сами файлы лежат
    # в отдельном хранилище (okdesk.storage.yandexcloud.net), доступ к нему есть не из каждой сети.
    # Идентификаторы Okdesk хранятся, чтобы докачать файл позже без повторного импорта заявки.
    file = models.FileField("Файл", upload_to=service_mail_upload_to, blank=True)
    filename = models.CharField("Имя файла", max_length=255)
    content_type = models.CharField("Тип содержимого", max_length=100, blank=True)
    size = models.PositiveIntegerField("Размер, байт", default=0)
    okdesk_issue_id = models.PositiveBigIntegerField("Заявка Okdesk", null=True, blank=True)
    okdesk_attachment_id = models.PositiveBigIntegerField("Вложение Okdesk", null=True, blank=True)

    class Meta:
        verbose_name = "Вложение письма"
        verbose_name_plural = "Вложения писем"
        ordering = ["id"]

    def __str__(self):
        return self.filename


class ServiceRequestSubscription(models.Model):
    """Кто получает уведомления об ответах подрядчика по заявке.

    Инициатор подписывается сам при подаче: ответ подрядчика адресован ему.
    Остальные читают журнал свободно и без уведомлений — подписка нужна только
    тому, кто хочет видеть заявку в колокольчике. Прочитанность живёт в самих
    уведомлениях (`access.Notification`), здесь её нет.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="service_request_subscriptions",
    )
    service_request = models.ForeignKey(
        ServiceRequest, verbose_name="Заявка", on_delete=models.CASCADE, related_name="subscriptions"
    )
    created_at = models.DateTimeField("Подписан", auto_now_add=True)

    class Meta:
        verbose_name = "Подписка на заявку"
        verbose_name_plural = "Подписки на заявки"
        constraints = [models.UniqueConstraint(fields=["user", "service_request"], name="uniq_request_subscriber")]

    def __str__(self):
        return f"{self.user} → {self.service_request.number}"
