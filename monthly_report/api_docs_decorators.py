# monthly_report/api_docs_decorators.py
"""
OpenAPI декораторы для существующих API views.
Добавляет документацию drf-spectacular к Django function-based views.
"""
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.fields import BooleanField, CharField, IntegerField

# Импорт request serializers
from .serializers import (
    UpdateCountersRequestSerializer,
    ResetManualRequestSerializer,
    SerialOverrideRequestSerializer,
    ToggleMonthPublishedRequestSerializer,
    ToggleAutoSyncRequestSerializer,
    DeleteMonthRequestSerializer,
    GLPIExportStartRequestSerializer,
)


# ──────────────────────────────────────────────────────────────────────────────
# SIMPLE SCHEMAS (non-nested, safe to use in ListField)
# ──────────────────────────────────────────────────────────────────────────────

# Базовый schema для успеха/ошибки
OK_RESPONSE_SCHEMA = inline_serializer(
    name="OkResponse",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
    },
)

# Schema для элемента списка месяцев (простые поля, без вложенных списков)
MONTH_ITEM_SCHEMA = inline_serializer(
    name="MonthItem",
    fields={
        "month": CharField(help_text="Месяц в формате YYYY-MM"),
        "month_name": CharField(help_text="Название месяца на русском"),
        "count": IntegerField(help_text="Количество записей"),
        "edit_until": CharField(help_text="Дедлайн редактирования (ISO)", allow_null=True, required=False),
        "is_editable": BooleanField(help_text="Доступен для редактирования"),
        "is_published": BooleanField(help_text="Опубликован"),
        "auto_sync_enabled": BooleanField(help_text="Включена автосинхронизация"),
        "completion_percent": IntegerField(help_text="Процент заполненности", allow_null=True, required=False),
        "has_prev_month": BooleanField(help_text="Есть предыдущий месяц"),
        "prev_month": CharField(help_text="Предыдущий месяц (YYYY-MM)", allow_null=True, required=False),
    },
)

# Schema для элемента в diff (простые поля)
DIFF_ITEM_SCHEMA = inline_serializer(
    name="DiffItem",
    fields={
        "inventory_number": CharField(help_text="Инвентарный номер"),
        "serial_number": CharField(help_text="Серийный номер"),
        "equipment_model": CharField(help_text="Модель оборудования"),
        "organization": CharField(help_text="Организация"),
        "branch": CharField(help_text="Филиал"),
        "city": CharField(help_text="Город"),
        "address": CharField(help_text="Адрес"),
    },
)

# Schema для элемента детального отчёта
MONTH_REPORT_ITEM_SCHEMA = inline_serializer(
    name="MonthReportItem",
    fields={
        "id": IntegerField(help_text="ID записи"),
        "organization": CharField(help_text="Организация"),
        "branch": CharField(help_text="Филиал"),
        "city": CharField(help_text="Город"),
        "address": CharField(help_text="Адрес"),
        "equipment_model": CharField(help_text="Модель оборудования"),
        "serial_number": CharField(help_text="Серийный номер"),
        "inventory_number": CharField(help_text="Инвентарный номер"),
        "contract_number": CharField(help_text="Номер договора", allow_null=True, required=False),
        "a4_bw_start": IntegerField(help_text="A4 ч/б начало"),
        "a4_bw_end": IntegerField(help_text="A4 ч/б конец"),
        "a4_bw_end_manual": BooleanField(help_text="A4 ч/б конец (ручной)"),
        "a4_color_start": IntegerField(help_text="A4 цвет начало"),
        "a4_color_end": IntegerField(help_text="A4 цвет конец"),
        "a4_color_end_manual": BooleanField(help_text="A4 цвет конец (ручной)"),
        "a3_bw_start": IntegerField(help_text="A3 ч/б начало"),
        "a3_bw_end": IntegerField(help_text="A3 ч/б конец"),
        "a3_bw_end_manual": BooleanField(help_text="A3 ч/б конец (ручной)"),
        "a3_color_start": IntegerField(help_text="A3 цвет начало"),
        "a3_color_end": IntegerField(help_text="A3 цвет конец"),
        "a3_color_end_manual": BooleanField(help_text="A3 цвет конец (ручной)"),
        "total": IntegerField(help_text="Всего отпечатков"),
        "device_ip": CharField(help_text="IP устройства", allow_null=True, required=False),
        "notes": CharField(help_text="Заметки", allow_null=True, required=False),
    },
)

# Schema для элемента истории изменений
CHANGE_HISTORY_ITEM_SCHEMA = inline_serializer(
    name="ChangeHistoryItem",
    fields={
        "id": IntegerField(help_text="ID записи изменений"),
        "timestamp": CharField(help_text="Время изменения (ISO)"),
        "user_username": CharField(help_text="Имя пользователя"),
        "user_full_name": CharField(help_text="Полное имя пользователя"),
        "field": CharField(help_text="Имя поля"),
        "field_display": CharField(help_text="Отображаемое имя поля"),
        "old_value": IntegerField(help_text="Старое значение", allow_null=True),
        "new_value": IntegerField(help_text="Новое значение", allow_null=True),
        "change_delta": IntegerField(help_text="Разница", allow_null=True),
        "change_source": CharField(help_text="Источник изменения"),
        "ip_address": CharField(help_text="IP адрес"),
        "comment": CharField(help_text="Комментарий", allow_null=True),
    },
)

# Schema для отчёта в истории изменений
REPORT_DATA_SCHEMA = inline_serializer(
    name="ReportData",
    fields={
        "id": IntegerField(help_text="ID записи"),
        "month": CharField(help_text="Месяц (ISO)"),
        "organization": CharField(help_text="Организация"),
        "branch": CharField(help_text="Филиал"),
        "city": CharField(help_text="Город"),
        "address": CharField(help_text="Адрес"),
        "equipment_model": CharField(help_text="Модель оборудования"),
        "serial_number": CharField(help_text="Серийный номер"),
        "inventory_number": CharField(help_text="Инвентарный номер"),
        "a4_bw_start": IntegerField(help_text="A4 ч/б начало"),
        "a4_bw_end": IntegerField(help_text="A4 ч/б конец"),
        "a4_bw_end_auto": IntegerField(help_text="A4 ч/б конец (авто)"),
        "a4_bw_end_manual": BooleanField(help_text="A4 ч/б конец (ручной)"),
        "a4_color_start": IntegerField(help_text="A4 цвет начало"),
        "a4_color_end": IntegerField(help_text="A4 цвет конец"),
        "a4_color_end_auto": IntegerField(help_text="A4 цвет конец (авто)"),
        "a4_color_end_manual": BooleanField(help_text="A4 цвет конец (ручной)"),
        "a3_bw_start": IntegerField(help_text="A3 ч/б начало"),
        "a3_bw_end": IntegerField(help_text="A3 ч/б конец"),
        "a3_bw_end_auto": IntegerField(help_text="A3 ч/б конец (авто)"),
        "a3_bw_end_manual": BooleanField(help_text="A3 ч/б конец (ручной)"),
        "a3_color_start": IntegerField(help_text="A3 цвет начало"),
        "a3_color_end": IntegerField(help_text="A3 цвет конец"),
        "a3_color_end_auto": IntegerField(help_text="A3 цвет конец (авто)"),
        "a3_color_end_manual": BooleanField(help_text="A3 цвет конец (ручной)"),
        "total_prints": IntegerField(help_text="Всего отпечатков"),
    },
)

# Schema для счётчиков устройства
DEVICE_COUNTERS_SCHEMA = inline_serializer(
    name="DeviceCounters",
    fields={
        "a4_bw_start": IntegerField(help_text="A4 ч/б начало"),
        "a4_bw_end": IntegerField(help_text="A4 ч/б конец"),
        "a4_bw_end_auto": IntegerField(help_text="A4 ч/б конец (авто)"),
        "a4_bw_end_manual": BooleanField(help_text="A4 ч/б конец (ручной)"),
        "a4_color_start": IntegerField(help_text="A4 цвет начало"),
        "a4_color_end": IntegerField(help_text="A4 цвет конец"),
        "a4_color_end_auto": IntegerField(help_text="A4 цвет конец (авто)"),
        "a4_color_end_manual": BooleanField(help_text="A4 цвет конец (ручной)"),
        "a3_bw_start": IntegerField(help_text="A3 ч/б начало"),
        "a3_bw_end": IntegerField(help_text="A3 ч/б конец"),
        "a3_bw_end_auto": IntegerField(help_text="A3 ч/б конец (авто)"),
        "a3_bw_end_manual": BooleanField(help_text="A3 ч/б конец (ручной)"),
        "a3_color_start": IntegerField(help_text="A3 цвет начало"),
        "a3_color_end": IntegerField(help_text="A3 цвет конец"),
        "a3_color_end_auto": IntegerField(help_text="A3 цвет конец (авто)"),
        "a3_color_end_manual": BooleanField(help_text="A3 цвет конец (ручной)"),
    },
)

# Schema для отчёта устройства
DEVICE_REPORT_DATA_SCHEMA = inline_serializer(
    name="DeviceReportData",
    fields={
        "id": IntegerField(help_text="ID записи"),
        "organization": CharField(help_text="Организация"),
        "branch": CharField(help_text="Филиал"),
        "city": CharField(help_text="Город"),
        "address": CharField(help_text="Адрес"),
        "equipment_model": CharField(help_text="Модель оборудования"),
        "serial_number": CharField(help_text="Серийный номер"),
        "inventory_number": CharField(help_text="Инвентарный номер"),
        "counters": DEVICE_COUNTERS_SCHEMA,
    },
)

# Schema для элемента списка изменений
CHANGE_ITEM_SCHEMA = inline_serializer(
    name="ChangeItem",
    fields={
        "id": IntegerField(help_text="ID записи изменений"),
        "timestamp": CharField(help_text="Время изменения (ISO)"),
        "user_username": CharField(help_text="Имя пользователя"),
        "user_full_name": CharField(help_text="Полное имя"),
        "field_name": CharField(help_text="Имя поля"),
        "field_label": CharField(help_text="Отображаемое имя поля"),
        "old_value": IntegerField(help_text="Старое значение", allow_null=True),
        "new_value": IntegerField(help_text="Новое значение", allow_null=True),
        "change_type": CharField(help_text="Тип изменения: filled_empty/edited_auto/edited_manual"),
        "change_source": CharField(help_text="Источник изменения"),
        "ip_address": CharField(help_text="IP адрес", allow_null=True, required=False),
        "report_id": IntegerField(help_text="ID отчёта"),
        "organization": CharField(help_text="Организация"),
        "branch": CharField(help_text="Филиал"),
        "city": CharField(help_text="Город"),
        "address": CharField(help_text="Адрес"),
        "equipment_model": CharField(help_text="Модель оборудования"),
        "serial_number": CharField(help_text="Серийный номер"),
        "inventory_number": CharField(help_text="Инвентарный номер"),
    },
)

# Schema для статистики пользователя
USER_STATS_SCHEMA = inline_serializer(
    name="UserStatsItem",
    fields={
        "username": CharField(help_text="Имя пользователя"),
        "full_name": CharField(help_text="Полное имя"),
        "edited_auto_count": IntegerField(help_text="Количество отредактированных автоматических значений"),
        "filled_empty_count": IntegerField(help_text="Количество заполненных пустых полей"),
        "changes_count": IntegerField(help_text="Всего изменений уникальных устройств"),
    },
)

# Schema для синхронизации с inventory
SYNC_RESULT_SCHEMA = inline_serializer(
    name="SyncResult",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "synced": IntegerField(help_text="Количество синхронизированных записей", allow_null=True, required=False),
        "skipped": IntegerField(help_text="Количество пропущенных записей", allow_null=True, required=False),
        "errors": IntegerField(help_text="Количество ошибок", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение", allow_null=True, required=False),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "auto_sync_disabled": BooleanField(help_text="Флаг отключённой автосинхронизации", allow_null=True, required=False),
    },
)

# Schema для обновления счётчиков
UPDATE_COUNTERS_RESULT_SCHEMA = inline_serializer(
    name="UpdateCountersResult",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "locked": BooleanField(help_text="Заблокировано (дубликат серийника)", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение", allow_null=True, required=False),
        "duplicate_info": CharField(help_text="Информация о дубликате (JSON строка)", allow_null=True, required=False),
    },
)

# Schema для сброса флага ручного редактирования
RESET_MANUAL_RESULT_SCHEMA = inline_serializer(
    name="ResetManualResult",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение"),
        "new_value": IntegerField(help_text="Новое значение", allow_null=True, required=False),
    },
)

# Schema для toggle serial override
SERIAL_OVERRIDE_RESULT_SCHEMA = inline_serializer(
    name="SerialOverrideResult",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "serial_override_active": BooleanField(help_text="Активен оверрайд"),
    },
)

# Schema для toggle month published / auto sync
TOGGLE_RESULT_SCHEMA = inline_serializer(
    name="ToggleResult",
    fields={
        "success": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение", allow_null=True, required=False),
        "is_published": BooleanField(help_text="Статус публикации", allow_null=True, required=False),
        "auto_sync_enabled": BooleanField(help_text="Статус автосинхронизации", allow_null=True, required=False),
    },
)

# Schema для удаления месяца
DELETE_MONTH_RESULT_SCHEMA = inline_serializer(
    name="DeleteMonthResult",
    fields={
        "success": BooleanField(help_text="Успешность операции"),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение", allow_null=True, required=False),
        "deleted_count": IntegerField(help_text="Количество удалённых записей", allow_null=True, required=False),
        "bulk_log_id": IntegerField(help_text="ID лога массовой операции", allow_null=True, required=False),
    },
)

# Schema для запуска GLPI экспорта
GLPI_EXPORT_START_SCHEMA = inline_serializer(
    name="GLPIExportStartResponse",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "task_id": CharField(help_text="ID задачи Celery", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение", allow_null=True, required=False),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
    },
)

# Schema для статуса GLPI экспорта
GLPI_EXPORT_STATUS_SCHEMA = inline_serializer(
    name="GLPIExportStatusResponse",
    fields={
        "ok": BooleanField(help_text="Успешность операции"),
        "state": CharField(help_text="Состояние: PENDING/PROGRESS/SUCCESS/FAILURE"),
        "current": IntegerField(help_text="Текущее количество обработанных", allow_null=True, required=False),
        "total": IntegerField(help_text="Общее количество", allow_null=True, required=False),
        "percent": IntegerField(help_text="Процент выполнения", allow_null=True, required=False),
        "message": CharField(help_text="Сообщение о прогрессе", allow_null=True, required=False),
        "result": CharField(help_text="Результат (JSON строка, если завершено)", allow_null=True, required=False),
        "error": CharField(help_text="Текст ошибки", allow_null=True, required=False),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# REQUEST SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

# Request schema для обновления счётчиков
UPDATE_COUNTERS_REQUEST_SCHEMA = inline_serializer(
    name="UpdateCountersRequest",
    fields={
        "a4_bw_end": IntegerField(help_text="A4 ч/б конец", required=False),
        "a4_color_end": IntegerField(help_text="A4 цвет конец", required=False),
        "a3_bw_end": IntegerField(help_text="A3 ч/б конец", required=False),
        "a3_color_end": IntegerField(help_text="A3 цвет конец", required=False),
        "notes": CharField(help_text="Заметки", required=False, allow_null=True, allow_blank=True),
    },
)

# Request schema для сброса флага ручного редактирования
RESET_MANUAL_REQUEST_SCHEMA = inline_serializer(
    name="ResetManualRequest",
    fields={
        "field": CharField(help_text="Имя поля для сброса"),
    },
)

# Request schema для toggle serial override
SERIAL_OVERRIDE_REQUEST_SCHEMA = inline_serializer(
    name="SerialOverrideRequest",
    fields={
        "serial_number": CharField(help_text="Серийный номер"),
        "allow": BooleanField(help_text="Разрешить/запретить"),
        "mode": CharField(help_text="Режим: this_month/permanent/until_date", required=False, allow_null=True),
        "year": IntegerField(help_text="Год (для режима this_month)", required=False, allow_null=True),
        "month": IntegerField(help_text="Месяц (для режима this_month)", required=False, allow_null=True),
        "expires_at": CharField(help_text="Дата истечения (ISO) (для режима until_date)", required=False, allow_null=True),
    },
)

# Request schema для toggle month published
TOGGLE_MONTH_PUBLISHED_REQUEST_SCHEMA = inline_serializer(
    name="ToggleMonthPublishedRequest",
    fields={
        "year": IntegerField(help_text="Год"),
        "month": IntegerField(help_text="Месяц"),
        "is_published": BooleanField(help_text="Статус публикации"),
    },
)

# Request schema для toggle auto sync
TOGGLE_AUTO_SYNC_REQUEST_SCHEMA = inline_serializer(
    name="ToggleAutoSyncRequest",
    fields={
        "year": IntegerField(help_text="Год"),
        "month": IntegerField(help_text="Месяц"),
        "auto_sync_enabled": BooleanField(help_text="Включить/выключить автосинхронизацию"),
    },
)

# Request schema для удаления месяца
DELETE_MONTH_REQUEST_SCHEMA = inline_serializer(
    name="DeleteMonthRequest",
    fields={
        "year": IntegerField(help_text="Год"),
        "month": IntegerField(help_text="Месяц"),
    },
)

# Request schema для запуска GLPI экспорта
GLPI_EXPORT_START_REQUEST_SCHEMA = inline_serializer(
    name="GLPIExportStartRequest",
    fields={
        "month": CharField(help_text="Месяц в формате YYYY-MM (опционально)", required=False, allow_null=True, allow_blank=True),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

api_sync_from_inventory_schema = extend_schema(
    operation_id="monthly_report_sync_from_inventory",
    tags=["monthly_report"],
    summary="Синхронизация с inventory",
    description=(
        "Синхронизирует данные отчёта за указанный месяц с данными из inventory. "
        "Требует право sync_from_inventory и открытый месяц с включённой автосинхронизацией."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(response=SYNC_RESULT_SCHEMA, description="Результат синхронизации"),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав или месяц закрыт"),
        500: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Ошибка сервера"),
    },
)

api_update_counters_schema = extend_schema(
    operation_id="monthly_report_update_counters",
    tags=["monthly_report"],
    summary="Обновление счётчиков",
    description=(
        "Обновляет счётчики одной записи при открытом месяце. "
        "Записывает аудит и помечает отредактированные *_end поля как ручные (отключает автосинхронизацию). "
        "Проверяет ограничения для дублирующихся серийников."
    ),
    parameters=[
        OpenApiParameter(name="pk", description="ID записи MonthlyReport", type=int, location="path", required=True),
    ],
    request=UpdateCountersRequestSerializer,
    responses={
        200: OpenApiResponse(response=UPDATE_COUNTERS_RESULT_SCHEMA, description="Счётчики обновлены"),
        400: OpenApiResponse(response=UPDATE_COUNTERS_RESULT_SCHEMA, description="Ошибка валидации"),
        403: OpenApiResponse(response=UPDATE_COUNTERS_RESULT_SCHEMA, description="Нет прав или месяц закрыт"),
        404: OpenApiResponse(response=UPDATE_COUNTERS_RESULT_SCHEMA, description="Запись не найдена"),
    },
)

api_change_history_schema = extend_schema(
    operation_id="monthly_report_change_history",
    tags=["monthly_report"],
    summary="История изменений записи",
    description=(
        "Возвращает историю изменений для конкретной записи MonthlyReport. "
        "Требует право view_change_history."
    ),
    parameters=[
        OpenApiParameter(name="pk", description="ID записи MonthlyReport", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(
            response=serializers.ListField(child=CHANGE_HISTORY_ITEM_SCHEMA),
            description="История изменений (список записей)"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
        404: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Запись не найдена"),
    },
)

api_reset_manual_flag_schema = extend_schema(
    operation_id="monthly_report_reset_manual_flag",
    tags=["monthly_report"],
    summary="Сброс флага ручного редактирования",
    description=(
        "Сбрасывает флаг ручного редактирования для указанного поля. "
        "Поле вернётся к автосинхронизации. "
        "Требует право can_reset_auto_polling."
    ),
    parameters=[
        OpenApiParameter(name="pk", description="ID записи MonthlyReport", type=int, location="path", required=True),
    ],
    request=ResetManualRequestSerializer,
    responses={
        200: OpenApiResponse(response=RESET_MANUAL_RESULT_SCHEMA, description="Флаг сброшен"),
        400: OpenApiResponse(response=RESET_MANUAL_RESULT_SCHEMA, description="Недопустимое поле"),
        403: OpenApiResponse(response=RESET_MANUAL_RESULT_SCHEMA, description="Нет прав или месяц закрыт"),
        404: OpenApiResponse(response=RESET_MANUAL_RESULT_SCHEMA, description="Запись не найдена"),
        500: OpenApiResponse(response=RESET_MANUAL_RESULT_SCHEMA, description="Ошибка сервера"),
    },
)

api_months_list_schema = extend_schema(
    operation_id="monthly_report_months_list",
    tags=["monthly_report"],
    summary="Список месяцев",
    description=(
        "Возвращает список месяцев с данными. "
        "Для обычных пользователей отображаются только опубликованные месяцы. "
        "Требует право access_monthly_report."
    ),
    responses={
        200: OpenApiResponse(
            response=serializers.ListField(child=MONTH_ITEM_SCHEMA),
            description="Список месяцев"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
    },
)

api_month_diff_schema = extend_schema(
    operation_id="monthly_report_month_diff",
    tags=["monthly_report"],
    summary="Diff между месяцами",
    description=(
        "Возвращает детальное сравнение между указанным месяцем и предыдущим. "
        "Содержит добавленные/удалённые позиции и изменения потенциала автозаполнения. "
        "Дополнительные данные (ip_gained, ip_lost, autofill_gained, autofill_lost) "
        "требуют право view_monthly_report_metrics. "
        "Требует право access_monthly_report."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="MonthDiffResponse",
                fields={
                    "ok": BooleanField(help_text="Успешность операции"),
                    "prev_month": CharField(help_text="Предыдущий месяц (ISO)", allow_null=True, required=False),
                },
            ),
            description="Diff между месяцами (содержит added/removed списки)"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
    },
)

api_month_detail_schema = extend_schema(
    operation_id="monthly_report_month_detail",
    tags=["monthly_report"],
    summary="Детали отчёта за месяц",
    description=(
        "Возвращает детальный список записей за указанный месяц с пагинацией и фильтрацией. "
        "Для обычных пользователей доступ к неопубликованным месяцам запрещён. "
        "Требует право access_monthly_report."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
        OpenApiParameter(name="q", description="Общий поиск (по организации, филиалу, городу, адресу, модели, serial, инв. номеру)", type=str, required=False),
        OpenApiParameter(name="org", description="Фильтр по организации (точное совпадение)", type=str, required=False),
        OpenApiParameter(name="org__in", description="Фильтр по организациям (список через ||)", type=str, required=False),
        OpenApiParameter(name="branch", description="Фильтр по филиалу", type=str, required=False),
        OpenApiParameter(name="branch__in", description="Фильтр по филиалам (список через ||)", type=str, required=False),
        OpenApiParameter(name="city", description="Фильтр по городу", type=str, required=False),
        OpenApiParameter(name="city__in", description="Фильтр по городам (список через ||)", type=str, required=False),
        OpenApiParameter(name="address", description="Фильтр по адресу", type=str, required=False),
        OpenApiParameter(name="address__in", description="Фильтр по адресам (список через ||)", type=str, required=False),
        OpenApiParameter(name="model", description="Фильтр по модели", type=str, required=False),
        OpenApiParameter(name="model__in", description="Фильтр по моделям (список через ||)", type=str, required=False),
        OpenApiParameter(name="serial", description="Фильтр по серийному номеру", type=str, required=False),
        OpenApiParameter(name="serial__in", description="Фильтр по серийным номерам (список через ||)", type=str, required=False),
        OpenApiParameter(name="inv", description="Фильтр по инвентарному номеру", type=str, required=False),
        OpenApiParameter(name="inv__in", description="Фильтр по инвентарным номерам (список через ||)", type=str, required=False),
        OpenApiParameter(name="num", description="Фильтр по номеру (части инвентарного)", type=str, required=False),
        OpenApiParameter(name="num__in", description="Фильтр по номерам (список через ||)", type=str, required=False),
        OpenApiParameter(name="total_min", description="Минимальное количество отпечатков", type=int, required=False),
        OpenApiParameter(name="total_max", description="Максимальное количество отпечатков", type=int, required=False),
        OpenApiParameter(name="page", description="Номер страницы", type=int, required=False),
        OpenApiParameter(name="per_page", description="Записей на странице", type=int, required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=serializers.ListField(child=MONTH_REPORT_ITEM_SCHEMA),
            description="Детали отчёта за месяц (список записей)"
        ),
        400: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Неверная дата"),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав или месяц не опубликован"),
    },
)

api_toggle_serial_override_schema = extend_schema(
    operation_id="monthly_report_toggle_serial_override",
    tags=["monthly_report"],
    summary="Управление оверрайдом серийного номера",
    description=(
        "Создаёт или удаляет SerialEditOverride для серийного номера. "
        "Позволяет разблокировать/заблокировать ручное редактирование end-полей "
        "для конкретного серийника. "
        "Требует право override_auto_lock."
    ),
    request=SerialOverrideRequestSerializer,
    responses={
        200: OpenApiResponse(response=SERIAL_OVERRIDE_RESULT_SCHEMA, description="Оверрайд обновлён"),
        400: OpenApiResponse(response=SERIAL_OVERRIDE_RESULT_SCHEMA, description="Ошибка валидации"),
        403: OpenApiResponse(response=SERIAL_OVERRIDE_RESULT_SCHEMA, description="Нет прав"),
    },
)

api_toggle_month_published_schema = extend_schema(
    operation_id="monthly_report_toggle_month_published",
    tags=["monthly_report"],
    summary="Публикация/скрытие месяца",
    description=(
        "Переключает статус публикации месяца. "
        "Только пользователи с правом can_manage_month_visibility могут управлять публикацией."
    ),
    request=ToggleMonthPublishedRequestSerializer,
    responses={
        200: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Статус обновлён"),
        400: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Ошибка валидации"),
        403: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Нет прав"),
        500: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Ошибка сервера"),
    },
)

api_toggle_auto_sync_schema = extend_schema(
    operation_id="monthly_report_toggle_auto_sync",
    tags=["monthly_report"],
    summary="Включение/выключение автосинхронизации",
    description=(
        "Переключает флаг автосинхронизации для месяца. "
        "Только пользователи с правом can_manage_month_visibility могут управлять автосинхронизацией."
    ),
    request=ToggleAutoSyncRequestSerializer,
    responses={
        200: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Статус обновлён"),
        400: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Ошибка валидации"),
        403: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Нет прав"),
        500: OpenApiResponse(response=TOGGLE_RESULT_SCHEMA, description="Ошибка сервера"),
    },
)

api_delete_month_schema = extend_schema(
    operation_id="monthly_report_delete_month",
    tags=["monthly_report"],
    summary="Удаление месяца",
    description=(
        "Удаляет месяц и все связанные данные безвозвратно: "
        "все записи MonthlyReport, MonthControl, логи изменений (CounterChangeLog). "
        "Требует право can_delete_month."
    ),
    request=DeleteMonthRequestSerializer,
    responses={
        200: OpenApiResponse(response=DELETE_MONTH_RESULT_SCHEMA, description="Месяц удалён"),
        400: OpenApiResponse(response=DELETE_MONTH_RESULT_SCHEMA, description="Ошибка валидации"),
        403: OpenApiResponse(response=DELETE_MONTH_RESULT_SCHEMA, description="Нет прав"),
        404: OpenApiResponse(response=DELETE_MONTH_RESULT_SCHEMA, description="Месяц не найден"),
        500: OpenApiResponse(response=DELETE_MONTH_RESULT_SCHEMA, description="Ошибка сервера"),
    },
)

api_month_users_stats_schema = extend_schema(
    operation_id="monthly_report_month_users_stats",
    tags=["monthly_report"],
    summary="Статистика по пользователям за месяц",
    description=(
        "Возвращает статистику по пользователям за указанный месяц. "
        "Для каждого пользователя показывает количество уникальных устройств, "
        "которые они редактировали (разделение на edited_auto и filled_empty). "
        "Требует право view_monthly_report_metrics."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(
            response=serializers.ListField(child=USER_STATS_SCHEMA),
            description="Статистика по пользователям (список)"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
    },
)

api_month_changes_list_schema = extend_schema(
    operation_id="monthly_report_month_changes_list",
    tags=["monthly_report"],
    summary="Список всех изменений за месяц",
    description=(
        "Возвращает плоский список всех ручных изменений за месяц для клиентской фильтрации и группировки. "
        "Каждое изменение помечено типом: filled_empty/edited_auto/edited_manual. "
        "Требует право view_monthly_report_metrics."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(
            response=serializers.ListField(child=CHANGE_ITEM_SCHEMA),
            description="Список изменений"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
    },
)

api_device_report_schema = extend_schema(
    operation_id="monthly_report_device_report",
    tags=["monthly_report"],
    summary="Отчёт по устройству за месяц",
    description=(
        "Возвращает данные MonthlyReport конкретного устройства за указанный месяц. "
        "Используется для отображения информации об устройстве и счётчиках. "
        "Требует право view_monthly_report_metrics."
    ),
    parameters=[
        OpenApiParameter(name="year", description="Год (например, 2024)", type=int, location="path", required=True),
        OpenApiParameter(name="month", description="Месяц (1-12)", type=int, location="path", required=True),
        OpenApiParameter(name="serial_number", description="Серийный номер устройства", type=str, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(
            response=DEVICE_REPORT_DATA_SCHEMA,
            description="Отчёт по устройству"
        ),
        403: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Нет прав"),
        404: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Отчёт не найден"),
        500: OpenApiResponse(response=OK_RESPONSE_SCHEMA, description="Ошибка сервера"),
    },
)

api_start_glpi_export_schema = extend_schema(
    operation_id="monthly_report_start_glpi_export",
    tags=["monthly_report"],
    summary="Запуск выгрузки в GLPI",
    description=(
        "Запускает асинхронную задачу выгрузки счётчиков в GLPI. "
        "Возвращает task_id для отслеживания статуса через api_glpi_export_status. "
        "Требует право sync_from_inventory."
    ),
    request=GLPIExportStartRequestSerializer,
    responses={
        200: OpenApiResponse(response=GLPI_EXPORT_START_SCHEMA, description="Задача запущена"),
        400: OpenApiResponse(response=GLPI_EXPORT_START_SCHEMA, description="Интеграция не установлена"),
        403: OpenApiResponse(response=GLPI_EXPORT_START_SCHEMA, description="Нет прав"),
    },
)

api_glpi_export_status_schema = extend_schema(
    operation_id="monthly_report_glpi_export_status",
    tags=["monthly_report"],
    summary="Статус выгрузки в GLPI",
    description=(
        "Возвращает статус задачи выгрузки счётчиков в GLPI по task_id. "
        "Возможные состояния: PENDING (в очереди), PROGRESS (выполняется), "
        "SUCCESS (завершено), FAILURE (ошибка)."
    ),
    parameters=[
        OpenApiParameter(name="task_id", description="ID задачи Celery", type=str, location="path", required=True),
    ],
    responses={
        200: OpenApiResponse(response=GLPI_EXPORT_STATUS_SCHEMA, description="Статус задачи"),
    },
)
