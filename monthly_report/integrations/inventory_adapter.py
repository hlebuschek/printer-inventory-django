from __future__ import annotations
from typing import Dict, Iterable, Tuple, Optional
from django.db.models import Max
from django.utils import timezone

from inventory.models import Printer, InventoryTask, PageCounter  # ← под твои модели

def _norm_serials(serials: Iterable[str]) -> list[str]:
    return [s.strip() for s in set([(s or "").strip() for s in serials]) if s]

def fetch_printer_info_by_serial(serials: Iterable[str]) -> Dict[str, Tuple[Optional[str], Optional[timezone.datetime]]]:
    serials = _norm_serials(serials)
    if not serials:
        return {}
    printers = Printer.objects.filter(serial_number__in=serials).only("id","serial_number","ip_address")
    serial_to_ip: Dict[str, Optional[str]] = {}
    ids = []
    for p in printers:
        sn = (p.serial_number or "").strip()
        if sn and sn not in serial_to_ip:
            serial_to_ip[sn] = p.ip_address
        ids.append(p.id)

    last_ok = (InventoryTask.objects
               .filter(printer_id__in=ids, status="SUCCESS")
               .values("printer__serial_number")
               .annotate(last_ok=Max("task_timestamp")))
    serial_to_ok = { (r["printer__serial_number"] or "").strip(): r["last_ok"] for r in last_ok }

    out = {}
    for sn in serials:
        out[sn] = (serial_to_ip.get(sn), serial_to_ok.get(sn))
    return out

def fetch_counters_snaps(serials: Iterable[str], start_dt, end_dt):
    serials = _norm_serials(serials)
    if not serials:
        return {}, {}

    base = (PageCounter.objects
            .select_related("task","task__printer")
            .filter(task__printer__serial_number__in=serials, task__status="SUCCESS")
            .only("task__printer__serial_number","recorded_at","bw_a4","bw_a3","color_a4","color_a3"))

    def pick_latest(qs):
        seen, out = set(), {}
        for pc in qs:
            sn = (pc.task.printer.serial_number or "").strip()
            if sn and sn not in seen:
                out[sn] = pc
                seen.add(sn)
        return out

    start_qs = base.filter(recorded_at__lte=start_dt).order_by("task__printer__serial_number","-recorded_at")
    end_qs   = base.filter(recorded_at__lte=end_dt).order_by("task__printer__serial_number","-recorded_at")
    return pick_latest(start_qs), pick_latest(end_qs)
