"""
Сканирование сетей (VLAN) в поисках принтеров и сверка найденного с опросом и договорами.

Сеть сканируется glpi-netdiscovery по диапазону (--first/--last) кусками по NETSCAN_CHUNK_PREFIX
(по умолчанию /26 = 64 адреса): у Celery-задачи жёсткий лимит 15 минут, кусок обязан в него влезть.

Сверка каждого найденного устройства (ключ — серийник, затем MAC):
  * опрашивается и IP совпадает                         → OK;
  * опрашивается на другом IP                           → переносим IP, если на старом адресе устройства
    больше нет и MAC совпадает (MAC проверяем, потому что после перепрошивки серийник бывает другой);
    иначе оставляем на ручную проверку;
  * есть в договоре, но не опрашивается                 → заводим в опрос автоматически;
  * нет ни в опросе, ни в договоре                      → «нет в договоре», на разбор.
После последнего куска принтеры из этой сети, которых скан не увидел, получают счётчик пропусков.
"""

import glob
import ipaddress
import logging
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Lower
from django.utils import timezone

from .models import (
    ConnectionType,
    DiscoveredDevice,
    NetworkScanRun,
    PollingMethod,
    Printer,
    PrinterChangeLog,
    ScanNetwork,
)
from .utils import mac_equal, normalize_mac, run_glpi_command

logger = logging.getLogger(__name__)

TRIGGERED_BY = "net_scan"
PRINTER_TYPE = "PRINTER"


def _setting(name, default):
    return getattr(settings, name, default)


def chunk_prefix() -> int:
    return int(_setting("NETSCAN_CHUNK_PREFIX", 26))


def max_hosts() -> int:
    return int(_setting("NETSCAN_MAX_HOSTS", 65536))


def missing_after() -> int:
    return int(_setting("NETSCAN_MISSING_AFTER", 3))


# ──────────────────────────────────────────────────────────────────────────────
# ДИАПАЗОНЫ
# ──────────────────────────────────────────────────────────────────────────────


def parse_cidr(value: str) -> ipaddress.IPv4Network:
    """Нормализует ввод пользователя: '10.1.2.5/24' → 10.1.2.0/24. Бросает ValueError."""
    net = ipaddress.ip_network((value or "").strip(), strict=False)
    if net.version != 4:
        raise ValueError("Поддерживаются только IPv4-сети")
    if net.num_addresses > max_hosts():
        raise ValueError(f"Сеть слишком большая: {net.num_addresses} адресов (максимум {max_hosts()})")
    return net


def network_chunks(cidr: str) -> List[Tuple[str, str]]:
    """Делит сеть на куски (first_ip, last_ip) по chunk_prefix(); адрес сети и broadcast не сканируем."""
    net = parse_cidr(cidr)
    prefix = chunk_prefix()
    subnets = [net] if net.prefixlen >= prefix else list(net.subnets(new_prefix=prefix))

    chunks = []
    for sub in subnets:
        if sub.num_addresses <= 2:
            first, last = sub[0], sub[-1]
        else:
            first, last = sub[0], sub[-1]
            if sub[0] == net.network_address:
                first = sub[1]
            if sub[-1] == net.broadcast_address:
                last = sub[-2]
        chunks.append((str(first), str(last)))
    return chunks


def ip_in_network(ip: str, cidr: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# ЗАПУСК GLPI-NETDISCOVERY ПО ДИАПАЗОНУ
# ──────────────────────────────────────────────────────────────────────────────


def _wrap_sudo(cmd: str) -> str:
    """Тот же sudo/GLPI_USER, что и у точечного discovery в services.py."""
    from .services import PLATFORM

    if PLATFORM in ("linux", "darwin"):
        glpi_user = _setting("GLPI_USER", "")
        if os.geteuid() == 0:
            return f"/usr/bin/sudo -u {glpi_user} {cmd}" if glpi_user else f"/usr/bin/sudo {cmd}"
        if _setting("GLPI_USE_SUDO", True):
            return f"/usr/bin/sudo {cmd}"
    return cmd


def run_range_discovery(first_ip: str, last_ip: str, community: str) -> Tuple[bool, List[Dict], str]:
    """
    Сканирует диапазон одним запуском glpi-netdiscovery.

    Returns:
        (ok, devices, error): devices — список словарей parse_discovery_xml().
    """
    from .services import OUTPUT_DIR, _get_glpi_discovery_path, _validate_community, _validate_ip

    if not (_validate_ip(first_ip) and _validate_ip(last_ip)):
        return False, [], f"Некорректный диапазон {first_ip}–{last_ip}"
    if not _validate_community(community):
        return False, [], "Некорректный SNMP community"

    # Свой каталог на кусок — чтобы не пересекаться с обычным опросом в inventory_output/netdiscovery
    save_dir = os.path.join(OUTPUT_DIR, "netscan", f"{first_ip}-{last_ip}")
    shutil.rmtree(save_dir, ignore_errors=True)
    os.makedirs(save_dir, exist_ok=True)

    threads = int(_setting("NETSCAN_THREADS", 20))
    timeout = int(_setting("NETSCAN_SNMP_TIMEOUT", 1))
    cmd = (
        f'"{_get_glpi_discovery_path()}" --first {first_ip} --last {last_ip} --community {community} '
        f'--threads {threads} --timeout {timeout} --save="{save_dir}"'
    )
    try:
        ok, out = run_glpi_command(_wrap_sudo(cmd), timeout=int(_setting("NETSCAN_CHUNK_TIMEOUT", 600)))
        files = glob.glob(os.path.join(save_dir, "netdiscovery", "*.xml")) + glob.glob(os.path.join(save_dir, "*.xml"))
        devices = [d for d in (parse_discovery_xml(f) for f in files) if d]
        if not ok and not devices:
            return False, [], (out or "netdiscovery завершился с ошибкой")[:2000]
        return True, devices, ""
    finally:
        shutil.rmtree(save_dir, ignore_errors=True)


def parse_discovery_xml(path: str) -> Optional[Dict]:
    """Достаёт из XML netdiscovery первые IP, MAC, SERIAL, TYPE, MANUFACTURER, MODEL, SNMPHOSTNAME."""
    wanted = {
        "IP": "ip",
        "MAC": "mac",
        "SERIAL": "serial",
        "TYPE": "type",
        "MANUFACTURER": "manufacturer",
        "MODEL": "model",
        "SNMPHOSTNAME": "name",
    }
    info = {v: "" for v in wanted.values()}
    try:
        for _, elem in ET.iterparse(path, events=("end",)):
            field = wanted.get(str(elem.tag).split("}", 1)[-1].upper())
            if field and not info[field]:
                info[field] = (elem.text or "").strip()
    except (ET.ParseError, OSError):
        logger.warning(f"netscan: не разобрал {path}")
        return None

    if not info["ip"]:
        info["ip"] = os.path.splitext(os.path.basename(path))[0]
    try:
        ipaddress.IPv4Address(info["ip"])
    except ValueError:
        return None
    info["mac"] = normalize_mac(info["mac"]) or ""
    info["type"] = info["type"].upper()
    return info


# ──────────────────────────────────────────────────────────────────────────────
# СВЕРКА
# ──────────────────────────────────────────────────────────────────────────────


def _identity(serial: str, mac: str, duplicate: bool = False) -> str:
    if serial and duplicate and mac:
        # Один серийник у нескольких устройств (перепрошивка): различаем их по MAC
        return f"sn:{serial.lower()}|mac:{mac}"[:150]
    if serial:
        return f"sn:{serial.lower()}"[:150]
    return f"mac:{mac}"


def duplicate_days() -> int:
    return int(_setting("NETSCAN_DUPLICATE_DAYS", 3))


def _is_duplicate_serial(network: ScanNetwork, serial: str, mac: str, since=None) -> bool:
    """
    Отдаёт ли этот серийник ещё какое-то устройство с другим MAC.
      * уже помечен как одинаковый (где угодно) — да;
      * в этой сети другой MAC отвечал в текущем прогоне (since) — да; ответ с другим MAC из прошлых
        прогонов этой же сети — скорее заменённая сетевая карта того же принтера, не считаем;
      * в другой сети другой MAC отвечал за последние NETSCAN_DUPLICATE_DAYS дней — да.
    """
    if not serial or not mac:
        return False
    same_serial = DiscoveredDevice.objects.filter(serial_number__iexact=serial)
    if same_serial.filter(status=DiscoveredDevice.DUPLICATE_SERIAL).exists():
        return True
    others = same_serial.exclude(mac_address="").exclude(mac_address__iexact=mac).exclude(last_seen__isnull=True)
    if since is None:
        since = timezone.now() - timedelta(days=duplicate_days())
    if others.filter(network=network, last_seen__gte=since).exists():
        return True
    window = timezone.now() - timedelta(days=duplicate_days())
    return others.exclude(network=network).filter(last_seen__gte=window).exists()


def _mark_duplicates(serial: str) -> None:
    """Записи с этим серийником, заведённые до того, как выяснилось, что он не уникален, переводим на ключ по MAC."""
    message = _duplicate_message(serial)
    for record in DiscoveredDevice.objects.filter(identity=_identity(serial, "")).exclude(mac_address=""):
        record.identity = _identity(serial, record.mac_address, duplicate=True)
        record.status, record.message = DiscoveredDevice.DUPLICATE_SERIAL, message
        try:
            with transaction.atomic():
                record.save(update_fields=["identity", "status", "message", "updated_at"])
        except IntegrityError:  # запись с таким MAC в сети уже есть — старая не нужна
            record.delete()


def _duplicate_message(serial: str) -> str:
    macs = (
        DiscoveredDevice.objects.filter(serial_number__iexact=serial)
        .exclude(mac_address="")
        .values_list("mac_address", flat=True)
        .distinct()
        .count()
    )
    return (
        f"Серийник {serial} отдают несколько устройств (разных MAC: {max(macs, 2)}) — вероятно, перепрошивка. "
        f"Автоматически ничего не делаем"
    )


def _active_network_printers():
    return Printer.objects.filter(is_active=True, connection_type=ConnectionType.NETWORK)


def _find_printer(serial: str, mac: str, ip: str) -> Optional[Printer]:
    """Ищет активный принтер: сначала по серийнику (предпочитая тот же IP), затем по MAC."""
    qs = _active_network_printers().select_related("device_model", "organization")
    if serial:
        found = list(qs.annotate(sn=Lower("serial_number")).filter(sn=serial.lower()))
        if found:
            return next((p for p in found if p.ip_address == ip), found[0])
    if mac:
        return qs.filter(mac_address__iexact=mac).first()
    return None


def _find_contract_device(serial: str, network: ScanNetwork):
    from contracts.models import ContractDevice

    if not serial:
        return None, ""
    candidates = list(
        ContractDevice.objects.filter(serial_number__iexact=serial).select_related(
            "organization", "model", "model__manufacturer", "printer"
        )
    )
    if len(candidates) == 1:
        return candidates[0], ""
    if not candidates:
        return None, ""
    org_names = {o.name for o in network.organizations.all()}
    by_org = [c for c in candidates if c.organization.name in org_names]
    if len(by_org) == 1:
        return by_org[0], ""
    orgs = ", ".join(sorted({c.organization.name for c in candidates}))
    return None, f"Серийник {serial} есть в договорах нескольких организаций ({orgs}) — укажите нужную у сети"


def _device_answers_at(ip: str, community: str, serial: str, mac: str) -> bool:
    """Отвечает ли по ip то же самое устройство (по серийнику или MAC)."""
    ok, devices, _ = run_range_discovery(ip, ip, community)
    if not ok:
        return False
    for d in devices:
        if serial and d["serial"] and d["serial"].lower() == serial.lower():
            return True
        if mac and mac_equal(d["mac"], mac):
            return True
    return False


def move_printer_ip(printer: Printer, new_ip: str, new_mac: str = "", comment: str = "", manual=False) -> Printer:
    """Переносит принтер на новый IP с записью в PrinterChangeLog."""
    old_ip = printer.ip_address
    old_values = {"ip_address": old_ip}
    new_values = {"ip_address": new_ip}
    update_fields = ["ip_address"]
    printer.ip_address = new_ip
    if new_mac and not printer.mac_address:
        old_values["mac_address"] = printer.mac_address
        new_values["mac_address"] = new_mac
        printer.mac_address = new_mac
        update_fields.append("mac_address")
    with transaction.atomic():
        printer.save(update_fields=update_fields)
        PrinterChangeLog.objects.create(
            printer=printer,
            action="ip_change",
            old_values=old_values,
            new_values=new_values,
            comment=comment or f"Сканирование сети: принтер переехал с {old_ip} на {new_ip}",
            triggered_by="manual" if manual else TRIGGERED_BY,
        )
    return printer


def _create_printer_from_contract(device, ip: str, mac: str, serial: str, community: str) -> Printer:
    from access.models import EntityChangeLog

    with transaction.atomic():
        printer = Printer.objects.create(
            ip_address=ip,
            serial_number=serial,
            mac_address=mac or None,
            device_model=device.model,
            model=str(device.model) if device.model else "",
            snmp_community=community,
            organization=device.organization,
            polling_method=PollingMethod.SNMP,
            connection_type=ConnectionType.NETWORK,
            is_active=True,
        )
        EntityChangeLog.objects.create(
            content_type=ContentType.objects.get_for_model(Printer),
            object_id=printer.id,
            action="create",
            user=None,
            object_repr=str(printer)[:500],
            changes={"source": {"old": None, "new": f"сканирование сети, найден на {ip}"}},
        )
        device.printer = printer
        device.save(update_fields=["printer", "updated_at"])
    return printer


def _queue_poll(printer: Printer) -> None:
    from .tasks import run_inventory_task_priority

    try:
        run_inventory_task_priority.delay(printer.id, None)
    except Exception:
        logger.exception(f"netscan: не удалось поставить опрос принтера {printer.id}")


def reconcile_device(network: ScanNetwork, info: Dict, since=None) -> Optional[DiscoveredDevice]:
    """
    Сверяет одно найденное устройство и сохраняет итог. Возвращает запись или None, если это не принтер.
    since — начало текущего прогона (для поиска одинаковых серийников внутри скана).
    """
    ip, serial, mac = info["ip"], (info.get("serial") or "").strip(), info.get("mac") or ""
    if not serial and not mac:
        return None

    duplicate = _is_duplicate_serial(network, serial, mac, since)
    if duplicate:
        # По такому серийнику нельзя ни искать принтер, ни заводить из договора — только по MAC и только показать
        printer = _active_network_printers().filter(mac_address__iexact=mac).first()
        contract_device, ambiguity = None, ""
    else:
        printer = _find_printer(serial, mac, ip)
        contract_device, ambiguity = (None, "") if printer else _find_contract_device(serial, network)

    # Чужие коммутаторы/камеры не храним: оставляем принтеры и всё, что мы уже знаем.
    if info.get("type") != PRINTER_TYPE and not printer and not contract_device and not ambiguity:
        return None

    status, message = DiscoveredDevice.NOT_IN_CONTRACT, ""
    printer_at_ip = _active_network_printers().filter(ip_address=ip).first()

    if duplicate:
        _mark_duplicates(serial)
        status, message = DiscoveredDevice.DUPLICATE_SERIAL, _duplicate_message(serial)
        if printer:
            message += f"; по MAC это принтер из опроса {printer.ip_address}"
    elif printer:
        if printer.ip_address == ip:
            status = DiscoveredDevice.OK
            if serial and printer.serial_number and serial.lower() != printer.serial_number.lower():
                message = f"Найден по MAC, но отдаёт серийник {serial} (в опросе {printer.serial_number})"
        else:
            status, message = _try_move(network, printer, ip, serial, mac, printer_at_ip)
    elif ambiguity:
        status, message = DiscoveredDevice.CONFLICT, ambiguity
    elif contract_device:
        linked = contract_device.printer
        if linked and linked.is_active:
            status = DiscoveredDevice.CONFLICT
            message = (
                f"Устройство из договора связано с принтером {linked.ip_address} (SN {linked.serial_number}), "
                f"а по {ip} отвечает SN {serial}"
            )
        elif printer_at_ip:
            status = DiscoveredDevice.CONFLICT
            message = f"IP {ip} в опросе занят принтером SN {printer_at_ip.serial_number}"
        else:
            try:
                printer = _create_printer_from_contract(contract_device, ip, mac, serial, network.snmp_community)
            except Exception as exc:
                logger.exception(f"netscan: не удалось завести {serial} ({ip})")
                status, message = DiscoveredDevice.CONFLICT, f"Не удалось завести в опрос: {exc}"[:2000]
            else:
                status, message = DiscoveredDevice.ADDED, f"Заведён в опрос: {contract_device.organization.name}"
                _queue_poll(printer)

    defaults = {
        "ip_address": ip,
        "serial_number": serial,
        "mac_address": mac,
        "manufacturer": info.get("manufacturer") or "",
        "model": info.get("model") or "",
        "device_type": info.get("type") or "",
        "snmp_name": (info.get("name") or "")[:200],
        "printer": printer,
        "contract_device": contract_device or (getattr(printer, "contract_device", None) if printer else None),
        "missed_scans": 0,
        "last_seen": timezone.now(),
    }
    record, created = DiscoveredDevice.objects.get_or_create(
        network=network,
        identity=_identity(serial, mac, duplicate),
        defaults={**defaults, "status": status, "message": message},
    )
    if not created:
        # Однажды выполненные действия не затираем при следующем скане, пока устройство на том же месте
        keep = record.status in (DiscoveredDevice.IP_CHANGED, DiscoveredDevice.ADDED) and status == DiscoveredDevice.OK
        for field, value in defaults.items():
            setattr(record, field, value)
        if not keep:
            record.status, record.message = status, message
        record.save()
    return record


def _try_move(network, printer, ip, serial, mac, printer_at_ip) -> Tuple[str, str]:
    old_ip = printer.ip_address
    pending = DiscoveredDevice.IP_CHANGE_PENDING
    if printer_at_ip and printer_at_ip.id != printer.id:
        return pending, f"Новый IP {ip} в опросе занят принтером SN {printer_at_ip.serial_number}"
    if not printer.mac_address:
        return pending, f"Был на {old_ip}; в опросе нет MAC — не с чем сверить, перенесите вручную"
    if not mac_equal(printer.mac_address, mac):
        return pending, f"Был на {old_ip}; MAC не совпадает ({printer.mac_address} ≠ {mac or '—'})"
    if _device_answers_at(old_ip, printer.snmp_community or network.snmp_community, serial, mac):
        return pending, f"Устройство отвечает и на старом адресе {old_ip}"
    move_printer_ip(printer, ip)
    _queue_poll(printer)
    return DiscoveredDevice.IP_CHANGED, f"IP обновлён: {old_ip} → {ip}"


def _in_ranges(ip: str, ranges) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip)
        return any(ipaddress.IPv4Address(a) <= addr <= ipaddress.IPv4Address(b) for a, b in ranges)
    except ValueError:
        return False


def mark_missing(network: ScanNetwork, seen_identities: set, failed_ranges=()) -> int:
    """
    Принтеры из этой сети, которых скан не увидел: счётчик пропусков, после N подряд — статус «не отвечает».
    Адреса из кусков, которые не удалось просканировать, не трогаем — там мы ничего не знаем.
    """
    now = timezone.now()
    missing = 0
    printers = [
        p
        for p in _active_network_printers()
        if ip_in_network(p.ip_address, network.cidr) and not _in_ranges(p.ip_address, failed_ranges)
    ]
    for printer in printers:
        identity = _identity((printer.serial_number or "").strip(), normalize_mac(printer.mac_address) or "")
        if identity in seen_identities or identity == "mac:":
            continue
        # Новую запись заводим со статусом MISSING, но «не отвечающим» он считается только после N пропусков
        # подряд (is_missing()): один пропущенный скан — это часто просто выключенный на ночь принтер.
        record, _ = DiscoveredDevice.objects.get_or_create(
            network=network,
            identity=identity,
            defaults={
                "ip_address": printer.ip_address,
                "serial_number": printer.serial_number or "",
                "mac_address": normalize_mac(printer.mac_address) or "",
                "status": DiscoveredDevice.MISSING,
                "printer": printer,
            },
        )
        DiscoveredDevice.objects.filter(pk=record.pk).update(missed_scans=F("missed_scans") + 1, updated_at=now)
        record.refresh_from_db()
        record.printer = printer
        if record.missed_scans >= missing_after():
            record.status = DiscoveredDevice.MISSING
            record.message = f"Не отвечает {record.missed_scans} сканов подряд (адрес в опросе {printer.ip_address})"
            missing += 1
        else:
            record.message = f"Не ответил на скане ({record.missed_scans} из {missing_after()})"
        record.save(update_fields=["status", "message", "printer", "updated_at"])
    return missing


def visible_missing_q():
    """Фильтр «не отвечает»: статус MISSING и порог пропусков достигнут."""
    from django.db.models import Q

    return Q(status=DiscoveredDevice.MISSING, missed_scans__gte=missing_after())


# ──────────────────────────────────────────────────────────────────────────────
# ПРОГОН
# ──────────────────────────────────────────────────────────────────────────────


def start_run(network: ScanNetwork, user=None) -> Optional[NetworkScanRun]:
    """Создаёт прогон, если по сети сейчас ничего не выполняется. Иначе None."""
    stale = timezone.now() - timedelta(hours=int(_setting("NETSCAN_STALE_RUN_HOURS", 12)))
    with transaction.atomic():
        ScanNetwork.objects.select_for_update().get(pk=network.pk)
        running = network.runs.filter(status=NetworkScanRun.RUNNING)
        running.filter(started_at__lt=stale).update(
            status=NetworkScanRun.ERROR, finished_at=timezone.now(), error="Прогон завис и был сброшен"
        )
        if running.filter(started_at__gte=stale).exists():
            return None
        return NetworkScanRun.objects.create(
            network=network, chunks_total=len(network_chunks(network.cidr)), triggered_by=user
        )


def scan_chunk(run: NetworkScanRun, index: int) -> Dict[str, int]:
    """Сканирует кусок index прогона и сверяет найденное. Возвращает счётчики куска."""
    network = run.network
    chunks = network_chunks(network.cidr)
    if index >= len(chunks):  # сеть успели отредактировать посреди прогона
        return {}
    first_ip, last_ip = chunks[index]
    counts: Dict[str, int] = {}
    seen = set()
    failed = []

    # Для живого прогресса на странице: какой диапазон сканируется прямо сейчас
    with transaction.atomic():
        locked = NetworkScanRun.objects.select_for_update().get(pk=run.pk)
        locked.stats = {
            **locked.stats,
            "_current": f"{first_ip} – {last_ip}",
            "_current_since": timezone.now().isoformat(),
        }
        locked.save(update_fields=["stats"])

    ok, devices, error = run_range_discovery(first_ip, last_ip, network.snmp_community)
    if not ok:
        logger.warning(f"netscan {network.cidr}: кусок {first_ip}-{last_ip}: {error}")
        counts["chunk_errors"] = 1
        failed.append([first_ip, last_ip])
        NetworkScanRun.objects.filter(pk=run.pk).update(error=(run.error + f"{first_ip}-{last_ip}: {error}\n")[-10000:])
    else:
        for info in devices:
            try:
                record = reconcile_device(network, info, since=run.started_at)
            except Exception:
                logger.exception(f"netscan: ошибка сверки {info.get('ip')}")
                counts["errors"] = counts.get("errors", 0) + 1
                continue
            if record:
                counts[record.status] = counts.get(record.status, 0) + 1
                seen.add(record.identity)
                if record.status == DiscoveredDevice.DUPLICATE_SERIAL and record.serial_number:
                    # принтер из опроса с этим серийником мог ответить — не считаем его пропавшим
                    seen.add(_identity(record.serial_number, ""))
                if record.printer_id:
                    # принтер мог найтись по MAC с другим серийником — он тоже «увиден»
                    p = record.printer
                    seen.add(_identity((p.serial_number or "").strip(), normalize_mac(p.mac_address) or ""))
        counts["responded"] = len(devices)

    with transaction.atomic():
        locked = NetworkScanRun.objects.select_for_update().get(pk=run.pk)
        stats = dict(locked.stats)
        stats["_seen"] = sorted(set(stats.get("_seen", [])) | seen)
        stats["_failed"] = stats.get("_failed", []) + failed
        stats.pop("_current", None)
        stats.pop("_current_since", None)
        for key, value in counts.items():
            stats[key] = stats.get(key, 0) + value
        locked.stats = stats
        locked.chunks_done = F("chunks_done") + 1
        locked.save(update_fields=["stats", "chunks_done"])
    return counts


def finish_run(run: NetworkScanRun) -> NetworkScanRun:
    run.refresh_from_db()
    network = run.network
    stats = dict(run.stats)
    seen = set(stats.pop("_seen", []))
    failed = stats.pop("_failed", [])
    stats.pop("_current", None)
    stats.pop("_current_since", None)
    stats[DiscoveredDevice.MISSING] = mark_missing(network, seen, failed)
    stats["chunks"] = run.chunks_total
    run.stats = stats
    run.finished_at = timezone.now()
    all_failed = stats.get("chunk_errors", 0) >= run.chunks_total > 0
    run.status = NetworkScanRun.ERROR if all_failed else NetworkScanRun.SUCCESS
    run.save(update_fields=["stats", "finished_at", "status"])
    ScanNetwork.objects.filter(pk=network.pk).update(last_scan_at=run.finished_at)
    logger.info(f"netscan {network.cidr}: готово, {stats}")
    return run


def _chunk_size(first_ip: str, last_ip: str) -> int:
    return int(ipaddress.IPv4Address(last_ip)) - int(ipaddress.IPv4Address(first_ip)) + 1


def run_progress(run: NetworkScanRun) -> Dict:
    """Состояние прогона для живого обновления страницы."""
    chunks = network_chunks(run.network.cidr)
    done = min(run.chunks_done, len(chunks))
    stats = run.stats or {}
    status_names = dict(DiscoveredDevice.STATUS_CHOICES)
    found = (
        DiscoveredDevice.objects.filter(network=run.network, last_seen__gte=run.started_at)
        .select_related("printer", "contract_device__organization")
        .order_by("-updated_at")[:200]
    )
    return {
        "id": run.id,
        "status": run.status,
        "status_display": run.get_status_display(),
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "chunks_done": run.chunks_done,
        "chunks_total": run.chunks_total,
        "addresses_done": sum(_chunk_size(a, b) for a, b in chunks[:done]),
        "addresses_total": sum(_chunk_size(a, b) for a, b in chunks),
        "current_range": stats.get("_current", ""),
        "current_since": stats.get("_current_since"),
        # прогон создан, но ни один кусок ещё не взят воркером — очередь занята или воркер не запущен
        "waiting_for_worker": run.status == NetworkScanRun.RUNNING
        and run.chunks_done == 0
        and not stats.get("_current"),
        "responded": stats.get("responded", 0),
        "counts": {
            key: {"title": status_names.get(key, key), "value": value}
            for key, value in stats.items()
            if not key.startswith("_") and key in status_names
        },
        "chunk_errors": stats.get("chunk_errors", 0),
        "error": run.error[-2000:],
        "devices": [
            {
                "ip": d.ip_address,
                "serial": d.serial_number,
                "mac": d.mac_address,
                "model": f"{d.manufacturer} {d.model}".strip(),
                "status": d.status,
                "status_display": d.get_status_display(),
                "message": d.message,
                "organization": d.contract_device.organization.name if d.contract_device_id else "",
            }
            for d in found
        ],
    }


def due_networks():
    """Включённые сети, которые пора сканировать."""
    now = timezone.now()
    result = []
    for network in ScanNetwork.objects.filter(is_enabled=True):
        if not network.last_scan_at or network.last_scan_at + timedelta(hours=network.scan_interval_hours) <= now:
            result.append(network)
    return result


def networks_progress() -> Dict:
    """Сводный прогресс сканирования и сверки с GLPI по всем сетям — для страницы списка сетей."""
    from .services_netscan_glpi import is_check_running

    running_runs = {
        run.network_id: run
        for run in NetworkScanRun.objects.filter(status=NetworkScanRun.RUNNING).order_by("started_at")
    }
    rows = []
    scan_done = scan_total = glpi_done = glpi_total = 0
    for network in ScanNetwork.objects.order_by("name"):
        row = {"id": network.id, "scan": None, "glpi": None}
        run = running_runs.get(network.id)
        if run:
            chunks = network_chunks(network.cidr)
            done = sum(_chunk_size(a, b) for a, b in chunks[: min(run.chunks_done, len(chunks))])
            total = sum(_chunk_size(a, b) for a, b in chunks)
            row["scan"] = {
                "done": done,
                "total": total,
                "chunks_done": run.chunks_done,
                "chunks_total": run.chunks_total,
            }
            scan_done, scan_total = scan_done + done, scan_total + total
        if is_check_running(network):
            row["glpi"] = {"done": network.glpi_check_done, "total": network.glpi_check_total}
            glpi_done, glpi_total = glpi_done + network.glpi_check_done, glpi_total + network.glpi_check_total
        rows.append(row)
    return {
        "networks": rows,
        "scan": {"running": sum(1 for r in rows if r["scan"]), "done": scan_done, "total": scan_total},
        "glpi": {"running": sum(1 for r in rows if r["glpi"]), "done": glpi_done, "total": glpi_total},
    }
