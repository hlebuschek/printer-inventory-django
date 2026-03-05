from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class PaperFormat(models.TextChoices):
    A4_ONLY = "A4", _("Только A4")
    A3_ONLY = "A3", _("Только A3")
    A4_A3 = "A4A3", _("A4 и A3")


class PrinterModelSpec(models.Model):
    # Сопоставляем по текстовому названию модели, которое уже хранится в MonthlyReport.equipment_model
    model_name = models.CharField(_("Модель оборудования"), max_length=128, unique=True)
    is_color = models.BooleanField(_("Цветной аппарат"), default=False)
    paper_format = models.CharField(
        _("Формат бумаги"), max_length=4, choices=PaperFormat.choices, default=PaperFormat.A4_A3
    )
    enforce = models.BooleanField(_("Применять ограничения"), default=True)
    allow_manual_edit = models.BooleanField(
        _("Разрешить ручное редактирование"),
        default=False,
        help_text=_("Разрешить редактирование даже при наличии автоопроса (для моделей с ненадёжным SNMP)"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Правило для модели")
        verbose_name_plural = _("Правила для моделей")

    def __str__(self) -> str:
        return f"{self.model_name} | {'Color' if self.is_color else 'Mono'} | {self.paper_format}"


class SerialEditOverride(models.Model):
    serial_number = models.CharField(
        _("Серийный номер"),
        max_length=100,
        unique=True,
        db_index=True,
    )
    allow_manual_edit = models.BooleanField(
        _("Разрешить ручное редактирование"),
        default=True,
        help_text=_("True = разблокировать, False = принудительно заблокировать"),
    )
    expires_at = models.DateTimeField(
        _("Действует до"),
        null=True,
        blank=True,
        help_text=_("Если задано, override автоматически истечёт после этой даты"),
    )
    reason = models.CharField(_("Причина"), max_length=255, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Создал"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Исключение по серийному номеру")
        verbose_name_plural = _("Исключения по серийным номерам")

    def __str__(self) -> str:
        status = "разрешён" if self.allow_manual_edit else "заблокирован"
        return f"{self.serial_number} — {status}"

    @property
    def is_active(self) -> bool:
        if self.expires_at is None:
            return True
        return timezone.now() < self.expires_at
