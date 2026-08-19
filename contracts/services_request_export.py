"""Выгрузка журнала заявок в Excel.

Один экспорт вместо шести окдесковых: те отличались только набором статусов,
а статус здесь — обычный фильтр. Выгружается ровно то, что отобрано в журнале,
включая заявки почтовым подрядчикам, которых в Okdesk нет вовсе.
"""

from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .services_working_hours import calculator_for_request

HEADERS = (
    "Номер",
    "У подрядчика",
    "Подрядчик",
    "Организация",
    "Город",
    "Адрес",
    "Кабинет",
    "Модель",
    "Серийный номер",
    "Инициатор",
    "Контакты",
    "Описание",
    "Зарегистрирована",
    "Норматив, раб. ч",
    "Срок",
    "Срочность",
    "Восстановлена",
    "Закрыта",
    "Простой, раб. ч",
    "Статус",
    "Просрочена",
    "Акт",
)

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="495057", end_color="495057", fill_type="solid")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)


def export_requests_excel(queryset):
    """Возвращает (содержимое xlsx, имя файла) по готовому queryset журнала."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Заявки"
    sheet.append(list(HEADERS))
    for cell in sheet[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN

    # Связи берём здесь, а не полагаемся на вызывающего: выгрузка читает больше полей,
    # чем журнал на экране. Простой вдобавок считается по производственному календарю,
    # поэтому калькуляторы кэшируются на всю выгрузку.
    calculators = {}
    rows = queryset.select_related(
        "device__organization",
        "device__city__work_schedule",
        "device__model__manufacturer",
        "device__work_schedule",
        "service_provider",
        "initiator",
        "schedule_snapshot",
    ).iterator(chunk_size=500)
    for service_request in rows:
        sheet.append(_row(service_request, calculators))

    _autosize(sheet)
    sheet.freeze_panes = "A2"

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue(), f"service_requests_{timezone.localdate().isoformat()}.xlsx"


def _row(service_request, calculators):
    device = service_request.device
    return [
        service_request.number,
        service_request.external_number,
        service_request.service_provider.name if service_request.service_provider_id else "",
        device.organization.name if device.organization_id else "",
        device.city.name if device.city_id else "",
        device.address,
        device.room_number,
        str(device.model) if device.model_id else "",
        device.serial_number,
        _initiator(service_request),
        service_request.initiator_contacts,
        service_request.description,
        _moment(service_request.registered_at),
        service_request.sla_hours,
        _moment(service_request.deadline_at),
        service_request.urgency_label,
        _moment(service_request.restored_at),
        _moment(service_request.closed_at),
        # Незакрытая заявка копит простой прямо сейчас — считаем на момент выгрузки
        _downtime(service_request, calculators),
        service_request.get_status_display(),
        "Да" if service_request.is_overdue else "",
        service_request.act_number,
    ]


def _downtime(service_request, calculators):
    if not service_request.stops_printing:
        return ""
    calculator = calculator_for_request(service_request, calculators)
    return round(service_request.downtime_hours(calculator=calculator), 2) if calculator else ""


def _initiator(service_request):
    if not service_request.initiator_id:
        return ""
    return service_request.initiator.get_full_name() or service_request.initiator.username


def _moment(value):
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M") if value else ""


def _autosize(sheet, max_width=60):
    for cells in sheet.columns:
        longest = max((len(str(cell.value)) for cell in cells if cell.value is not None), default=10)
        sheet.column_dimensions[get_column_letter(cells[0].column)].width = min(longest + 2, max_width)
