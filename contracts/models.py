from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.core.validators import RegexValidator
from inventory.models import Organization, Printer


# ─── Справочники ───────────────────────────────────────────────────────────────

class City(models.Model):
    name = models.CharField("Город", max_length=128, unique=True)

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="city_name_ci_unique")]

    def __str__(self): return self.name


class Manufacturer(models.Model):
    name = models.CharField("Производитель", max_length=128, unique=True)

    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="mfr_name_ci_unique")]

    def __str__(self): return self.name


class DeviceModel(models.Model):
    manufacturer = models.ForeignKey(
        Manufacturer, verbose_name="Производитель",
        on_delete=models.PROTECT, related_name="models"
    )
    name = models.CharField("Модель", max_length=128)
    DEVICE_TYPES = [("printer", "Принтер/МФУ"), ("scanner", "Сканер"), ("other", "Другое")]
    device_type = models.CharField("Тип устройства", max_length=16, choices=DEVICE_TYPES, default="printer")

    class Meta:
        verbose_name = "Модель оборудования"
        verbose_name_plural = "Модели оборудования"
        unique_together = [("manufacturer", "name")]
        indexes = [models.Index(fields=["manufacturer", "name"])]
        ordering = ["manufacturer__name", "name"]

    def __str__(self): return f"{self.manufacturer} {self.name}"


# ─── Статусы ───────────────────────────────────────────────────────────────────

class ContractStatus(models.Model):
    name  = models.CharField("Название", max_length=128, unique=True)
    color = models.CharField(
        "Цвет", max_length=7, default="#6c757d",
        validators=[RegexValidator(r"^#([0-9a-fA-F]{6})$", "HEX вида #1E90FF")],
        help_text="HEX цвет бейджа, например #0d6efd",
    )
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Статус устройства"
        verbose_name_plural = "Статусы устройства"
        ordering = ["name"]

    def __str__(self): return self.name


# ─── Устройства по договору ───────────────────────────────────────────────────

class ContractDevice(models.Model):
    # координаты
    organization = models.ForeignKey(
        Organization, verbose_name="Организация",
        on_delete=models.PROTECT, related_name="contract_devices"
    )
    city = models.ForeignKey(
        City, verbose_name="Город",
        on_delete=models.PROTECT, related_name="contract_devices"
    )
    address = models.CharField("Адрес", max_length=255)
    room_number = models.CharField("№ кабинета", max_length=128, blank=True)

    # оборудование
    model = models.ForeignKey(
        DeviceModel, verbose_name="Модель оборудования",
        on_delete=models.PROTECT, related_name="devices"
    )
    serial_number = models.CharField("Серийный номер", max_length=128, blank=True)

    # статус
    status = models.ForeignKey(
        ContractStatus, verbose_name="Статус",
        on_delete=models.PROTECT, related_name="devices"
    )
    comment = models.TextField("Комментарий", blank=True)

    # связь 1:1 с опрашиваемым принтером
    printer = models.OneToOneField(
        Printer, verbose_name="Связанный принтер (опрос)",
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="contract_device",
        help_text="Связанный объект из опроса (если есть)"
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
        ]
        constraints = [
            # серийник уникален в рамках организации (если заполнен), без учёта регистра
            models.UniqueConstraint(
                Lower("serial_number"), "organization",
                condition=Q(serial_number__isnull=False) & ~Q(serial_number=""),
                name="uq_contractdevice_org_sn_ci",
            )
        ]

    def __str__(self):
        base = f"{self.organization} • {self.city} • {self.address}"
        return f"{base} • {self.model} • SN:{self.serial_number or '—'}"

class ContractsAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_contracts_app", "Can access Contracts app"),
            ("export_contracts", "Can export contracts to Excel"),
        ]
        app_label = "contracts"