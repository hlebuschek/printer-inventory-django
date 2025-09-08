from __future__ import annotations
from typing import Iterable, Tuple, Dict, Any, Optional
from django.apps import apps
from django.db.models import Q

def _first_attr(obj, names: list[str], default: Any = None) -> Any:
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            return v() if callable(v) else v
    return default

def _get_printer_model():
    """Пытаемся найти модель устройства в разных приложениях/названиях."""
    candidates = [
        ("inventory", "Device"),
        ("inventory", "Printer"),
        ("printers",  "Printer"),
        ("printers",  "Device"),
    ]
    for app_label, model_name in candidates:
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            continue
    return None

def get_inventory_suggestions(pairs: Iterable[Tuple[str | None, str | None]]
                              ) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    На вход — список (serial_number, inventory_number).
    Возвращает dict с ключом (sn, inv) и данными:
      {
        'ip': str|None, 'polled_at': datetime|None,
        'a4_bw': int, 'a4_color': int, 'a3_bw': int, 'a3_color': int
      }
    """
    Printer = _get_printer_model()
    if not Printer:
        return {}

    norm_pairs = []
    sns, invs = set(), set()
    for sn, inv in pairs:
        sn = (sn or "").strip()
        inv = (inv or "").strip()
        norm_pairs.append((sn, inv))
        if sn: sns.add(sn)
        if inv: invs.add(inv)

    q = Q()
    # серийник
    if sns:
        if hasattr(Printer, "serial_number"):
            q |= Q(serial_number__in=list(sns))
        elif hasattr(Printer, "serial"):
            q |= Q(serial__in=list(sns))
    # инвентарный
    if invs:
        if hasattr(Printer, "inventory_number"):
            q |= Q(inventory_number__in=list(invs))
        elif hasattr(Printer, "inventory"):
            q |= Q(inventory__in=list(invs))

    if not q:
        return {}

    devices = Printer.objects.filter(q)

    result: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for d in devices:
        sn  = (_first_attr(d, ["serial_number", "serial", "sn"], "") or "").strip()
        inv = (_first_attr(d, ["inventory_number", "inventory", "inv"], "") or "").strip()

        key = (sn, inv)
        result[key] = {
            "ip": _first_attr(d, ["ip", "ip_address", "host", "hostname"], None),
            "polled_at": _first_attr(d, ["last_polled_at", "polled_at", "updated_at", "last_seen"], None),
            # возможные имена полей счётчиков
            "a4_bw":     int(_first_attr(d, ["a4_bw", "a4_bw_total", "counter_a4_bw", "bw_a4", "a4_mono"], 0) or 0),
            "a4_color":  int(_first_attr(d, ["a4_color", "a4_cl", "counter_a4_color", "color_a4"], 0) or 0),
            "a3_bw":     int(_first_attr(d, ["a3_bw", "a3_bw_total", "counter_a3_bw", "bw_a3"], 0) or 0),
            "a3_color":  int(_first_attr(d, ["a3_color", "a3_cl", "counter_a3_color", "color_a3"], 0) or 0),
        }
    return result
