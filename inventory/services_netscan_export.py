"""Выгрузка найденных сканированием сетей устройств в Excel (вместе с итогом сверки с GLPI)."""

from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# (заголовок, ширина, функция значения)
COLUMNS = [
    ("Сеть", 24, lambda d: d.network.name),
    ("CIDR", 16, lambda d: d.network.cidr),
    ("VLAN", 7, lambda d: d.network.vlan_id),
    ("IP", 15, lambda d: d.ip_address),
    ("Серийный номер", 20, lambda d: d.serial_number),
    ("MAC", 19, lambda d: d.mac_address),
    ("Модель (SNMP)", 28, lambda d: f"{d.manufacturer} {d.model}".strip()),
    ("Статус", 26, lambda d: d.get_status_display()),
    ("Пояснение", 50, lambda d: d.message),
    ("В опросе (IP)", 15, lambda d: d.printer.ip_address if d.printer_id else ""),
    ("Организация (договор)", 30, lambda d: d.contract_device.organization.name if d.contract_device_id else ""),
    ("Адрес (договор)", 36, lambda d: d.contract_device.address if d.contract_device_id else ""),
    ("GLPI", 26, lambda d: d.get_glpi_status_display() if d.glpi_status else "не сверялось"),
    ("GLPI ID", 9, lambda d: d.glpi_printer_id),
    ("GLPI имя", 22, lambda d: d.glpi_name),
    ("GLPI сущность", 40, lambda d: d.glpi_entity),
    ("GLPI IP", 15, lambda d: d.glpi_ip),
    ("GLPI последний опрос", 18, lambda d: _naive(d.glpi_last_inventory)),
    ("GLPI счётчик", 12, lambda d: d.glpi_counter),
    ("GLPI пояснение", 50, lambda d: d.glpi_message),
    ("Последний ответ", 18, lambda d: _naive(d.last_seen)),
    ("Скрыто", 8, lambda d: "да" if d.is_ignored else ""),
]


def _naive(value):
    """Excel не умеет даты с часовым поясом — пишем местное время."""
    return timezone.localtime(value).replace(tzinfo=None) if value else None


def devices_xlsx(devices) -> bytes:
    """devices — queryset DiscoveredDevice. Возвращает содержимое .xlsx."""
    devices = devices.select_related("network", "printer", "contract_device", "contract_device__organization").order_by(
        "network__name", "ip_address"
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Устройства в сетях"
    ws.append([title for title, _, _ in COLUMNS])
    header_fill = PatternFill("solid", fgColor="DDEBF7")
    for idx, (_, width, _) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=idx)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(idx)].width = width

    date_columns = [
        i for i, (title, _, _) in enumerate(COLUMNS, 1) if title in ("GLPI последний опрос", "Последний ответ")
    ]
    for device in devices.iterator(chunk_size=500):
        ws.append([func(device) for _, _, func in COLUMNS])
        for col in date_columns:
            ws.cell(row=ws.max_row, column=col).number_format = "DD.MM.YYYY HH:MM"

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{max(ws.max_row, 1)}"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
