from __future__ import annotations
import io
from datetime import date
from typing import List
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse

from ..models import MonthlyReport


def export_month_to_excel(month_dt: date) -> HttpResponse:
    """
    Экспортирует данные месяца в Excel в том же формате, что и загрузка.
    """
    # Получаем данные за месяц
    reports = MonthlyReport.objects.filter(
        month__year=month_dt.year,
        month__month=month_dt.month
    ).order_by('order_number', 'organization', 'city', 'equipment_model', 'serial_number')

    # Создаем книгу Excel
    wb = Workbook()
    ws = wb.active
    ws.title = f"{month_dt.strftime('%Y-%m')}"

    # Определяем заголовки (точно как в загрузке)
    headers = [
        "№ п/п",
        "Организация",
        "Филиал",
        "Город",
        "Адрес",
        "Модель и наименование оборудования",
        "Серийный номер оборудования",
        "Инв номер",
        "A4 ч/б начало",
        "A4 ч/б конец",
        "A4 цвет начало",
        "A4 цвет конец",
        "A3 ч/б начало",
        "A3 ч/б конец",
        "A3 цвет начало",
        "A3 цвет конец",
        "Итого отпечатков шт.",
        "Нормативное время доступности (A)",
        "Фактическое время недоступности (D)",
        "K1 = ((A - D)/A)*100%",
        "Количество не просроченных запросов (L)",
        "Общее количество запросов (W)",
        "K2 = (L/W)*100%",
    ]

    # Стили для заголовков
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Записываем заголовки
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Устанавливаем ширину колонок
    column_widths = {
        1: 8,  # № п/п
        2: 25,  # Организация
        3: 20,  # Филиал
        4: 15,  # Город
        5: 30,  # Адрес
        6: 35,  # Модель
        7: 20,  # Серийный номер
        8: 15,  # Инв номер
        9: 12,  # A4 ч/б начало
        10: 12,  # A4 ч/б конец
        11: 12,  # A4 цвет начало
        12: 12,  # A4 цвет конец
        13: 12,  # A3 ч/б начало
        14: 12,  # A3 ч/б конец
        15: 12,  # A3 цвет начало
        16: 12,  # A3 цвет конец
        17: 15,  # Итого отпечатков
        18: 12,  # A
        19: 12,  # D
        20: 12,  # K1
        21: 12,  # L
        22: 12,  # W
        23: 12,  # K2
    }

    for col_idx, width in column_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Высота строки заголовка
    ws.row_dimensions[1].height = 40

    # Записываем данные
    for row_idx, report in enumerate(reports, start=2):
        row_data = [
            report.order_number,
            report.organization,
            report.branch,
            report.city,
            report.address,
            report.equipment_model,
            report.serial_number,
            report.inventory_number,
            report.a4_bw_start,
            report.a4_bw_end,
            report.a4_color_start,
            report.a4_color_end,
            report.a3_bw_start,
            report.a3_bw_end,
            report.a3_color_start,
            report.a3_color_end,
            report.total_prints,
            report.normative_availability,
            report.actual_downtime,
            round(report.k1, 2) if report.k1 else 0,
            report.non_overdue_requests,
            report.total_requests,
            round(report.k2, 2) if report.k2 else 0,
        ]

        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border

            # Выравнивание
            if col_idx == 1:  # № п/п
                cell.alignment = Alignment(horizontal="center")
            elif col_idx >= 9:  # Числовые поля
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")

    # Закрепляем первую строку
    ws.freeze_panes = "A2"

    # Сохраняем в байты
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # Создаем HTTP ответ
    filename = f"monthly_report_{month_dt.strftime('%Y-%m')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response