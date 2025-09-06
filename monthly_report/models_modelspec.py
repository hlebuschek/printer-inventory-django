from django.db import models
from django.utils.translation import gettext_lazy as _

class PaperFormat(models.TextChoices):
    A4_ONLY = "A4", _("Только A4")
    A3_ONLY = "A3", _("Только A3")
    A4_A3   = "A4A3", _("A4 и A3")

class PrinterModelSpec(models.Model):
    # Сопоставляем по текстовому названию модели, которое уже хранится в MonthlyReport.equipment_model
    model_name   = models.CharField(_("Модель оборудования"), max_length=128, unique=True)
    is_color     = models.BooleanField(_("Цветной аппарат"), default=False)
    paper_format = models.CharField(_("Формат бумаги"), max_length=4, choices=PaperFormat.choices, default=PaperFormat.A4_A3)
    enforce      = models.BooleanField(_("Применять ограничения"), default=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Правило для модели")
        verbose_name_plural = _("Правила для моделей")

    def __str__(self) -> str:
        return f"{self.model_name} | {'Color' if self.is_color else 'Mono'} | {self.paper_format}"
