from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from inventory.models import Organization, Printer

class City(models.Model):
    name = models.CharField(max_length=128, unique=True)
    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), name="city_name_ci_unique")]
    def __str__(self): return self.name

class Manufacturer(models.Model):
    name = models.CharField(max_length=128, unique=True)
    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), name="mfr_name_ci_unique")]
    def __str__(self): return self.name

class DeviceModel(models.Model):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=128)
    DEVICE_TYPES = [("printer", "Принтер/МФУ"), ("scanner", "Сканер"), ("other", "Другое")]
    device_type = models.CharField(max_length=16, choices=DEVICE_TYPES, default="printer")
    class Meta:
        unique_together = [("manufacturer", "name")]
        indexes = [models.Index(fields=["manufacturer", "name"])]
    def __str__(self): return f"{self.manufacturer} {self.name}"

class ContractStatus(models.Model):
    name = models.CharField("Статус", max_length=128, unique=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), name="contractstatus_name_ci_unique")]
    def __str__(self): return self.name

class ContractDevice(models.Model):
    # координаты
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="contract_devices")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="contract_devices")
    address = models.CharField("Адрес", max_length=255)
    room_number = models.CharField("№ кабинета", max_length=128, blank=True)

    # оборудование
    model = models.ForeignKey(DeviceModel, on_delete=models.PROTECT, related_name="devices")
    serial_number = models.CharField("Серийный номер", max_length=128, blank=True)

    # статус
    status = models.ForeignKey(ContractStatus, on_delete=models.PROTECT, related_name="devices")
    comment = models.TextField("Комментарий", blank=True)

    # связь 1:1 с опрашиваемым принтером
    printer = models.OneToOneField(
        Printer, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="contract_device", help_text="Связанный объект из опроса (если есть)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization"]),
            models.Index(fields=["city"]),
            models.Index(fields=["status"]),
            models.Index(fields=["serial_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("serial_number"), "organization",
                condition=Q(serial_number__isnull=False) & ~Q(serial_number=""),
                name="uq_contractdevice_org_sn_ci"
            )
        ]

    def __str__(self):
        base = f"{self.organization} • {self.city} • {self.address}"
        return f"{base} • {self.model} • SN:{self.serial_number or '—'}"
