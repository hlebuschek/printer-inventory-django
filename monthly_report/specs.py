from typing import Iterable, Optional, Set
import logging
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models_modelspec import PrinterModelSpec, PaperFormat
from .models import MonthlyReport

logger = logging.getLogger(__name__)

SPEC_CACHE: dict[str, PrinterModelSpec] = {}


def clear_spec_cache():
    """
    Очистить кэш спецификаций моделей принтеров.
    Используется при изменении PrinterModelSpec в админке.
    """
    global SPEC_CACHE
    cache_size = len(SPEC_CACHE)
    SPEC_CACHE = {}
    if cache_size > 0:
        logger.info(f"Очищен кэш PrinterModelSpec ({cache_size} записей)")


def get_spec_for_model_name(model_name: Optional[str]) -> Optional[PrinterModelSpec]:
    name = _norm_model_name(model_name)
    if not name:
        return None
    hit = SPEC_CACHE.get(name.lower())
    if hit is not None:
        return hit
    spec = PrinterModelSpec.objects.filter(model_name__iexact=name).first()
    SPEC_CACHE[name.lower()] = spec
    return spec


# Автоматическая очистка кэша при изменении/удалении спецификаций
@receiver(post_save, sender=PrinterModelSpec)
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    """Очистить кэш при сохранении PrinterModelSpec"""
    action = "создана" if created else "обновлена"
    logger.info(
        f"PrinterModelSpec '{instance.model_name}' {action} "
        f"(is_color={instance.is_color}, format={instance.paper_format}, "
        f"enforce={instance.enforce}) - очистка кэша"
    )
    clear_spec_cache()


@receiver(post_delete, sender=PrinterModelSpec)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """Очистить кэш при удалении PrinterModelSpec"""
    logger.info(f"PrinterModelSpec '{instance.model_name}' удалена - очистка кэша")
    clear_spec_cache()


def allowed_counter_fields(spec: Optional[PrinterModelSpec]) -> Set[str]:
    """
    Какие поля счётчиков можно редактировать пользователю для данной модели.

    БИЗНЕС-ПРАВИЛО:
    - Монохромный аппарат -> ТОЛЬКО BW поля (все отпечатки считаются ч/б)
    - Цветной аппарат -> ТОЛЬКО COLOR поля (все отпечатки считаются цветными)

    В зависимости от формата разрешаем A4/A3.
    """
    fields: Set[str] = set()

    if spec is None or not spec.enforce:
        # Если правил нет или они отключены - разрешаем все поля
        return {
            "a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end",
            "a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end",
        }

    allow_a4 = spec.paper_format in (PaperFormat.A4_ONLY, PaperFormat.A4_A3)
    allow_a3 = spec.paper_format in (PaperFormat.A3_ONLY, PaperFormat.A4_A3)

    if spec.is_color:
        # Цветной принтер - ВСЕ отпечатки считаются цветными
        if allow_a4:
            fields |= {"a4_color_start", "a4_color_end"}
        if allow_a3:
            fields |= {"a3_color_start", "a3_color_end"}
    else:
        # Монохромный принтер - ВСЕ отпечатки считаются ч/б
        if allow_a4:
            fields |= {"a4_bw_start", "a4_bw_end"}
        if allow_a3:
            fields |= {"a3_bw_start", "a3_bw_end"}

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