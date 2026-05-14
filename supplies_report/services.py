"""Сервисный слой для отчёта по расходникам.

Содержит две точки входа:
- build_report_data(group) — собирает строки таблицы по группе.
- build_eml(group, ...) — формирует RFC822 .eml для ручной отправки через Outlook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from html import escape
from typing import Iterable

from django.utils import timezone

from inventory.models import PageCounter

from .models import ReportGroup, ReportGroupItem

# Порядок цветов как в исходном письме: Y → M → C → K
COLOR_ORDER = [
    ("yellow", "желтый"),
    ("magenta", "пурпурный"),
    ("cyan", "голубой"),
    ("black", "черный"),
]

_RAW_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*$")


def _format_toner_value(raw: str) -> str:
    """Привести значение тонера к виду '79%' / '1900 стр.' / '-'."""
    if raw is None:
        return "-"
    value = str(raw).strip()
    if not value:
        return "-"
    # Если в БД лежит просто число 0..100 — трактуем как проценты.
    if _RAW_NUMBER_RE.match(value):
        return f"{value}%"
    return value


@dataclass
class ConsumableRow:
    """Одна строка по цвету: тонер и барабан рядом."""

    color_label: str
    toner_text: str  # "78%" или ""
    drum_text: str  # "93%" или ""


@dataclass
class PrinterRow:
    item: ReportGroupItem
    ip: str
    model: str
    location: str  # многострочный текст
    additional: str  # многострочный текст
    consumables: list[ConsumableRow] = field(default_factory=list)
    last_polled_at: datetime | None = None
    is_stale: bool = False
    no_data: bool = False

    @property
    def row_span(self) -> int:
        return max(len(self.consumables), 1)


def _latest_counters_map(printer_ids: list[int]) -> dict[int, PageCounter]:
    """Один запрос: последний успешный PageCounter для каждого из переданных принтеров.

    Использует PostgreSQL `DISTINCT ON (task__printer_id)` поверх упорядочивания
    по recorded_at desc. Эквивалентно «window-row-number == 1», но проще.
    """
    if not printer_ids:
        return {}
    counters = (
        PageCounter.objects.filter(
            task__printer_id__in=printer_ids,
            task__status="SUCCESS",
        )
        .select_related("task")
        .order_by("task__printer_id", "-recorded_at")
        .distinct("task__printer_id")
    )
    return {pc.task.printer_id: pc for pc in counters}


def _build_consumables(counter: PageCounter | None) -> list[ConsumableRow]:
    """Для каждого цвета (Y/M/C/K) собрать пару тонер+барабан. Строка добавляется,
    если есть хотя бы одно непустое значение."""
    if counter is None:
        return []
    out: list[ConsumableRow] = []
    for color, label in COLOR_ORDER:
        toner_raw = (getattr(counter, f"toner_{color}", "") or "").strip()
        drum_raw = (getattr(counter, f"drum_{color}", "") or "").strip()
        if not toner_raw and not drum_raw:
            continue
        out.append(
            ConsumableRow(
                color_label=label,
                toner_text=_format_toner_value(toner_raw) if toner_raw else "",
                drum_text=_format_toner_value(drum_raw) if drum_raw else "",
            )
        )
    return out


def build_report_data(group: ReportGroup) -> list[PrinterRow]:
    """Собрать данные для письма по группе.

    Выполняет фиксированное количество SQL-запросов независимо от размера группы:
    один для items с принтерами и моделями, один — для последних PageCounter.
    """
    threshold = timedelta(hours=group.stale_threshold_hours or 24)
    now = timezone.now()

    items = list(
        group.items.select_related("printer", "printer__device_model", "printer__device_model__manufacturer").order_by(
            "sort_order", "id"
        )
    )
    counters_by_printer = _latest_counters_map([i.printer_id for i in items])

    rows: list[PrinterRow] = []
    for item in items:
        printer = item.printer
        counter = counters_by_printer.get(printer.id)
        consumables = _build_consumables(counter)

        no_data = counter is None
        is_stale = False
        last_polled_at = None
        if counter is not None:
            last_polled_at = counter.recorded_at
            is_stale = (now - counter.recorded_at) > threshold

        rows.append(
            PrinterRow(
                item=item,
                ip=str(printer.ip_address),
                model=printer.model_display or "",
                location=item.location or "",
                additional=item.additional_info or "",
                consumables=consumables,
                last_polled_at=last_polled_at,
                is_stale=is_stale,
                no_data=no_data,
            )
        )
    return rows


# ─── .eml builder ─────────────────────────────────────────────────────────────


def split_emails(blob: str) -> list[str]:
    """Распарсить To/Cc — разделители: запятая, точка с запятой, перевод строки."""
    if not blob:
        return []
    parts = re.split(r"[,;\n\r]+", blob)
    return [p.strip() for p in parts if p.strip()]


# Поддерживаемые плейсхолдеры в subject_template. Используем простой replace
# вместо str.format(), чтобы не давать доступ к атрибутам объектов
# (например, {date.__class__}) — менеджер группы вводит шаблон в админке.
SUBJECT_PLACEHOLDERS = ("{date}", "{location}")


def format_subject(group: ReportGroup, today: datetime) -> str:
    template = group.subject_template or ""
    replacements = {
        "{date}": today.strftime("%d.%m.%Y"),
        "{location}": group.location_label or "",
    }
    for key, val in replacements.items():
        template = template.replace(key, val)
    return template.strip()


def _multiline_html(text: str) -> str:
    if not text:
        return "&mdash;"
    return "<br>".join(escape(line) for line in text.splitlines())


CELL_STYLE = "border:1px solid #000;padding:6px 10px;vertical-align:top;"
HEADER_STYLE = "border:1px solid #000;padding:6px 10px;background-color:#d9d9d9;" "font-weight:bold;text-align:center;"
STALE_STYLE = "color:#a00;font-style:italic;font-size:9pt;"


def _render_html_table(rows: list[PrinterRow]) -> str:
    """HTML-таблица в стиле, который Outlook (Word-рендер) разбирает корректно."""
    parts: list[str] = []
    parts.append(
        '<table border="1" cellspacing="0" cellpadding="0" '
        'style="border-collapse:collapse;border:1px solid #000;'
        'font-family:Arial,sans-serif;font-size:11pt;">'
    )
    parts.append("<tr>")
    parts.append(f'<th style="{HEADER_STYLE}">IP&nbsp;Адрес</th>')
    parts.append(f'<th style="{HEADER_STYLE}">Наименование</th>')
    parts.append(f'<th style="{HEADER_STYLE}">Расположение</th>')
    parts.append(f'<th style="{HEADER_STYLE}">Дополнительно</th>')
    parts.append(f'<th style="{HEADER_STYLE}">Цвет</th>')
    parts.append(f'<th style="{HEADER_STYLE}" colspan="2">Остаток, %</th>')
    parts.append("</tr>")

    for row in rows:
        span = row.row_span
        extra = ""
        if row.no_data:
            extra = f'<br><span style="{STALE_STYLE}">нет данных опроса</span>'
        elif row.is_stale and row.last_polled_at is not None:
            extra = (
                f'<br><span style="{STALE_STYLE}">данные от '
                f'{escape(row.last_polled_at.strftime("%d.%m.%Y %H:%M"))}</span>'
            )

        location_cell = _multiline_html(row.location) + extra
        additional_cell = _multiline_html(row.additional)

        if not row.consumables:
            parts.append(
                "<tr>"
                f'<td style="{CELL_STYLE}">{escape(row.ip)}</td>'
                f'<td style="{CELL_STYLE}">{escape(row.model)}</td>'
                f'<td style="{CELL_STYLE}">{location_cell}</td>'
                f'<td style="{CELL_STYLE}">{additional_cell}</td>'
                f'<td style="{CELL_STYLE}" colspan="3">&mdash;</td>'
                "</tr>"
            )
            continue

        for idx, cr in enumerate(row.consumables):
            parts.append("<tr>")
            if idx == 0:
                parts.append(f'<td style="{CELL_STYLE}" rowspan="{span}">{escape(row.ip)}</td>')
                parts.append(f'<td style="{CELL_STYLE}" rowspan="{span}">{escape(row.model)}</td>')
                parts.append(f'<td style="{CELL_STYLE}" rowspan="{span}">{location_cell}</td>')
                parts.append(f'<td style="{CELL_STYLE}" rowspan="{span}">{additional_cell}</td>')
            parts.append(f'<td style="{CELL_STYLE}">{escape(cr.color_label)}</td>')
            parts.append(f'<td style="{CELL_STYLE}">{escape(cr.toner_text) if cr.toner_text else "&mdash;"}</td>')
            parts.append(f'<td style="{CELL_STYLE}">{escape(cr.drum_text) if cr.drum_text else "&mdash;"}</td>')
            parts.append("</tr>")

    parts.append("</table>")
    return "".join(parts)


def _render_text_table(rows: list[PrinterRow]) -> str:
    """Plain-text версия для клиентов без HTML (fallback)."""
    out: list[str] = []
    for row in rows:
        out.append(f"{row.ip}  {row.model}")
        if row.location:
            for line in row.location.splitlines():
                out.append(f"  {line}")
        if row.additional:
            for line in row.additional.splitlines():
                out.append(f"  {line}")
        if row.no_data:
            out.append("  (нет данных опроса)")
        elif row.is_stale and row.last_polled_at:
            out.append(f"  (данные от {row.last_polled_at.strftime('%d.%m.%Y %H:%M')})")
        if row.consumables:
            for cr in row.consumables:
                toner_part = f"тонер {cr.toner_text}" if cr.toner_text else "тонер —"
                drum_part = f"барабан {cr.drum_text}" if cr.drum_text else "барабан —"
                out.append(f"    {cr.color_label}: {toner_part}, {drum_part}")
        else:
            out.append("    —")
        out.append("")
    return "\n".join(out)


@dataclass
class EmailBodies:
    """Сформированное содержимое письма: тема + plain/html тело."""

    subject: str
    text_body: str
    html_body: str


def build_email_bodies(
    group: ReportGroup,
    *,
    today: datetime | None = None,
    rows: Iterable[PrinterRow] | None = None,
) -> EmailBodies:
    """Единая точка построения содержимого письма — используется и .eml-выгрузкой,
    и Celery-отправкой через SMTP. Гарантирует одинаковый текст/HTML в обеих ветках.
    """
    if today is None:
        today = timezone.localtime()
    if rows is None:
        rows = build_report_data(group)
    rows = list(rows)

    body_intro = group.body_intro or ""
    body_signature = group.body_signature or ""

    html_body = (
        '<html><head><meta charset="utf-8"></head>'
        '<body style="font-family:Arial,sans-serif;font-size:11pt;color:#000;">'
        f"<p>{_multiline_html(body_intro)}</p>"
        + _render_html_table(rows)
        + (f"<p>{_multiline_html(body_signature)}</p>" if body_signature else "")
        + "</body></html>"
    )
    text_body = body_intro + "\n\n" + _render_text_table(rows)
    if body_signature:
        text_body += "\n" + body_signature

    return EmailBodies(subject=format_subject(group, today), text_body=text_body, html_body=html_body)


def build_eml(
    group: ReportGroup,
    *,
    from_email: str | None = None,
    today: datetime | None = None,
    rows: Iterable[PrinterRow] | None = None,
) -> bytes:
    """Сгенерировать .eml через классический MIMEMultipart (как contracts/utils).

    X-Unsent: 1 заставляет Outlook открыть письмо как ЧЕРНОВИК.
    """
    bodies = build_email_bodies(group, today=today, rows=rows)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = bodies.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="supplies-report.local")
    msg["X-Unsent"] = "1"
    if from_email:
        msg["From"] = from_email
    elif group.from_email:
        msg["From"] = group.from_email

    to_list = split_emails(group.to_emails)
    cc_list = split_emails(group.cc_emails)
    if to_list:
        msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    # Порядок в multipart/alternative: сначала plain, потом html — html будет «предпочтительным».
    msg.attach(MIMEText(bodies.text_body, "plain", "utf-8"))
    msg.attach(MIMEText(bodies.html_body, "html", "utf-8"))
    return msg.as_bytes()
