"""
Сверка найденных сканированием сети устройств с GLPI: опрашивает ли их GLPI.

Нужна потому, что в GLPI организаций больше, чем в наших договорах: принтер может не опрашиваться
ни нами, ни GLPI. По каждому устройству сети (и нашему, и чужому):
  * ищем карточку по серийнику — стандартное поле и кастомное «серийный номер на бирке»
    (тот же GLPIClient.search_printer_by_serial, что и в contracts);
  * несколько карточек — выбираем по MAC сетевого порта; по серийнику пусто — ищем по MAC;
  * у найденной карточки смотрим последний SNMP-опрос (PrinterLog) и IP сетевого порта.

Итог (DiscoveredDevice.glpi_status):
  active    — счётчик свежее GLPI_FRESHNESS_DAYS и IP совпадает (или в GLPI его нет);
  other_ip  — счётчик свежий, но в GLPI записан другой IP;
  stale     — счётчик старый или его нет;
  not_found — карточки нет; multiple — несколько карточек, MAC не помог; error — сбой запроса.

Запускается кнопкой на странице сети, задачей в очереди netscan, пачками по NETSCAN_GLPI_BATCH.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import DiscoveredDevice, ScanNetwork
from .utils import mac_equal

logger = logging.getLogger(__name__)


def batch_size() -> int:
    return int(getattr(settings, "NETSCAN_GLPI_BATCH", 40))


def freshness_days() -> int:
    return int(getattr(settings, "GLPI_FRESHNESS_DAYS", 7))


def devices_to_check(network: ScanNetwork):
    """Устройства, которые реально отвечали на скане (записи «не отвечает» без ответа не сверяем)."""
    return network.devices.filter(last_seen__isnull=False)


# ──────────────────────────────────────────────────────────────────────────────
# ОДНО УСТРОЙСТВО
# ──────────────────────────────────────────────────────────────────────────────


def _item_id(item: Dict) -> Optional[int]:
    value = item.get("2") or item.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _exact_serial(items: List[Dict], serial: str) -> List[Dict]:
    """Поиск в GLPI идёт по 'contains': ABC1 находит и ABC12. Оставляем карточки, где серийник совпал целиком."""
    wanted = serial.strip().lower()
    exact = [
        i for i in items if any(isinstance(v, (str, int)) and str(v).strip().lower() == wanted for v in i.values())
    ]
    return exact or items


def _find_cards(client, serial: str, mac: str) -> Tuple[str, List[int], str, Dict[int, List[Dict]]]:
    """
    Returns: (status, card_ids, how, ports_cache)
      status: FOUND / NOT_FOUND / MULTIPLE / ERROR; how — чем нашли («серийник», «MAC», «серийник + MAC»).
    """
    ports: Dict[int, List[Dict]] = {}

    def card_ports(card_id):
        if card_id not in ports:
            ports[card_id] = client.get_printer_ports(card_id)
        return ports[card_id]

    ids: List[int] = []
    how = ""
    if serial:
        status, items, error = client.search_printer_by_serial(serial)
        if status == "ERROR":
            return "ERROR", [], error or "ошибка поиска по серийнику", ports
        ids = list(dict.fromkeys(i for i in (_item_id(x) for x in _exact_serial(items, serial)) if i))
        how = "серийник"

    if not ids and mac:
        status, ids, error = client.search_printer_ids_by_mac(mac)
        if status == "ERROR":
            return "ERROR", [], error or "ошибка поиска по MAC", ports
        how = "MAC"

    if not ids:
        return "NOT_FOUND", [], how, ports

    if len(ids) > 1 and mac:
        by_mac = [i for i in ids if any(mac_equal(p["mac"], mac) for p in card_ports(i))]
        if len(by_mac) == 1:
            return "FOUND", by_mac, f"{how} + MAC", ports
        return "MULTIPLE", ids, how, ports
    if len(ids) > 1:
        return "MULTIPLE", ids, how, ports
    return "FOUND", ids, how, ports


def probe_device(client, device: DiscoveredDevice, cutoff) -> Dict:
    """Проверяет одно устройство в GLPI. Возвращает поля glpi_* для DiscoveredDevice."""
    from integrations.glpi.services import _parse_glpi_date

    serial, mac = (device.serial_number or "").strip(), device.mac_address or ""
    result = {
        "glpi_status": DiscoveredDevice.GLPI_ERROR,
        "glpi_message": "",
        "glpi_printer_id": None,
        "glpi_name": "",
        "glpi_entity": "",
        "glpi_ip": "",
        "glpi_last_inventory": None,
        "glpi_counter": None,
    }
    status, ids, how, ports = _find_cards(client, serial, mac)
    if status == "ERROR":
        result["glpi_message"] = how[:2000]
        return result
    if status == "NOT_FOUND":
        result["glpi_status"] = DiscoveredDevice.GLPI_NOT_FOUND
        result["glpi_message"] = "Не найден ни по серийнику, ни по MAC" if mac and serial else "Не найден"
        return result
    if status == "MULTIPLE":
        result["glpi_status"] = DiscoveredDevice.GLPI_MULTIPLE
        result["glpi_message"] = f"По {how} карточек: {len(ids)} (ID {', '.join(map(str, ids[:10]))}), MAC не помог"
        return result

    card_id = ids[0]
    result["glpi_printer_id"] = card_id
    detail = client.get_printer(card_id) or {}
    result["glpi_name"] = (detail.get("name") or "")[:255]
    try:
        result["glpi_entity"] = client.get_entity_name(int(detail.get("entities_id")))[:500]
    except (TypeError, ValueError):
        pass
    try:
        result["glpi_counter"] = int(detail["last_pages_counter"])
    except (KeyError, TypeError, ValueError):
        pass

    log = client.get_printer_log(card_id)
    if log:
        result["glpi_last_inventory"] = _parse_glpi_date(log[0].get("date"))
        try:
            result["glpi_counter"] = int(log[0]["total_pages"])
        except (KeyError, TypeError, ValueError):
            pass

    card_ports = ports.get(card_id)
    if card_ports is None:
        card_ports = client.get_printer_ports(card_id)
    card_ips = sorted({p["ip"] for p in card_ports if p.get("ip")})
    result["glpi_ip"] = ", ".join(card_ips)[:100]

    notes = [f"найден по {how}"]
    if mac and card_ports and not any(mac_equal(p["mac"], mac) for p in card_ports if p.get("mac")):
        card_macs = ", ".join(sorted({p["mac"] for p in card_ports if p.get("mac")})) or "нет"
        notes.append(f"MAC в карточке другой ({card_macs})")

    fresh = bool(result["glpi_last_inventory"] and result["glpi_last_inventory"] >= cutoff and result["glpi_counter"])
    ip_ok = not card_ips or device.ip_address in card_ips
    if not fresh:
        result["glpi_status"] = DiscoveredDevice.GLPI_STALE
        last = result["glpi_last_inventory"]
        notes.insert(0, f"последний опрос {timezone.localtime(last):%d.%m.%Y}" if last else "опросов в GLPI нет")
        if not ip_ok:
            notes.append(f"в GLPI IP {result['glpi_ip']}, в сети {device.ip_address}")
    elif not ip_ok:
        result["glpi_status"] = DiscoveredDevice.GLPI_OTHER_IP
        notes.insert(0, f"в GLPI IP {result['glpi_ip']}, в сети {device.ip_address}")
    else:
        result["glpi_status"] = DiscoveredDevice.GLPI_ACTIVE
    result["glpi_message"] = "; ".join(notes)[:2000]
    return result


# ──────────────────────────────────────────────────────────────────────────────
# ПРОГОН ПО СЕТИ
# ──────────────────────────────────────────────────────────────────────────────


def is_check_running(network: ScanNetwork) -> bool:
    if not network.glpi_check_started_at or network.glpi_check_finished_at:
        return False
    stale = timezone.now() - timedelta(hours=int(getattr(settings, "NETSCAN_STALE_RUN_HOURS", 12)))
    return network.glpi_check_started_at >= stale


def start_check(network: ScanNetwork) -> bool:
    """Начинает сверку сети с GLPI. False — уже идёт."""
    network.refresh_from_db()
    if is_check_running(network):
        return False
    network.glpi_check_started_at = timezone.now()
    network.glpi_check_finished_at = None
    network.glpi_check_total = devices_to_check(network).count()
    network.glpi_check_done = 0
    network.glpi_check_error = ""
    network.save(
        update_fields=[
            "glpi_check_started_at",
            "glpi_check_finished_at",
            "glpi_check_total",
            "glpi_check_done",
            "glpi_check_error",
        ]
    )
    return True


def _pending(network: ScanNetwork):
    return devices_to_check(network).filter(
        Q(glpi_checked_at__isnull=True) | Q(glpi_checked_at__lt=network.glpi_check_started_at)
    )


def _finish(network: ScanNetwork, error: str = "") -> None:
    ScanNetwork.objects.filter(pk=network.pk).update(glpi_check_finished_at=timezone.now(), glpi_check_error=error)


def check_batch(network: ScanNetwork) -> bool:
    """
    Сверяет очередную пачку устройств сети. Возвращает True, если остались непроверенные (нужна ещё задача).
    """
    from integrations.glpi.client import GLPIAPIError, GLPIClient

    if not network.glpi_check_started_at or network.glpi_check_finished_at:
        return False
    batch = list(_pending(network).order_by("ip_address")[: batch_size()])
    if not batch:
        _finish(network)
        return False

    cutoff = timezone.now() - timedelta(days=freshness_days())
    try:
        with GLPIClient() as client:
            for device in batch:
                try:
                    fields = probe_device(client, device, cutoff)
                except Exception as exc:
                    logger.exception(f"netscan-glpi: ошибка сверки {device.serial_number or device.mac_address}")
                    fields = {"glpi_status": DiscoveredDevice.GLPI_ERROR, "glpi_message": str(exc)[:2000]}
                fields["glpi_checked_at"] = timezone.now()
                DiscoveredDevice.objects.filter(pk=device.pk).update(**fields)
                ScanNetwork.objects.filter(pk=network.pk).update(glpi_check_done=F("glpi_check_done") + 1)
    except GLPIAPIError as exc:
        logger.error(f"netscan-glpi {network.cidr}: нет связи с GLPI: {exc}")
        _finish(network, f"Нет связи с GLPI: {exc}"[:2000])
        return False

    if _pending(network).exists():
        return True
    _finish(network)
    return False


def check_progress(network: ScanNetwork) -> Dict:
    network.refresh_from_db()
    counts = dict(
        devices_to_check(network).exclude(glpi_status="").values_list("glpi_status").order_by().annotate(n=Count("id"))
    )
    names = dict(DiscoveredDevice.GLPI_STATUS_CHOICES)
    return {
        "running": is_check_running(network),
        "started_at": network.glpi_check_started_at.isoformat() if network.glpi_check_started_at else None,
        "finished_at": network.glpi_check_finished_at.isoformat() if network.glpi_check_finished_at else None,
        "done": network.glpi_check_done,
        "total": network.glpi_check_total,
        "error": network.glpi_check_error,
        "waiting_for_worker": is_check_running(network) and network.glpi_check_done == 0,
        "counts": {k: {"title": names.get(k, k), "value": v} for k, v in counts.items()},
    }
