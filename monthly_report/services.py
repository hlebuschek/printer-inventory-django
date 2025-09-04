from typing import Optional, Tuple, Iterable
from .models import MonthlyReport

def _nz(x) -> int:
    try:
        return int(x or 0)
    except Exception:
        return 0

def _a4(obj: MonthlyReport) -> int:
    return max(0, _nz(obj.a4_bw_end) - _nz(obj.a4_bw_start)) + \
           max(0, _nz(obj.a4_color_end) - _nz(obj.a4_color_start))

def _a3(obj: MonthlyReport) -> int:
    return max(0, _nz(obj.a3_bw_end) - _nz(obj.a3_bw_start)) + \
           max(0, _nz(obj.a3_color_end) - _nz(obj.a3_color_start))

def recompute_group(month, serial: Optional[str], inv: Optional[str]) -> None:
    """
    Пересчитать total_prints для всех записей в группе (month, serial, inv)
    по правилу: первая по id = только A4, остальные = только A3.
    Если группа из 1 записи — A4 + A3.
    Пустые serial & inv не группируем.
    """
    sn = (serial or "").strip()
    iv = (inv or "").strip()
    if not sn and not iv:
        return

    qs = MonthlyReport.objects.filter(month=month, serial_number=sn, inventory_number=iv).order_by('id')
    objs = list(qs)
    if not objs:
        return

    if len(objs) == 1:
        total = _a4(objs[0]) + _a3(objs[0])
        if objs[0].total_prints != total:
            objs[0].total_prints = total
            objs[0].save(update_fields=['total_prints'])
        return

    updates = []
    for i, obj in enumerate(objs):
        total = _a4(obj) if i == 0 else _a3(obj)
        if obj.total_prints != total:
            obj.total_prints = total
            updates.append(obj)
    if updates:
        MonthlyReport.objects.bulk_update(updates, ['total_prints'])

def recompute_month(month) -> None:
    """
    Опционально: массовый пересчёт всего месяца одним вызовом (удобно после импорта).
    """
    keys = set()
    for row in MonthlyReport.objects.filter(month=month).values('serial_number', 'inventory_number'):
        sn = (row['serial_number'] or '').strip()
        iv = (row['inventory_number'] or '').strip()
        if sn or iv:
            keys.add((sn, iv))
    for sn, iv in keys:
        recompute_group(month, sn, iv)
