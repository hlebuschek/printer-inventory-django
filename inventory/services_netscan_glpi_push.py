"""
Постановка найденного сканированием принтера на опрос в GLPI (плагин glpiinventory) по кнопке.

Что выяснено по коду плагина и проверено на GLPI 10 + glpiinventory 1.3.4:
  * SNMP-опрос (networkinventory) берёт учётку из самой карточки (Printer.snmpcredentials_id) и IP из её
    сетевого порта; учётки диапазона нужны только поиску (networkdiscovery);
  * цели задачи — JSON в PluginGlpiinventoryTaskjob.targets: IP-диапазоны или сами карточки {"Printer": "id"};
  * активную задачу (PluginGlpiinventoryTask) менять нельзя, её taskjob — можно;
  * найденное поиском устройство попадает в организацию (entity) диапазона.

Поэтому два пути:
  1. Карточка есть и у неё есть SNMP-учётка (её раньше опрашивали) — правим IP карточки на найденный
     сканом и, если ни карточка, ни диапазон с этим IP не входят в задачу опроса организации, добавляем
     карточку в неё. Поиск не нужен.
  2. Карточки нет (или у неё нет учётки / IP) — диапазон на один IP в организации, учётки
     GLPI_NETSCAN_SNMP_CREDENTIALS (по порядку = rank), диапазон в задачи поиска и опроса организации.

У каждой организации GLPI свои задачи поиска и опроса; ищем их у организации карточки,
а если там нет — у родительских.
"""

import ipaddress
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from .models import DiscoveredDevice
from .utils import mac_equal

logger = logging.getLogger(__name__)

DISCOVERY = "networkdiscovery"
INVENTORY = "networkinventory"
RANGE = "PluginGlpiinventoryIPRange"
TASK = "PluginGlpiinventoryTask"
TASKJOB = "PluginGlpiinventoryTaskjob"
RANGE_CRED = "PluginGlpiinventoryIPRange_SNMPCredential"


def snmp_credentials() -> List[int]:
    raw = getattr(settings, "GLPI_NETSCAN_SNMP_CREDENTIALS", "1,2")
    return [int(x) for x in str(raw).replace(" ", "").split(",") if x]


def _targets(job: Dict) -> List[Dict]:
    try:
        value = json.loads(job.get("targets") or "[]")
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def _dump_targets(targets: List[Dict]) -> str:
    # как json_encode в PHP (без пробелов): плагин ищет диапазон в задачах через LIKE '{"…IPRange":"id"}'
    return json.dumps(targets, separators=(",", ":"), ensure_ascii=False)


def _has_target(job: Dict, itemtype: str, item_id: int) -> bool:
    return any(str(t.get(itemtype)) == str(item_id) for t in _targets(job) if isinstance(t, dict))


def _in_range(ip: str, rng: Dict) -> bool:
    try:
        a = ipaddress.IPv4Address(ip)
        return ipaddress.IPv4Address(rng["ip_start"]) <= a <= ipaddress.IPv4Address(rng["ip_end"])
    except (ValueError, KeyError, TypeError):
        return False


@dataclass
class Step:
    text: str
    action: Optional[Callable[[Dict], None]] = None


@dataclass
class Plan:
    device: DiscoveredDevice
    entity_id: Optional[int] = None
    entity_name: str = ""
    mode: str = ""  # fix_ip / discovery
    card: Optional[Dict] = None
    jobs: Dict[str, Dict] = field(default_factory=dict)
    steps: List[Step] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def can_run(self) -> bool:
        return not self.problems and any(s.action for s in self.steps)


# ──────────────────────────────────────────────────────────────────────────────
# ЧТЕНИЕ GLPI
# ──────────────────────────────────────────────────────────────────────────────


def entities(client) -> Dict[int, Dict]:
    """{id: {"name": completename, "parent": id}}"""
    result = {}
    for e in client.list_items("Entity"):
        result[int(e["id"])] = {
            "name": e.get("completename") or e.get("name") or str(e["id"]),
            "parent": int(e.get("entities_id") or 0) if int(e["id"]) else None,
        }
    return result


def entity_jobs(client, entity_id: int, ents: Dict[int, Dict]) -> Dict[str, Dict]:
    """
    Задачи поиска и опроса организации: taskjob нужного метода в задаче этой организации,
    а если у неё своих нет — ближайшей родительской. Несколько подходящих у одной организации — ошибка.
    """
    tasks = {int(t["id"]): t for t in client.list_items(TASK)}
    jobs_by_entity: Dict[int, Dict[str, List[Dict]]] = {}
    for job in client.list_items(TASKJOB):
        task = tasks.get(int(job.get("plugin_glpiinventory_tasks_id") or 0))
        if not task or job.get("method") not in (DISCOVERY, INVENTORY):
            continue
        job["_task"] = task
        job["task_name"] = task.get("name") or f"задача {task['id']}"
        jobs_by_entity.setdefault(int(task.get("entities_id") or 0), {}).setdefault(job["method"], []).append(job)

    found: Dict[str, Dict] = {}
    current: Optional[int] = entity_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        for method, jobs in jobs_by_entity.get(current, {}).items():
            if method in found:
                continue
            if len(jobs) > 1:
                names = ", ".join(sorted(j["task_name"] for j in jobs))
                raise ValueError(
                    f"У организации «{ents.get(current, {}).get('name', current)}» несколько задач "
                    f"{method}: {names} — непонятно, в какую добавлять"
                )
            found[method] = jobs[0]
        current = ents.get(current, {}).get("parent")
    return found


def card_addresses(client, card_id: int) -> List[Dict]:
    """IP карточки с id объектов IPAddress: [{"ip_id", "ip", "mac"}]."""
    rows = []
    for port in client.get_sub_items("Printer", card_id, "NetworkPort"):
        for name in client.get_sub_items("NetworkPort", int(port["id"]), "NetworkName"):
            for addr in client.get_sub_items("NetworkName", int(name["id"]), "IPAddress"):
                if addr.get("name") and str(addr.get("version")) == "4":
                    rows.append({"ip_id": int(addr["id"]), "ip": addr["name"], "mac": port.get("mac") or ""})
    return rows


def suggest_entity(device: DiscoveredDevice) -> Optional[int]:
    """Организация GLPI для устройства без карточки: самая частая среди карточек соседей по сети."""
    if device.glpi_entity_id is not None:
        return device.glpi_entity_id
    ids = (
        DiscoveredDevice.objects.filter(network_id=device.network_id, glpi_entity_id__isnull=False)
        .exclude(pk=device.pk)
        .values_list("glpi_entity_id", flat=True)
    )
    common = Counter(ids).most_common(1)
    return common[0][0] if common else None


# ──────────────────────────────────────────────────────────────────────────────
# ПЛАН
# ──────────────────────────────────────────────────────────────────────────────


def build_plan(client, device: DiscoveredDevice, entity_id: Optional[int] = None) -> Plan:
    plan = Plan(device=device)
    ip = device.ip_address
    if not ip:
        plan.problems.append("У записи нет IP-адреса")
        return plan
    if device.status == DiscoveredDevice.DUPLICATE_SERIAL or device.glpi_status == DiscoveredDevice.GLPI_MULTIPLE:
        plan.problems.append("Одинаковый серийник / несколько карточек в GLPI — сначала разберитесь вручную")
        return plan

    if device.glpi_printer_id:
        plan.card = client.get_item("Printer", device.glpi_printer_id)
        if plan.card is None:
            plan.notes.append(f"Карточки {device.glpi_printer_id} в GLPI больше нет — ставим на поиск")
    if plan.card:
        entity_id = int(plan.card.get("entities_id") or 0)
        plan.notes.append(f"Организация берётся из карточки GLPI {plan.card['id']} «{plan.card.get('name', '')}»")

    ents = entities(client)
    if entity_id is None:
        plan.problems.append("Выберите организацию GLPI")
        return plan
    if entity_id not in ents:
        plan.problems.append(f"Организации {entity_id} в GLPI нет")
        return plan
    plan.entity_id, plan.entity_name = entity_id, ents[entity_id]["name"]
    try:
        plan.jobs = entity_jobs(client, entity_id, ents)
    except ValueError as exc:
        plan.problems.append(str(exc))
        return plan

    has_credential = bool(plan.card and int(plan.card.get("snmpcredentials_id") or 0))
    addresses = card_addresses(client, int(plan.card["id"])) if has_credential else []
    if has_credential and addresses:
        _plan_fix_ip(client, plan, addresses)
    else:
        if plan.card and not has_credential:
            plan.notes.append("У карточки нет SNMP-учётки — её проставит поиск")
        elif plan.card:
            plan.notes.append("У карточки нет IP — его проставит поиск")
        _plan_discovery(client, plan)
    return plan


def _plan_fix_ip(client, plan: Plan, addresses: List[Dict]) -> None:
    plan.mode = "fix_ip"
    device, card_id = plan.device, int(plan.card["id"])
    ip = device.ip_address
    if ip in [a["ip"] for a in addresses]:
        plan.notes.append(f"IP в карточке уже {ip}")
    else:
        target = next((a for a in addresses if device.mac_address and mac_equal(a["mac"], device.mac_address)), None)
        target = target or addresses[0]

        def fix_ip(ctx, ip_id=target["ip_id"]):
            client.update_item("IPAddress", ip_id, {"name": ip})

        plan.steps.append(Step(f"Исправить IP карточки {card_id}: {target['ip']} → {ip}", fix_ip))

    job = plan.jobs.get(INVENTORY)
    if not job:
        plan.problems.append(f"У организации «{plan.entity_name}» нет задачи опроса (networkinventory)")
        return
    task_name = job["task_name"]
    if _has_target(job, "Printer", card_id):
        plan.notes.append(f"Карточка уже в задаче опроса «{task_name}»")
        return
    ranges = {int(r["id"]): r for r in client.list_items(RANGE)}
    covering = [
        ranges[int(t[RANGE])]
        for t in _targets(job)
        if isinstance(t, dict)
        and str(t.get(RANGE, "")).isdigit()
        and int(t[RANGE]) in ranges
        and _in_range(ip, ranges[int(t[RANGE])])
    ]
    if covering:
        plan.notes.append(f"IP {ip} входит в диапазон «{covering[0].get('name')}» задачи опроса «{task_name}»")
        return
    plan.steps.append(
        Step(
            f"Добавить карточку {card_id} в задачу опроса «{task_name}»",
            _append_target(client, job, "Printer", card_id),
        )
    )


def _plan_discovery(client, plan: Plan) -> None:
    plan.mode = "discovery"
    device, ip, entity_id = plan.device, plan.device.ip_address, plan.entity_id
    creds = snmp_credentials()
    existing = next(
        (
            r
            for r in client.list_items(RANGE)
            if r.get("ip_start") == ip and r.get("ip_end") == ip and int(r.get("entities_id") or 0) == entity_id
        ),
        None,
    )
    ctx_range = {"id": int(existing["id"]) if existing else None}

    if existing:
        plan.notes.append(f"Диапазон {ip} уже есть: «{existing.get('name')}» (ID {existing['id']})")
        linked = {
            int(link["snmpcredentials_id"])
            for link in client.list_items(RANGE_CRED)
            if int(link.get("plugin_glpiinventory_ipranges_id") or 0) == int(existing["id"])
        }
        missing = [c for c in creds if c not in linked]
    else:
        name = f"netscan {ip}" + (f" {device.serial_number}" if device.serial_number else "")

        def create_range(ctx):
            ctx["range_id"] = client.add_item(
                RANGE, {"name": name[:255], "entities_id": entity_id, "ip_start": ip, "ip_end": ip}
            )

        plan.steps.append(Step(f"Создать диапазон «{name}» ({ip}) в организации «{plan.entity_name}»", create_range))
        missing = creds

    if missing:

        def link_creds(ctx, missing=tuple(missing)):
            range_id = ctx.get("range_id") or ctx_range["id"]
            for cred in missing:
                client.add_item(
                    RANGE_CRED,
                    {
                        "plugin_glpiinventory_ipranges_id": range_id,
                        "snmpcredentials_id": cred,
                        "rank": creds.index(cred) + 1,
                    },
                )

        plan.steps.append(Step(f"Привязать SNMP-учётки {', '.join(map(str, missing))} к диапазону", link_creds))

    for method, title in ((DISCOVERY, "поиска"), (INVENTORY, "опроса")):
        job = plan.jobs.get(method)
        if not job:
            plan.problems.append(f"У организации «{plan.entity_name}» нет задачи {title} ({method})")
            continue
        task_name = job["task_name"]
        if ctx_range["id"] and _has_target(job, RANGE, ctx_range["id"]):
            plan.notes.append(f"Диапазон уже в задаче {title} «{task_name}»")
            continue
        plan.steps.append(
            Step(
                f"Добавить диапазон в задачу {title} «{task_name}»", _append_target(client, job, RANGE, ctx_range["id"])
            )
        )


def _append_target(client, job: Dict, itemtype: str, item_id: Optional[int]):
    def action(ctx):
        target_id = item_id or ctx["range_id"]
        fresh = client.get_item(TASKJOB, int(job["id"])) or job  # перечитать: задачу могли поменять в GLPI
        if _has_target(fresh, itemtype, target_id):
            return
        targets = _targets(fresh) + [{itemtype: str(target_id)}]
        client.update_item(TASKJOB, int(job["id"]), {"targets": _dump_targets(targets)})

    return action


# ──────────────────────────────────────────────────────────────────────────────
# ВЫПОЛНЕНИЕ
# ──────────────────────────────────────────────────────────────────────────────


def execute(plan: Plan, user=None) -> List[str]:
    """Выполняет шаги плана по порядку. Возвращает выполненные; при ошибке сохраняет, что успело пройти."""
    done: List[str] = []
    ctx: Dict = {}
    error = ""
    try:
        for step in plan.steps:
            if step.action:
                step.action(ctx)
                done.append(step.text)
    except Exception as exc:
        logger.exception(f"netscan→GLPI: ошибка на шаге для {plan.device.ip_address}")
        error = f"Ошибка: {exc}"
    message = "; ".join(done) or "ничего не сделано"
    if error:
        message += f". {error}"
    DiscoveredDevice.objects.filter(pk=plan.device.pk).update(
        glpi_push_message=message[:2000], glpi_push_at=timezone.now(), glpi_push_by=user
    )
    if error:
        raise RuntimeError(message)
    return done
