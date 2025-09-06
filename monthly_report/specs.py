from typing import Iterable, Optional, Set
from django.db import models
from .models_modelspec import PrinterModelSpec, PaperFormat
from .models import MonthlyReport

SPEC_CACHE: dict[str, PrinterModelSpec] = {}

def get_spec_for_model_name(model_name: Optional[str]) -> Optional[PrinterModelSpec]:
    name = (model_name or "").strip()
    if not name:
        return None
    hit = SPEC_CACHE.get(name.lower())
    if hit is not None:
        return hit
    spec = PrinterModelSpec.objects.filter(model_name__iexact=name).first()
    SPEC_CACHE[name.lower()] = spec
    return spec

def allowed_counter_fields(spec: Optional[PrinterModelSpec]) -> Set[str]:
    """
    Какие поля счётчиков можно редактировать пользователю для данной модели.
    Цветной аппарат -> только color; монохром -> только bw.
    В зависимости от формата разрешаем A4/A3.
    """
    fields: Set[str] = set()
    if spec is None or not spec.enforce:
        # ничего не ограничиваем
        return {
            "a4_bw_start","a4_bw_end","a4_color_start","a4_color_end",
            "a3_bw_start","a3_bw_end","a3_color_start","a3_color_end",
        }

    allow_a4 = spec.paper_format in (PaperFormat.A4_ONLY, PaperFormat.A4_A3)
    allow_a3 = spec.paper_format in (PaperFormat.A3_ONLY, PaperFormat.A4_A3)

    if spec.is_color:
        if allow_a4: fields |= {"a4_color_start","a4_color_end"}
        if allow_a3: fields |= {"a3_color_start","a3_color_end"}
    else:
        if allow_a4: fields |= {"a4_bw_start","a4_bw_end"}
        if allow_a3: fields |= {"a3_bw_start","a3_bw_end"}

    return fields

def _norm_model_name(name: Optional[str]) -> str:
    return " ".join((name or "").strip().split())

def ensure_model_specs(model_names: Iterable[str], *, enforce: bool = False,
                       default_format: str = PaperFormat.A4_A3, default_color: bool = False) -> int:
    """
    Убедиться, что для перечисленных моделей есть записи в справочнике.
    Возвращает количество созданных записей.
    По умолчанию создаются «свободные» правила: enforce=False (разрешено всё).
    """
    created = 0
    for raw in model_names:
        name = _norm_model_name(raw)
        if not name:
            continue
        # case-insensitive поиск: если есть — пропускаем
        exist = PrinterModelSpec.objects.filter(model_name__iexact=name).first()
        if exist:
            continue
        obj = PrinterModelSpec(
            model_name=name,
            is_color=default_color,
            paper_format=default_format,
            enforce=enforce,  # False => allowed_counter_fields вернёт все поля
        )
        obj.save()
        created += 1
    return created