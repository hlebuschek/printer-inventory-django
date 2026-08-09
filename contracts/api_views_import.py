"""
API массового импорта устройств по договору (Vue.js frontend).

Две фазы: загрузка файлов с анализом (ничего не пишется в ContractDevice)
и применение решений пользователя.
"""

import io
import json
import logging

from openpyxl import Workbook

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import AutoPollCandidate, ContractStatus, ImportRow, ImportSession, ServiceProvider
from .services_autopoll import candidate_payload, create_printers, verify_candidate
from .services_import import (
    ImportFileError,
    analyze_file,
    apply_session,
    find_missing_devices,
    rows_to_apply,
    session_summary,
)

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _import_permission(view):
    return login_required(
        permission_required("contracts.access_contracts_app", raise_exception=True)(
            permission_required("contracts.import_contracts", raise_exception=True)(view)
        )
    )


def _get_session(pk):
    return get_object_or_404(ImportSession, pk=pk)


def _row_payload(row):
    return {
        "id": row.id,
        "file": row.file.original_name,
        "row_number": row.row_number,
        "classification": row.classification,
        "decision": row.decision,
        "organization": row.raw.get("organization", ""),
        "city": row.raw.get("city", ""),
        "address": row.raw.get("address", ""),
        "room": row.raw.get("room", ""),
        "manufacturer": row.raw.get("manufacturer", ""),
        "model": row.raw.get("model", ""),
        "serial": row.raw.get("serial", ""),
        "errors": row.errors,
        "warnings": row.warnings,
        "apply_error": row.apply_error,
        "matched_device": (
            {
                "id": row.matched_device.id,
                "organization": row.matched_device.organization.name,
                "address": row.matched_device.address,
            }
            if row.matched_device_id
            else None
        ),
    }


@_import_permission
@require_http_methods(["POST"])
def create_session(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    status = ContractStatus.objects.filter(pk=payload.get("target_status_id")).first()
    if status is None:
        return JsonResponse({"error": "Не выбран статус для загружаемых устройств"}, status=400)

    provider = ServiceProvider.objects.filter(pk=payload.get("service_provider_id")).first()
    if provider is None:
        return JsonResponse({"error": "Не выбран подрядчик для загружаемых устройств"}, status=400)

    session = ImportSession.objects.create(
        name=(payload.get("name") or "")[:255],
        target_status=status,
        service_provider=provider,
        created_by=request.user,
    )
    return JsonResponse({"session_id": session.id})


@_import_permission
@require_http_methods(["POST"])
def upload_file(request, pk):
    session = _get_session(pk)
    if session.state == ImportSession.APPLIED:
        return JsonResponse({"error": "Сессия уже применена, файлы добавить нельзя"}, status=400)

    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "Файл не передан"}, status=400)
    if upload.size > MAX_UPLOAD_BYTES:
        return JsonResponse({"error": "Файл больше 20 МБ"}, status=400)

    replaced = session.files.filter(original_name=upload.name[:255]).exists()

    try:
        import_file = analyze_file(session, upload, upload.name, sheet=request.POST.get("sheet") or None)
    except ImportFileError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("Ошибка разбора файла импорта: %s", exc)
        return JsonResponse({"error": f"Не удалось разобрать файл: {exc}"}, status=400)

    return JsonResponse(
        {
            "file_id": import_file.id,
            "original_name": import_file.original_name,
            "rows_total": import_file.rows_total,
            "replaced": replaced,
            "summary": session_summary(session),
        }
    )


@_import_permission
@require_http_methods(["GET"])
def preview(request, pk):
    session = _get_session(pk)

    rows = session.rows.select_related("file", "matched_device", "matched_device__organization")

    classification = request.GET.get("classification")
    if classification:
        rows = rows.filter(classification=classification)

    query = (request.GET.get("q") or "").strip()
    if query:
        rows = rows.filter(Q(sn_lower__contains=query.lower()) | Q(raw__address__icontains=query))

    paginator = Paginator(rows, min(int(request.GET.get("per_page") or 50), 200))
    page = paginator.get_page(request.GET.get("page") or 1)

    return JsonResponse(
        {
            "session": {
                "id": session.id,
                "name": session.name,
                "state": session.state,
                "target_status": session.target_status.name,
                "service_provider": session.service_provider.name if session.service_provider_id else "",
                "stats": session.stats,
                "files": [
                    {"id": f.id, "name": f.original_name, "rows_total": f.rows_total} for f in session.files.all()
                ],
            },
            "summary": session_summary(session),
            "ready_to_apply": rows_to_apply(session).count(),
            "rows": [_row_payload(row) for row in page.object_list],
            "page_info": {
                "page": page.number,
                "pages": paginator.num_pages,
                "total": paginator.count,
            },
        }
    )


@_import_permission
@require_http_methods(["POST"])
def set_decisions(request, pk):
    session = _get_session(pk)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    valid = {choice for choice, _ in ImportRow.DECISION_CHOICES}
    updated = 0

    for item in payload.get("decisions", []):
        decision = item.get("decision")
        if decision not in valid:
            continue
        updated += session.rows.filter(pk=item.get("row_id")).update(decision=decision)

    bulk = payload.get("all_conflicts")
    if bulk in valid:
        updated += session.rows.filter(classification__in=[ImportRow.MOVED, ImportRow.DUP_IN_FILE]).update(
            decision=bulk
        )

    return JsonResponse({"updated": updated, "summary": session_summary(session)})


@_import_permission
@require_http_methods(["POST"])
def apply(request, pk):
    session = _get_session(pk)
    if session.state == ImportSession.APPLIED:
        return JsonResponse({"error": "Сессия уже применена"}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    try:
        result = apply_session(session, user=request.user, create_cities=bool(payload.get("create_cities")))
    except ImportFileError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("Ошибка применения импорта %s: %s", pk, exc)
        return JsonResponse({"error": f"Не удалось применить импорт: {exc}"}, status=500)

    return JsonResponse(result)


@_import_permission
@require_http_methods(["GET"])
def missing(request, pk):
    session = _get_session(pk)
    devices = find_missing_devices(session)

    paginator = Paginator(devices, min(int(request.GET.get("per_page") or 100), 500))
    page = paginator.get_page(request.GET.get("page") or 1)

    return JsonResponse(
        {
            "rows": [
                {
                    "id": d.id,
                    "organization": d.organization.name,
                    "city": d.city.name,
                    "address": d.address,
                    "room": d.room_number,
                    "manufacturer": d.model.manufacturer.name,
                    "model": d.model.name,
                    "serial": d.serial_number,
                    "status": d.status.name,
                }
                for d in page.object_list
            ],
            "page_info": {"page": page.number, "pages": paginator.num_pages, "total": paginator.count},
        }
    )


@_import_permission
@require_http_methods(["GET"])
def missing_export(request, pk):
    session = _get_session(pk)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Не найдены в файлах"
    worksheet.append(
        [
            "Организация",
            "Город",
            "Адрес",
            "№ кабинета",
            "Производитель",
            "Модель оборудования",
            "Серийный номер",
            "Статус",
        ]
    )

    for device in find_missing_devices(session).iterator(chunk_size=500):
        worksheet.append(
            [
                device.organization.name,
                device.city.name,
                device.address,
                device.room_number,
                device.model.manufacturer.name,
                device.model.name,
                device.serial_number,
                device.status.name,
            ]
        )

    stream = io.BytesIO()
    workbook.save(stream)

    return HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="import-{session.id}-missing.xlsx"'},
    )


@_import_permission
@require_http_methods(["POST"])
def autopoll_probe(request, pk):
    """Ставит в очередь проверку устройств сессии в GLPI."""
    from .tasks import probe_autopoll_candidates_task

    session = _get_session(pk)
    if session.state != ImportSession.APPLIED:
        return JsonResponse({"error": "Сначала примените импорт"}, status=400)

    task = probe_autopoll_candidates_task.delay(session.id)
    return JsonResponse({"task_id": task.id})


@_import_permission
@require_http_methods(["GET"])
def autopoll_list(request, pk):
    """Кандидаты на автозаведение + состояние задачи проверки (?task_id=)."""
    session = _get_session(pk)

    task_state = None
    task_id = (request.GET.get("task_id") or "").strip()
    if task_id:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)
        task_state = {"state": result.state, "ready": result.ready()}
        if result.ready() and not result.successful():
            task_state["error"] = str(result.result)

    candidates = session.autopoll_candidates.select_related(
        "contract_device__organization", "contract_device__model", "contract_device__model__manufacturer"
    )

    counts = {}
    payload = []
    for candidate in candidates:
        counts[candidate.status] = counts.get(candidate.status, 0) + 1
        payload.append(candidate_payload(candidate))

    return JsonResponse({"candidates": payload, "counts": counts, "task": task_state})


@_import_permission
@permission_required("inventory.add_printer", raise_exception=True)
@require_http_methods(["POST"])
def autopoll_create(request, pk):
    """Создаёт принтеры по выбранным кандидатам и сразу ставит их в очередь опроса."""
    session = _get_session(pk)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    ids = payload.get("candidate_ids") or []
    candidates = list(
        session.autopoll_candidates.filter(pk__in=ids).select_related(
            "contract_device__organization", "contract_device__model"
        )
    )
    if not candidates:
        return JsonResponse({"error": "Не выбрано ни одного устройства"}, status=400)

    results = create_printers(candidates, user=request.user)
    return JsonResponse(
        {
            "results": results,
            "created": sum(1 for r in results if r["created"]),
            "candidates": [candidate_payload(c) for c in candidates],
        }
    )


@_import_permission
@require_http_methods(["POST"])
def autopoll_verify(request, pk, candidate_id):
    """Пробный опрос устройства по IP из GLPI — без создания принтера."""
    session = _get_session(pk)
    candidate = get_object_or_404(
        AutoPollCandidate.objects.select_related("contract_device__organization", "contract_device__model"),
        pk=candidate_id,
        session=session,
    )

    verify_candidate(candidate)
    return JsonResponse(candidate_payload(candidate))


@_import_permission
@require_http_methods(["DELETE"])
def delete_session(request, pk):
    session = _get_session(pk)
    if session.state == ImportSession.APPLIED:
        return JsonResponse({"error": "Применённую сессию удалять нельзя — по ней считаются пропавшие"}, status=400)

    session.delete()
    return JsonResponse({"deleted": True})
