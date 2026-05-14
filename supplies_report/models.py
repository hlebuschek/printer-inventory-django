from django.db import models

from inventory.models import Printer

DEFAULT_SUBJECT_TEMPLATE = "{date} Состояние расходных материалов МФУ и принтеров {location}"
DEFAULT_BODY_INTRO = "Добрый день, коллеги\n" "Направляю отчет по состоянию расходных материалов МФУ и принтеров."
DEFAULT_BODY_SIGNATURE = ""


class ReportGroup(models.Model):
    """Группа принтеров, по которой формируется одно ежедневное письмо."""

    name = models.CharField("Название", max_length=200, unique=True)
    location_label = models.CharField(
        "Локация (в теме письма)",
        max_length=255,
        blank=True,
        help_text='Подставляется в {location} в теме. Например: "г. Иркутск, ул. 5й Армии, 2А".',
    )
    subject_template = models.CharField(
        "Шаблон темы",
        max_length=500,
        default=DEFAULT_SUBJECT_TEMPLATE,
        help_text="Плейсхолдеры: {date} (дд.мм.гггг), {location}.",
    )
    body_intro = models.TextField("Вступление письма", default=DEFAULT_BODY_INTRO, blank=True)
    body_signature = models.TextField("Подпись", default=DEFAULT_BODY_SIGNATURE, blank=True)
    to_emails = models.TextField(
        "Получатели To",
        blank=True,
        help_text="Список адресов через запятую или с новой строки.",
    )
    cc_emails = models.TextField(
        "Получатели Cc",
        blank=True,
        help_text="Список адресов через запятую или с новой строки.",
    )
    from_email = models.EmailField(
        "Адрес отправителя",
        blank=True,
        help_text="Если пусто — будет использован email пользователя, скачавшего письмо.",
    )
    stale_threshold_hours = models.PositiveIntegerField(
        "Порог 'устаревших' данных (часов)",
        default=24,
        help_text="Если последний успешный опрос старше N часов, в письме появится пометка с датой.",
    )
    is_active = models.BooleanField("Активна", default=True, db_index=True)

    # ── Автоотправка по расписанию (Этап 3) ────────────────────────────────
    auto_send_enabled = models.BooleanField(
        "Автоотправка включена",
        default=False,
        db_index=True,
        help_text="Если выключено — письмо генерируется только по кнопке.",
    )
    auto_send_time = models.TimeField(
        "Время автоотправки",
        null=True,
        blank=True,
        help_text="Локальное время (CELERY_TIMEZONE). Например 08:00.",
    )
    auto_send_weekdays = models.CharField(
        "Дни недели",
        max_length=20,
        default="1,2,3,4,5",
        help_text="Список через запятую: 1=Пн, 2=Вт, …, 7=Вс. По умолчанию — будни.",
    )
    last_sent_at = models.DateTimeField("Последняя успешная отправка", null=True, blank=True)
    last_send_error = models.TextField(
        "Последняя ошибка отправки",
        blank=True,
        default="",
        help_text="Заполняется автоматически при сбое автоотправки.",
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Группа отчёта по расходникам"
        verbose_name_plural = "Группы отчёта по расходникам"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ReportGroupItem(models.Model):
    """Принтер внутри группы с описанием расположения и пользователя для письма."""

    group = models.ForeignKey(ReportGroup, on_delete=models.CASCADE, related_name="items", verbose_name="Группа")
    printer = models.ForeignKey(
        Printer, on_delete=models.PROTECT, related_name="report_group_items", verbose_name="Принтер"
    )
    location = models.TextField(
        "Расположение",
        blank=True,
        help_text='Многострочно. Пример: "5 этаж\\nкаб. 157.1".',
    )
    additional_info = models.TextField(
        "Дополнительно",
        blank=True,
        help_text='ФИО пользователя, примечание. Пример: "Сотников А.А.\\nПриёмная Колмогорова В.В.".',
    )
    sort_order = models.IntegerField("Порядок", default=0, db_index=True)

    class Meta:
        verbose_name = "Принтер в группе отчёта"
        verbose_name_plural = "Принтеры в группе отчёта"
        unique_together = [("group", "printer")]
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.group.name}: {self.printer}"


class SuppliesReportAccess(models.Model):
    """Proxy-модель для управления правами доступа."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_supplies_report", "Доступ к отчёту по расходникам"),
            ("manage_supplies_report", "Управление группами отчёта"),
            ("download_supplies_report", "Скачивание .eml письма"),
        ]
        app_label = "supplies_report"
        verbose_name = "Отчёт по расходникам"
        verbose_name_plural = "Отчёт по расходникам"
