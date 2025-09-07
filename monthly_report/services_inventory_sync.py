# monthly_report/services_inventory_sync.py
from __future__ import annotations
from typing import Optional, Iterable, Dict, Tuple
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import MonthlyReport, MonthControl
from .services import recompute_group
from .specs import allowed_counter_fields, get_spec_for_model_name
from .integrations.inventory_adapter import (
    fetch_printer_info_by_serial,   # -> dict(ip: str|None, last_ok: datetime|None)
    fetch_counters_snaps_for_range, # -> dict(start: {...}|None, end: {...}|None)
)

# Какие поля считаем "end"-полями
END_FIELDS = ("a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end")
START_FIELDS = ("a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start")

def _apply_spec_whitelist(model_name: str, payload: Dict[str, int]) -> Dict[str, int]:
    """Обрезаем счётчики по справочнику модели (цвет/A4-A3)."""
    spec = get_spec_for_model_name(model_name)
    allowed = allowed_counter_fields(spec) or set(START_FIELDS + END_FIELDS)
    return {k: (v if k in allowed else 0) for k, v in payload.items()}

def _should_update_auto(current: int, auto_flag: bool, new_val: Optional[int]) -> bool:
    """
    Обновляем, если:
      - значение ещё не задано (0), или
      - оно было заполнено автосинком ранее (auto_flag=True).
    Ручные правки не затираем.
    """
    if new_val is None:
        return False
    if (current or 0) == 0:
        return True
    return bool(auto_flag)

def _snap_to_dict(snap: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Нормализуем ключи из снапшота inventory к нашим полям *_start/*_end."""
    if not snap:
        return {}
    return {
        "a4_bw": int(snap.get("a4_bw", 0)),
        "a4_color": int(snap.get("a4_color", 0)),
        "a3_bw": int(snap.get("a3_bw", 0)),
        "a3_color": int(snap.get("a3_color", 0)),
    }

@transaction.atomic
def sync_month_from_inventory(month: datetime.date,
                              serials: Optional[Iterable[str]] = None,
                              only_empty: bool = False) -> Dict[str, int]:
    """
    Массовая синхронизация месяца (кнопка и фоновая задача).
    Если serials передан — ограничиваемся этими серийниками.
    only_empty=True — обновляем только пустые поля (старт/энд).
    """
    now = timezone.now()
    mc = MonthControl.objects.filter(month=month).first()
    if not (mc and mc.is_editable):
        return {"ok": False, "error": "Месяц закрыт"}

    base_qs = MonthlyReport.objects.select_for_update().filter(month=month)
    if serials:
        serials = { (s or "").strip() for s in serials if (s or "").strip() }
        base_qs = base_qs.filter(serial_number__in=serials)

    rows = list(base_qs.order_by("order_number", "id"))
    if not rows:
        return {"ok": True, "updated_rows": 0, "groups_recomputed": 0}

    # группируем по серийнику (и инв. № для корректного recompute_group)
    by_key: Dict[Tuple[str, str], list[MonthlyReport]] = {}
    for r in rows:
        key = ((r.serial_number or "").strip(), (r.inventory_number or "").strip())
        by_key.setdefault(key, []).append(r)

    updated = 0
    recomputed_groups = 0

    for (serial, _inv), group in by_key.items():
        if not serial:
            continue

        # 1) получаем инфо об устройстве и снапшоты для диапазона месяца
        info = fetch_printer_info_by_serial(serial) or {}
        snaps = fetch_counters_snaps_for_range(
            serial=serial,
            period_start=timezone.make_aware(datetime(month.year, month.month, 1), timezone.get_current_timezone()),
            period_end=now,
        ) or {}

        start_dict = _snap_to_dict(snaps.get("start"))
        end_dict   = _snap_to_dict(snaps.get("end"))

        # 2) применяем справочник модели
        # (в группе модели одинаковые; берём первую)
        model_name = group[0].equipment_model
        start_dict = _apply_spec_whitelist(model_name, start_dict)
        end_dict   = _apply_spec_whitelist(model_name, end_dict)

        touched_any = False

        for row in group:
            # ip/last_ok
            if info:
                row.device_ip = info.get("ip") or row.device_ip
                row.inventory_last_ok = info.get("last_ok") or row.inventory_last_ok

            # стартовые — обновляем только если пустые или only_empty=False и было auto (у старта авто-флагов нет — считаем "пустые")
            if start_dict:
                for name_src, name_dst in (
                    ("a4_bw", "a4_bw_start"),
                    ("a4_color", "a4_color_start"),
                    ("a3_bw", "a3_bw_start"),
                    ("a3_color", "a3_color_start"),
                ):
                    new_val = start_dict.get(name_src)
                    cur_val = getattr(row, name_dst)
                    if (only_empty and (cur_val or 0) > 0):
                        continue
                    if (cur_val or 0) == 0 and new_val is not None:
                        setattr(row, name_dst, int(new_val))
                        touched_any = True

            # конечные — обновляем по правилу: пустые ИЛИ ранее авто
            if end_dict:
                mapping = [
                    ("a4_bw", "a4_bw_end",   "a4_bw_end_auto"),
                    ("a4_color", "a4_color_end", "a4_color_end_auto"),
                    ("a3_bw", "a3_bw_end",   "a3_bw_end_auto"),
                    ("a3_color", "a3_color_end", "a3_color_end_auto"),
                ]
                for src, dst, flag in mapping:
                    new_val = end_dict.get(src)
                    cur_val = getattr(row, dst)
                    was_auto = getattr(row, flag)
                    if only_empty and (cur_val or 0) > 0 and not was_auto:
                        continue
                    if _should_update_auto(cur_val, was_auto, new_val):
                        setattr(row, dst, int(new_val))
                        setattr(row, flag, True)
                        touched_any = True

            if touched_any:
                row.inventory_autosync_at = now

        # сохраняем, если что-то поменялось
        if any(
            r.inventory_autosync_at == now or
            any(getattr(r, f"{f}_auto") for f in ("a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"))
            for r in group
        ):
            MonthlyReport.objects.bulk_update(
                group,
                [
                    "device_ip", "inventory_last_ok",
                    "a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start",
                    "a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end",
                    "a4_bw_end_auto", "a4_color_end_auto", "a3_bw_end_auto", "a3_color_end_auto",
                    "inventory_autosync_at",
                ],
            )
            # важный шаг — правильная «раскладка» total_prints (верх=A4, низ=A3)
            recompute_group(month, serial, group[0].inventory_number)
            updated += len(group)
            recomputed_groups += 1

    return {"ok": True, "updated_rows": updated, "groups_recomputed": recomputed_groups}

def sync_for_serial(serial: str, throttle_seconds: int = 60) -> Dict[str, int]:
    """
    Автосинк по событию из inventory: проходим по всем ОТКРЫТЫМ месяцам, где есть такой серийник,
    и обновляем значения (не затирая ручные).
    """
    serial = (serial or "").strip()
    if not serial:
        return {"ok": False, "error": "empty serial"}

    now = timezone.now()
    months_open = list(
        MonthControl.objects
        .filter(edit_until__gt=now)
        .values_list("month", flat=True)
    )
    total_rows = total_groups = 0
    for m in months_open:
        # Синхроним только строки с этим серийником
        res = sync_month_from_inventory(month=m, serials=[serial], only_empty=False)
        if res.get("ok"):
            total_rows += res.get("updated_rows", 0)
            total_groups += res.get("groups_recomputed", 0)

    return {"ok": True, "updated_rows": total_rows, "groups_recomputed": total_groups}
