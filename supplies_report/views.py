import json
from datetime import time as dt_time
from urllib.parse import quote

from django.contrib.auth.decorators import login_required, permission_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from inventory.models import Printer

from .models import ReportGroup, ReportGroupItem
from .services import build_eml, build_report_data

# ─── Helpers ──────────────────────────────────────────────────────────────────

GROUP_EDITABLE_FIELDS = {
    "name",
    "location_label",
    "subject_template",
    "body_intro",
    "body_signature",
    "from_email",
    "to_emails",
    "cc_emails",
    "stale_threshold_hours",
    "is_active",
    "auto_send_enabled",
    "auto_send_time",
    "auto_send_weekdays",
}

ITEM_EDITABLE_FIELDS = {"location", "additional_info", "sort_order", "printer_id"}


def _serialize_group(group: ReportGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "location_label": group.location_label,
        "subject_template": group.subject_template,
        "body_intro": group.body_intro,
        "body_signature": group.body_signature,
        "from_email": group.from_email,
        "to_emails": group.to_emails,
        "cc_emails": group.cc_emails,
        "stale_threshold_hours": group.stale_threshold_hours,
        "is_active": group.is_active,
        "auto_send_enabled": group.auto_send_enabled,
        "auto_send_time": group.auto_send_time.strftime("%H:%M") if group.auto_send_time else "",
        "auto_send_weekdays": group.auto_send_weekdays,
        "last_sent_at": group.last_sent_at.isoformat() if group.last_sent_at else None,
        "last_send_error": group.last_send_error or "",
        # items_count подставляется через annotate() в списочных view'ах;
        # fallback — отдельный COUNT для одиночного объекта (detail view).
        "items_count": (
            getattr(group, "items_count", None)
            if getattr(group, "items_count", None) is not None
            else group.items.count()
        ),
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }


def _serialize_item(item: ReportGroupItem) -> dict:
    printer = item.printer
    return {
        "id": item.id,
        "sort_order": item.sort_order,
        "location": item.location,
        "additional_info": item.additional_info,
        "printer": {
            "id": printer.id,
            "ip_address": str(printer.ip_address),
            "serial_number": printer.serial_number,
            "model": printer.model_display,
            "is_active": printer.is_active,
        },
    }


def _serialize_row(row) -> dict:
    """Preview-строка для письма (PrinterRow → dict)."""
    return {
        "item_id": row.item.id,
        "printer_id": row.item.printer_id,
        "ip": row.ip,
        "model": row.model,
        "location": row.location,
        "additional_info": row.additional,
        "consumables": [{"label": c.color_label, "toner": c.toner_text, "drum": c.drum_text} for c in row.consumables],
        "last_polled_at": row.last_polled_at.isoformat() if row.last_polled_at else None,
        "is_stale": row.is_stale,
        "no_data": row.no_data,
    }


def _parse_json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return None


# ─── Page views ───────────────────────────────────────────────────────────────


@login_required
@permission_required("supplies_report.access_supplies_report", raise_exception=True)
@ensure_csrf_cookie
def list_page(request):
    return render(request, "supplies_report/list.html", {"app": "supplies_report"})


@login_required
@permission_required("supplies_report.access_supplies_report", raise_exception=True)
@ensure_csrf_cookie
def detail_page(request, group_id: int):
    group = get_object_or_404(ReportGroup, pk=group_id)
    return render(
        request,
        "supplies_report/detail.html",
        {"app": "supplies_report", "group": group},
    )


# ─── API views ────────────────────────────────────────────────────────────────


@login_required
@permission_required("supplies_report.access_supplies_report", raise_exception=True)
@require_GET
def api_groups_list(request):
    groups = ReportGroup.objects.annotate(items_count=Count("items")).order_by("name")
    return JsonResponse({"groups": [_serialize_group(g) for g in groups]})


@login_required
@permission_required("supplies_report.access_supplies_report", raise_exception=True)
@require_GET
def api_group_detail(request, group_id: int):
    group = get_object_or_404(ReportGroup, pk=group_id)
    items_qs = group.items.select_related("printer", "printer__device_model").order_by("sort_order", "id")
    items = [_serialize_item(i) for i in items_qs]
    rows = [_serialize_row(r) for r in build_report_data(group)]
    return JsonResponse(
        {
            "group": _serialize_group(group),
            "items": items,
            "rows": rows,
        }
    )


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["PATCH"])
def api_group_update(request, group_id: int):
    group = get_object_or_404(ReportGroup, pk=group_id)
    payload = _parse_json_body(request)
    if payload is None or not isinstance(payload, dict):
        return HttpResponseBadRequest("invalid JSON body")

    changed = []
    for field, value in payload.items():
        if field not in GROUP_EDITABLE_FIELDS:
            continue
        if field == "stale_threshold_hours":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return HttpResponseBadRequest(f"invalid {field}")
            if value < 1:
                return HttpResponseBadRequest("stale_threshold_hours must be >= 1")
        elif field in ("is_active", "auto_send_enabled"):
            value = bool(value)
        elif field == "auto_send_time":
            # принимаем "HH:MM" или пустую строку → None
            if value in (None, ""):
                value = None
            else:
                try:
                    hh, mm = str(value).split(":")[:2]
                    value = dt_time(hour=int(hh), minute=int(mm))
                except (ValueError, TypeError):
                    return HttpResponseBadRequest("invalid auto_send_time (use HH:MM)")
        elif field == "auto_send_weekdays":
            # принимаем строку "1,2,3" или массив [1,2,3]
            if isinstance(value, list):
                value = ",".join(str(int(v)) for v in value)
            else:
                value = str(value or "")
        setattr(group, field, value)
        changed.append(field)

    if not changed:
        return JsonResponse({"group": _serialize_group(group), "changed": []})

    # updated_at обновится сам (auto_now=True), но Django требует включить его в
    # update_fields, чтобы триггер сработал при частичном save().
    group.save(update_fields=changed + ["updated_at"])
    return JsonResponse({"group": _serialize_group(group), "changed": changed})


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["PATCH"])
def api_item_update(request, item_id: int):
    item = get_object_or_404(ReportGroupItem.objects.select_related("printer"), pk=item_id)
    payload = _parse_json_body(request)
    if payload is None or not isinstance(payload, dict):
        return HttpResponseBadRequest("invalid JSON body")

    changed = []
    for field, value in payload.items():
        if field not in ITEM_EDITABLE_FIELDS:
            continue
        if field == "sort_order":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return HttpResponseBadRequest("invalid sort_order")
        elif field == "printer_id":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return HttpResponseBadRequest("invalid printer_id")
            if not Printer.objects.filter(pk=value).exists():
                return HttpResponseBadRequest("printer not found")
        else:
            value = "" if value is None else str(value)
        setattr(item, field, value)
        changed.append(field)

    if changed:
        item.save(update_fields=changed)

    return JsonResponse({"item": _serialize_item(item), "changed": changed})


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["POST"])
def api_item_create(request, group_id: int):
    group = get_object_or_404(ReportGroup, pk=group_id)
    payload = _parse_json_body(request)
    if payload is None or not isinstance(payload, dict):
        return HttpResponseBadRequest("invalid JSON body")

    printer_id = payload.get("printer_id")
    if not printer_id:
        return HttpResponseBadRequest("printer_id required")
    try:
        printer_id = int(printer_id)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("invalid printer_id")
    if not Printer.objects.filter(pk=printer_id).exists():
        return HttpResponseBadRequest("printer not found")

    sort_order = payload.get("sort_order")
    if sort_order in (None, ""):
        last = group.items.order_by("-sort_order").first()
        sort_order = (last.sort_order if last else 0) + 1
    else:
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("invalid sort_order")

    # Защита от параллельной вставки: предварительный exists() остался для
    # человеческого ответа, но финальное слово — за unique_together на уровне БД.
    try:
        item = ReportGroupItem.objects.create(
            group=group,
            printer_id=printer_id,
            location=str(payload.get("location") or ""),
            additional_info=str(payload.get("additional_info") or ""),
            sort_order=sort_order,
        )
    except IntegrityError:
        return HttpResponseBadRequest("printer already in group")
    return JsonResponse({"item": _serialize_item(item)}, status=201)


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["DELETE"])
def api_item_delete(request, item_id: int):
    item = get_object_or_404(ReportGroupItem, pk=item_id)
    item.delete()
    return JsonResponse({"deleted": item_id})


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["POST"])
@transaction.atomic
def api_items_reorder(request, group_id: int):
    """Тело: {"order": [item_id1, item_id2, ...]}. Перенумерует sort_order шагом 1."""
    group = get_object_or_404(ReportGroup, pk=group_id)
    payload = _parse_json_body(request)
    if not payload or not isinstance(payload.get("order"), list):
        return HttpResponseBadRequest("order list required")

    items_by_id = {i.id: i for i in group.items.all()}
    for idx, item_id in enumerate(payload["order"]):
        item = items_by_id.get(int(item_id))
        if not item:
            continue
        item.sort_order = idx + 1
        item.save(update_fields=["sort_order"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("supplies_report.access_supplies_report", raise_exception=True)
@require_GET
def api_printer_search(request):
    """Поиск активных принтеров по ip/serial — для autocomplete при добавлении item'а."""
    q = (request.GET.get("q") or "").strip()
    qs = Printer.objects.filter(is_active=True).select_related("device_model")
    if q:
        qs = qs.filter(ip_address__icontains=q) | qs.filter(serial_number__icontains=q)
    results = [
        {
            "id": p.id,
            "ip_address": str(p.ip_address),
            "serial_number": p.serial_number,
            "model": p.model_display,
        }
        for p in qs.order_by("ip_address")[:25]
    ]
    return JsonResponse({"results": results})


# ─── Отправка сейчас (через Celery) ───────────────────────────────────────────


@login_required
@permission_required("supplies_report.manage_supplies_report", raise_exception=True)
@require_http_methods(["POST"])
def api_send_now(request, group_id: int):
    """Запустить отправку письма прямо сейчас. Возвращает task_id Celery.

    Реальная отправка идёт через EmailMultiAlternatives с SMTP-настройками
    из settings (EMAIL_BACKEND). В dev по умолчанию это console-backend —
    письмо попадёт в лог воркера, никуда не уйдёт.
    """
    group = get_object_or_404(ReportGroup, pk=group_id)
    if not group.is_active:
        return HttpResponseBadRequest("group is not active")

    # Импорт здесь, чтобы не таскать celery в модулях, где он не нужен.
    from kombu.exceptions import OperationalError

    from .tasks import send_supplies_report_task

    try:
        async_result = send_supplies_report_task.delay(group.id)
    except OperationalError:
        # Redis/брокер недоступен — отдаём 503, чтобы UI показал понятную ошибку.
        return JsonResponse(
            {"error": "Очередь задач недоступна — обратитесь к администратору."},
            status=503,
        )
    return JsonResponse({"task_id": async_result.id, "group_id": group.id})


# ─── .eml download (с этапа 1) ────────────────────────────────────────────────


@login_required
@permission_required("supplies_report.download_supplies_report", raise_exception=True)
def download_eml(request, group_id: int):
    group = get_object_or_404(ReportGroup, pk=group_id, is_active=True)
    from_email = request.user.email or None
    eml_bytes = build_eml(group, from_email=from_email)

    safe_name = quote(f"{group.name}.eml")
    response = HttpResponse(eml_bytes, content_type="message/rfc822")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{safe_name}"
    return response
