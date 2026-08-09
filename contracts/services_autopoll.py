"""
Автозаведение принтеров в опрос по данным GLPI.

После применения сессии импорта берём устройства с сетевым портом, которые у нас
не опрашиваются, и ищем их серийники в GLPI. Если GLPI опрашивал устройство
недавно и знает его IP — принтер можно создать одним нажатием и сразу опросить.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from access.models import EntityChangeLog
from contracts.models import AutoPollCandidate, ContractDevice
from integrations.glpi.client import GLPIAPIError, GLPIClient
from integrations.glpi.services import probe_serial_in_glpi
from inventory.models import ConnectionType, InventoryTask, PollingMethod, Printer

logger = logging.getLogger(__name__)

DEFAULT_COMMUNITY = "public"


def _freshness_hours():
    return getattr(settings, "AUTOPOLL_FRESHNESS_HOURS", 24)


def collect_devices(session):
    """
    Устройства сессии, для которых имеет смысл идти в GLPI: сетевой порт по справочнику,
    непустой серийник и ни одного активного принтера у нас.

    Устройства с активным принтером сюда не попадают даже если он давно не отвечает —
    заводить дубль нельзя, а починка существующего принтера это другая история.
    """
    device_ids = session.rows.filter(applied_device__isnull=False).values_list("applied_device_id", flat=True)

    devices = (
        ContractDevice.objects.filter(id__in=device_ids, model__has_network_port=True)
        .select_related("organization", "model", "model__manufacturer", "printer")
        .order_by("serial_number")
    )

    serials = {(d.serial_number or "").strip().lower() for d in devices}
    serials.discard("")
    # Серийники сравниваем без учёта регистра: в файле импорта и в SNMP-ответе
    # регистр часто разный, а уникальность серийника среди сетевых принтеров БД не держит.
    taken = set(
        Printer.objects.filter(is_active=True)
        .annotate(serial_lower=Lower("serial_number"))
        .filter(serial_lower__in=serials)
        .values_list("serial_lower", flat=True)
    )

    result = []
    seen = set()
    for device in devices:
        serial = (device.serial_number or "").strip()
        key = serial.lower()
        if not serial or key in seen or key in taken:
            continue
        if device.printer_id and device.printer.is_active:
            continue
        seen.add(key)
        result.append(device)

    return result


def _classify(probe, glpi_ip):
    """Переводит результат probe_serial_in_glpi в статус кандидата."""
    if probe["status"] in ("NOT_FOUND", "ERROR"):
        return probe["status"].lower()
    if not glpi_ip:
        return AutoPollCandidate.NO_IP
    if Printer.objects.filter(ip_address=glpi_ip, is_active=True, connection_type=ConnectionType.NETWORK).exists():
        return AutoPollCandidate.IP_CONFLICT
    return probe["status"].lower()


def probe_session(session):
    """
    Проверяет все подходящие устройства сессии в GLPI и пересоздаёт кандидатов.

    Returns:
        dict: счётчики по статусам
    """
    devices = collect_devices(session)
    session.autopoll_candidates.filter(created_printer__isnull=True).delete()

    stats = {key: 0 for key, _ in AutoPollCandidate.STATUS_CHOICES}
    stats["total"] = len(devices)

    if not devices:
        return stats

    cutoff = timezone.now() - timedelta(hours=_freshness_hours())

    try:
        with GLPIClient() as client:
            for device in devices:
                serial = device.serial_number.strip()
                try:
                    probe = probe_serial_in_glpi(client, serial, cutoff, with_ip=True)
                    status = _classify(probe, probe["glpi_ip"])
                    error = probe["error"]
                except Exception as exc:
                    logger.exception(f"Автоопрос: ошибка проверки {serial} в GLPI")
                    probe = {
                        "glpi_printer_id": None,
                        "glpi_name": "",
                        "glpi_ip": None,
                        "glpi_counter": None,
                        "glpi_date": None,
                    }
                    status = AutoPollCandidate.ERROR
                    error = f"{exc.__class__.__name__}: {exc}"

                AutoPollCandidate.objects.update_or_create(
                    session=session,
                    serial_number=serial,
                    defaults={
                        "contract_device": device,
                        "status": status,
                        "glpi_printer_id": probe["glpi_printer_id"],
                        "glpi_name": probe["glpi_name"],
                        "glpi_ip": probe["glpi_ip"],
                        "glpi_counter": probe["glpi_counter"],
                        "glpi_date": probe["glpi_date"],
                        "error": error,
                    },
                )
                stats[status] = stats.get(status, 0) + 1

    except GLPIAPIError as exc:
        logger.error(f"Автоопрос: нет связи с GLPI: {exc}")
        raise

    return stats


def verify_candidate(candidate):
    """
    Пробный опрос кандидата без создания принтера: netdiscovery по IP из GLPI.
    Нужен для устаревших в GLPI устройств — если железка отвечает, её можно заводить.
    """
    from inventory.services import extract_device_info_from_xml, run_discovery_for_ip

    candidate.verified_at = timezone.now()

    if not candidate.glpi_ip:
        candidate.verify_ok = False
        candidate.verify_message = "Нет IP-адреса для опроса"
    else:
        ok, payload = run_discovery_for_ip(candidate.glpi_ip, DEFAULT_COMMUNITY)
        if not ok:
            candidate.verify_ok = False
            candidate.verify_message = f"Устройство не ответило: {payload}"[:2000]
        else:
            info = extract_device_info_from_xml(payload)
            found_serial = (info.get("serial") or "").strip()
            if not found_serial:
                candidate.verify_ok = False
                candidate.verify_message = "Устройство ответило, но не отдало серийный номер"
            elif found_serial.lower() != candidate.serial_number.lower():
                candidate.verify_ok = False
                candidate.verify_message = f"По {candidate.glpi_ip} отвечает другое устройство: {found_serial}"
            else:
                candidate.verify_ok = True
                model = " ".join(filter(None, [info.get("manufacturer"), info.get("model")]))
                candidate.verify_message = f"Устройство ответило: {model or found_serial}"

    candidate.save(update_fields=["verify_ok", "verify_message", "verified_at", "checked_at"])
    return candidate


def can_create(candidate):
    """Заводить можно свежее в GLPI либо то, что ответило на пробный опрос."""
    if candidate.created_printer_id:
        return False, "Принтер уже создан"
    if not candidate.glpi_ip:
        return False, "Нет IP-адреса"
    if candidate.contract_device_id is None:
        return False, "Устройство удалено"
    if candidate.status == AutoPollCandidate.IP_CONFLICT:
        return False, f"IP {candidate.glpi_ip} занят другим активным принтером"
    if candidate.status == AutoPollCandidate.GLPI_ACTIVE:
        return True, ""
    if candidate.verify_ok:
        return True, ""
    return False, "Данные в GLPI устарели — сначала выполните пробный опрос"


def create_printers(candidates, user=None):
    """
    Создаёт принтеры по кандидатам и сразу ставит их в очередь опроса.

    Returns:
        list of dict: {candidate_id, serial, created, printer_id, error}
    """
    from inventory.tasks import run_inventory_task_priority

    content_type = ContentType.objects.get_for_model(Printer)
    results = []

    for candidate in candidates:
        allowed, reason = can_create(candidate)
        if not allowed:
            results.append(
                {
                    "candidate_id": candidate.id,
                    "serial": candidate.serial_number,
                    "created": False,
                    "printer_id": None,
                    "error": reason,
                }
            )
            continue

        try:
            with transaction.atomic():
                printer = _create_printer(candidate, content_type, user)
        except Exception as exc:
            logger.exception(f"Автоопрос: не удалось создать принтер для {candidate.serial_number}")
            candidate.error = f"{exc.__class__.__name__}: {exc}"
            if "unique_active_ip" in str(exc):
                candidate.status = AutoPollCandidate.IP_CONFLICT
            candidate.save(update_fields=["error", "status", "checked_at"])
            results.append(
                {
                    "candidate_id": candidate.id,
                    "serial": candidate.serial_number,
                    "created": False,
                    "printer_id": None,
                    "error": candidate.error,
                }
            )
            continue

        run_inventory_task_priority.delay(printer.id, user.id if user else None)
        results.append(
            {
                "candidate_id": candidate.id,
                "serial": candidate.serial_number,
                "created": True,
                "printer_id": printer.id,
                "error": "",
            }
        )

    return results


def _create_printer(candidate, content_type, user):
    device = candidate.contract_device
    printer = Printer.objects.create(
        ip_address=candidate.glpi_ip,
        serial_number=candidate.serial_number,
        device_model=device.model,
        model=str(device.model) if device.model else "",
        snmp_community=DEFAULT_COMMUNITY,
        organization=device.organization,
        polling_method=PollingMethod.SNMP,
        connection_type=ConnectionType.NETWORK,
        is_active=True,
    )

    EntityChangeLog.objects.create(
        content_type=content_type,
        object_id=printer.id,
        action="create",
        user=user,
        object_repr=str(printer)[:500],
        changes={"source": {"old": None, "new": f"автозаведение по GLPI #{candidate.glpi_printer_id}"}},
    )

    if not device.printer_id:
        device.printer = printer
        device.save(update_fields=["printer", "updated_at"])

    candidate.created_printer = printer
    candidate.error = ""
    candidate.save(update_fields=["created_printer", "error", "checked_at"])

    return printer


def candidate_payload(candidate):
    """Сериализация кандидата для фронта."""
    device = candidate.contract_device
    printer = candidate.created_printer
    last_task = None
    if printer:
        task = InventoryTask.objects.filter(printer=printer).order_by("-task_timestamp").first()
        if task:
            last_task = {
                "status": task.status,
                "timestamp": task.task_timestamp.isoformat(),
                "error": task.error_message or "",
            }

    return {
        "id": candidate.id,
        "serial": candidate.serial_number,
        "status": candidate.status,
        "status_display": candidate.get_status_display(),
        "organization": device.organization.name if device and device.organization else "",
        "model": str(device.model) if device and device.model else "",
        "address": device.address if device else "",
        "glpi_printer_id": candidate.glpi_printer_id,
        "glpi_name": candidate.glpi_name,
        "glpi_ip": candidate.glpi_ip,
        "glpi_counter": candidate.glpi_counter,
        "glpi_date": candidate.glpi_date.isoformat() if candidate.glpi_date else None,
        "verify_ok": candidate.verify_ok,
        "verify_message": candidate.verify_message,
        "can_create": can_create(candidate)[0],
        "printer_id": candidate.created_printer_id,
        "last_task": last_task,
        "error": candidate.error,
    }
