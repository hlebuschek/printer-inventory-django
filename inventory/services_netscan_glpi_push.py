"""
Постановка найденного сканированием принтера на опрос в GLPI (плагин glpiinventory) по кнопке.

Что выяснено по коду плагина и проверено на GLPI 10 + glpiinventory 1.3.4:
  * SNMP-опрос (networkinventory) берёт учётку из самой карточки (Printer.snmpcredentials_id) и IP из её
    сетевого порта; учётки диапазона нужны только поиску (networkdiscovery);
  * цели задачи — JSON в PluginGlpiinventoryTaskjob.targets: IP-диапазоны или сами карточки {"Printer": "id"};
  * активную задачу (PluginGlpiinventoryTask) менять нельзя, её taskjob — можно;
  * найденное поиском устройство попадает в организацию (entity) диапазона.

Что делаем:
  * диапазон на один IP в организации, учётки GLPI_NETSCAN_SNMP_CREDENTIALS (по порядку = rank),
    диапазон — во ВСЕ задачи поиска и опроса организации (поиск проставит карточке IP и учётку,
    опрос возьмёт её по диапазону);
  * если карточка есть, её раньше опрашивали (есть SNMP-учётка) и IP в ней другой — дополнительно
    сразу правим IP карточки на найденный сканом, не дожидаясь поиска.

Задачи организации — taskjob'ы нужного метода в задачах этой организации, а если у неё таких нет —
ближайшей родительской. Если подходящих несколько — диапазон добавляется во все.
"""

import ipaddress
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from datetime import timedelta

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from .models import DiscoveredDevice, ScanNetwork
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


@dataclass
class Step:
    text: str
    action: Optional[Callable[[Dict], None]] = None


@dataclass
class Plan:
    device: DiscoveredDevice
    entity_id: Optional[int] = None
    entity_name: str = ""
    card: Optional[Dict] = None
    card_addresses: List[Dict] = field(default_factory=list)
    jobs: Dict[str, List[Dict]] = field(default_factory=dict)  # метод -> все taskjob'ы организации
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


def entity_jobs(client, entity_id: int, ents: Dict[int, Dict]) -> Dict[str, List[Dict]]:
    """
    Задачи поиска и опроса организации: все taskjob'ы нужного метода в задачах этой организации,
    а если у неё своих нет — ближайшей родительской.
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

    found: Dict[str, List[Dict]] = {}
    current: Optional[int] = entity_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        for method, jobs in jobs_by_entity.get(current, {}).items():
            found.setdefault(method, sorted(jobs, key=lambda j: (j["task_name"], int(j["id"]))))
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
    plan.jobs = entity_jobs(client, entity_id, ents)

    has_credential = bool(plan.card and int(plan.card.get("snmpcredentials_id") or 0))
    plan.card_addresses = card_addresses(client, int(plan.card["id"])) if plan.card else []
    addresses = plan.card_addresses
    if has_credential and addresses:
        _plan_fix_ip(client, plan, addresses)
    elif plan.card and not has_credential:
        plan.notes.append("У карточки нет SNMP-учётки — её проставит поиск")
    elif plan.card:
        plan.notes.append("У карточки нет IP — его проставит поиск")
    _plan_range(client, plan)
    return plan


def _plan_fix_ip(client, plan: Plan, addresses: List[Dict]) -> None:
    device, card_id = plan.device, int(plan.card["id"])
    ip = device.ip_address
    if ip in [a["ip"] for a in addresses]:
        plan.notes.append(f"IP в карточке уже {ip}")
        return
    target = next((a for a in addresses if device.mac_address and mac_equal(a["mac"], device.mac_address)), None)
    target = target or addresses[0]

    def fix_ip(ctx, ip_id=target["ip_id"]):
        client.update_item("IPAddress", ip_id, {"name": ip})

    plan.steps.append(Step(f"Исправить IP карточки {card_id}: {target['ip']} → {ip}", fix_ip))


def range_name(ip: str, serial: str = "") -> str:
    return (f"netscan {ip}" + (f" {serial}" if serial else ""))[:255]


def _single(r: Dict, entity_id: int) -> bool:
    return (
        bool(r.get("ip_start")) and r.get("ip_start") == r.get("ip_end") and int(r.get("entities_id") or 0) == entity_id
    )


def _word_in(word: str, text: str) -> bool:
    """word встречается в text отдельным словом (разделители — всё, кроме букв и цифр): ABC1 не находит ABC12."""
    if not word or not text:
        return False
    return re.search(rf"(?<![0-9a-z]){re.escape(word.lower())}(?![0-9a-z])", text.lower()) is not None


def _host(name: str) -> str:
    """Имя хоста без домена: KM546918.ie.corp → km546918. IP-адрес хостом не считаем."""
    name = (name or "").strip().lower()
    try:
        ipaddress.IPv4Address(name)
        return ""
    except ValueError:
        return name.split(".")[0]


def old_ips(plan: Plan) -> List[str]:
    """Прежние IP устройства: из карточки GLPI, последней сверки и нашего опроса (кроме нового)."""
    device = plan.device
    ips = [a["ip"] for a in plan.card_addresses] + (device.glpi_ip or "").split(",")
    if device.printer_id and device.printer:
        ips.append(device.printer.ip_address or "")
    result = []
    for ip in ips:
        ip = (ip or "").strip()
        if ip and ip != device.ip_address and ip not in result:
            result.append(ip)
    return result


def _ip_taken_by_other(device: DiscoveredDevice, ip: str) -> bool:
    """На адресе по последнему скану отвечает другое устройство — старый диапазон этого IP уже не наш."""
    return (
        DiscoveredDevice.objects.filter(ip_address=ip)
        .exclude(pk=device.pk)
        .exclude(identity=device.identity)
        .exclude(status=DiscoveredDevice.MISSING)
        .exists()
    )


def find_old_range(plan: Plan, ranges: List[Dict]) -> Optional[Dict]:
    """
    Прежний диапазон на один адрес этого устройства в той же организации (имена диапазонов заданы как попало):
      1. серийник отдельным словом в имени («ECOSYS_VCF7Y87967», «Kyocera M4132idn_VKJ0408688»);
      2. имя без домена = имя карточки GLPI или SNMP-имя («RRZ-P-XRX13», «KM546918.ie.corp»);
      3. диапазон ровно на прежний IP устройства (имя любое) — если этот адрес не занят другим устройством.
    Возвращает диапазон с ключом "_why" — как найден.
    """
    device, entity_id = plan.device, plan.entity_id
    own = [r for r in ranges if _single(r, entity_id) and r.get("ip_start") != device.ip_address]
    serial = (device.serial_number or "").strip()
    if len(serial) >= 4:
        found = [r for r in own if _word_in(serial, str(r.get("name") or ""))]
        if len(found) == 1:
            return {**found[0], "_why": f"по серийнику {serial} в имени"}
    # имя карточки / SNMP-имя бывает просто моделью — по нему сопоставляем, только если это имя хоста
    model = (device.model or "").strip().lower()
    hosts = {_host(n) for n in ((plan.card or {}).get("name"), device.snmp_name) if n}
    hosts = {h for h in hosts if len(h) >= 4 and not re.search(r"\s", h) and h != model}
    if hosts:
        found = [r for r in own if _host(str(r.get("name") or "")) in hosts]
        if len(found) == 1:
            return {**found[0], "_why": "по имени устройства"}
    for ip in old_ips(plan):
        for r in own:
            if r.get("ip_start") == ip and not _ip_taken_by_other(device, ip):
                return {**r, "_why": f"по прежнему IP {ip}"}
    return None


def _moved_name(r: Dict, ip: str, serial: str) -> str:
    """Имя после переноса: наше «netscan …» и имя-IP меняем, остальные (модель, хост, серийник) оставляем."""
    name = str(r.get("name") or "").strip()
    if name == r.get("ip_start") or not name:
        return ip
    if name.startswith("netscan "):
        return range_name(ip, serial)
    return name


def _plan_range(client, plan: Plan) -> None:
    device, ip, entity_id = plan.device, plan.device.ip_address, plan.entity_id
    creds = snmp_credentials()
    ranges = client.list_items(RANGE)
    existing = next(
        (
            r
            for r in ranges
            if r.get("ip_start") == ip and r.get("ip_end") == ip and int(r.get("entities_id") or 0) == entity_id
        ),
        None,
    )
    name = range_name(ip, device.serial_number)
    moved = None if existing else find_old_range(plan, ranges)
    if moved:
        # принтер сменил адрес: переносим его прежний диапазон на новый IP, а не заводим ещё один
        new_name = _moved_name(moved, ip, device.serial_number)

        def move_range(ctx, range_id=int(moved["id"]), new_name=new_name):
            client.update_item(RANGE, range_id, {"name": new_name, "ip_start": ip, "ip_end": ip})

        rename = f", имя → «{new_name}»" if new_name != moved.get("name") else ""
        plan.steps.append(
            Step(
                f"Перенести диапазон «{moved.get('name')}» (ID {moved['id']}, найден {moved['_why']}): "
                f"{moved.get('ip_start')} → {ip}{rename}",
                move_range,
            )
        )
        existing = moved
    ctx_range = {"id": int(existing["id"]) if existing else None}

    if existing:
        if not moved:
            plan.notes.append(f"Диапазон {ip} уже есть: «{existing.get('name')}» (ID {existing['id']})")
            stale = find_old_range(plan, ranges)
            if stale:
                plan.notes.append(
                    f"Остался прежний диапазон «{stale.get('name')}» (ID {stale['id']}, {stale.get('ip_start')}, "
                    f"найден {stale['_why']}) — удалите его в GLPI, чтобы не опрашивать старый адрес"
                )
        linked = {
            int(link["snmpcredentials_id"])
            for link in client.list_items(RANGE_CRED)
            if int(link.get("plugin_glpiinventory_ipranges_id") or 0) == int(existing["id"])
        }
        missing = [c for c in creds if c not in linked]
    else:

        def create_range(ctx):
            ctx["range_id"] = client.add_item(
                RANGE, {"name": name, "entities_id": entity_id, "ip_start": ip, "ip_end": ip}
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
        jobs = plan.jobs.get(method) or []
        if not jobs:
            plan.problems.append(f"У организации «{plan.entity_name}» нет задачи {title} ({method})")
        for job in jobs:
            task_name = job["task_name"]
            if ctx_range["id"] and _has_target(job, RANGE, ctx_range["id"]):
                plan.notes.append(f"Диапазон уже в задаче {title} «{task_name}»")
                continue
            plan.steps.append(
                Step(
                    f"Добавить диапазон в задачу {title} «{task_name}»",
                    _append_target(client, job, RANGE, ctx_range["id"]),
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


# ──────────────────────────────────────────────────────────────────────────────
# ВСЕ УСТРОЙСТВА СЕТИ СРАЗУ (по кнопке, задачами в очереди netscan, пачками)
# ──────────────────────────────────────────────────────────────────────────────

PUSHABLE = (DiscoveredDevice.GLPI_OTHER_IP, DiscoveredDevice.GLPI_STALE, DiscoveredDevice.GLPI_NOT_FOUND)


def push_batch_size() -> int:
    return max(1, int(getattr(settings, "NETSCAN_GLPI_PUSH_BATCH", 10)))


def push_candidates(network: ScanNetwork):
    """Найденные в сети устройства, которые GLPI не опрашивает (по последней сверке)."""
    return (
        network.devices.filter(glpi_status__in=PUSHABLE, is_ignored=False)
        .exclude(ip_address__isnull=True)
        .exclude(status=DiscoveredDevice.DUPLICATE_SERIAL)
    )


def is_push_running(network: ScanNetwork) -> bool:
    if not network.glpi_push_started_at or network.glpi_push_finished_at:
        return False
    stale = timezone.now() - timedelta(hours=int(getattr(settings, "NETSCAN_STALE_RUN_HOURS", 12)))
    return network.glpi_push_started_at >= stale


def start_push(network: ScanNetwork) -> bool:
    """Начинает постановку всех подходящих устройств сети. False — уже идёт."""
    network.refresh_from_db()
    if is_push_running(network):
        return False
    now = timezone.now()
    total = push_candidates(network).count()
    ScanNetwork.objects.filter(pk=network.pk).update(
        glpi_push_started_at=now,
        glpi_push_finished_at=None if total else now,
        glpi_push_total=total,
        glpi_push_done=0,
        glpi_push_error="",
    )
    network.refresh_from_db()
    return True


def _push_pending(network: ScanNetwork):
    return push_candidates(network).filter(
        Q(glpi_push_tried_at__isnull=True) | Q(glpi_push_tried_at__lt=network.glpi_push_started_at)
    )


def _finish_push(network: ScanNetwork, error: str = "") -> None:
    ScanNetwork.objects.filter(pk=network.pk).update(glpi_push_finished_at=timezone.now(), glpi_push_error=error)


def push_device(client, device: DiscoveredDevice, user=None) -> str:
    """Ставит одно устройство на опрос без выбора на странице. Возвращает причину, если не поставлено, иначе ''."""
    plan = build_plan(client, device, suggest_entity(device))
    if plan.problems:
        return "; ".join(plan.problems)
    if plan.can_run:
        try:
            execute(plan, user=user)
        except RuntimeError as exc:
            return str(exc)
    return ""


def push_batch(network: ScanNetwork, user=None) -> bool:
    """Ставит на опрос очередную пачку устройств сети. True — остались необработанные (нужна ещё задача)."""
    from integrations.glpi.client import GLPIAPIError, GLPIClient

    network.refresh_from_db()
    if not is_push_running(network):
        return False
    batch = list(_push_pending(network).select_related("printer").order_by("ip_address")[: push_batch_size()])
    if not batch:
        _finish_push(network)
        return False
    try:
        with GLPIClient() as client:
            for device in batch:
                try:
                    problem = push_device(client, device, user)
                except GLPIAPIError:
                    raise
                except Exception as exc:
                    logger.exception(f"netscan→GLPI: ошибка постановки {device.ip_address}")
                    problem = f"Ошибка: {exc}"
                DiscoveredDevice.objects.filter(pk=device.pk).update(
                    glpi_push_tried_at=timezone.now(), glpi_push_problem=problem[:2000]
                )
                ScanNetwork.objects.filter(pk=network.pk).update(glpi_push_done=F("glpi_push_done") + 1)
    except GLPIAPIError as exc:
        logger.error(f"netscan→GLPI {network.cidr}: нет связи с GLPI: {exc}")
        _finish_push(network, f"Нет связи с GLPI: {exc}"[:2000])
        return False
    if _push_pending(network).exists():
        return True
    _finish_push(network)
    return False


def push_progress(network: ScanNetwork) -> Dict:
    network.refresh_from_db()
    running = is_push_running(network)
    tried = network.devices.none()
    if network.glpi_push_started_at:
        tried = network.devices.filter(glpi_push_tried_at__gte=network.glpi_push_started_at)
    problems = list(
        tried.exclude(glpi_push_problem="").order_by("ip_address").values("ip_address", "glpi_push_problem")
    )
    return {
        "running": running,
        "started_at": network.glpi_push_started_at.isoformat() if network.glpi_push_started_at else None,
        "finished_at": network.glpi_push_finished_at.isoformat() if network.glpi_push_finished_at else None,
        "done": network.glpi_push_done,
        "total": network.glpi_push_total,
        "ok": tried.filter(glpi_push_problem="").count(),
        "skipped": len(problems),
        "problems": [{"ip": p["ip_address"], "text": p["glpi_push_problem"]} for p in problems[:200]],
        "error": network.glpi_push_error,
        "waiting_for_worker": running and network.glpi_push_done == 0,
    }
