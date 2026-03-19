"""
Сервисы для работы с GLPI интеграцией.
Содержат бизнес-логику проверки и синхронизации.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from contracts.models import ContractDevice
from integrations.models import GLPICrossCheck, GLPISync

from .client import GLPIAPIError, GLPIClient

logger = logging.getLogger(__name__)


def check_device_in_glpi(device: ContractDevice, user: Optional[User] = None, force_check: bool = False) -> GLPISync:
    """
    Проверяет наличие устройства в GLPI по серийному номеру.

    Args:
        device: Устройство для проверки
        user: Пользователь, инициировавший проверку
        force_check: Принудительная проверка даже если недавно проверялось

    Returns:
        GLPISync объект с результатами проверки
    """
    serial_number = device.serial_number

    if not serial_number:
        # Создаём запись об ошибке
        sync = GLPISync.objects.create(
            contract_device=device,
            status="ERROR",
            searched_serial="",
            error_message="Серийный номер отсутствует",
            checked_by=user,
        )
        logger.warning(f"Попытка проверки устройства без серийного номера: {device} (ID: {device.id})")
        return sync

    # Проверяем, не проверяли ли недавно (в течение часа)
    if not force_check:
        recent_sync = GLPISync.objects.filter(
            contract_device=device, checked_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).first()

        if recent_sync:
            logger.info(f"Используем кэшированный результат для {device.serial_number}")
            # Обновляем время последней проверки и пользователя
            recent_sync.checked_at = timezone.now()
            if user:
                recent_sync.checked_by = user
            recent_sync.save(update_fields=["checked_at", "checked_by"])
            return recent_sync

    # Выполняем проверку через GLPI API
    try:
        with GLPIClient() as client:
            status, items, error = client.search_printer_by_serial(serial_number)

            # Извлекаем ID найденных карточек
            # Формат зависит от способа поиска:
            # - /search/Printer возвращает {'2': id, '1': name, ...}
            # - /Printer/{id} возвращает {'id': id, 'name': name, ...}
            glpi_ids = []

            for item in items:
                # Пробуем оба формата
                item_id = item.get("2") or item.get("id")
                if item_id:
                    glpi_ids.append(item_id)
                else:
                    logger.warning(f"Could not extract ID from GLPI item for {serial_number}: {item}")

            # Извлекаем state_name из первого найденного устройства
            state_name = None
            if items and len(items) > 0:
                first_item = items[0]
                # Вариант 1: Берем название состояния из поля '31' (search API)
                state_name = first_item.get("31", "").strip() if first_item.get("31") else None
                # Вариант 2: Если нет поля '31', берем из states_id (detail API)
                if not state_name:
                    state_id = first_item.get("states_id")
                    if state_id:
                        state_name = client.get_state_name(state_id)

            # Сохраняем результат
            sync = GLPISync.objects.create(
                contract_device=device,
                status=status,
                searched_serial=serial_number,
                glpi_ids=glpi_ids,
                glpi_data={"items": items} if items else {},
                glpi_state_id=None,  # ID состояния не используется
                glpi_state_name=state_name or "",
                error_message=error,
                checked_by=user,
            )

            # Логируем только проблемы
            if status == "FOUND_MULTIPLE":
                logger.warning(f"GLPI: {serial_number} - найдено {len(glpi_ids)} карточек (конфликт)")
            elif status == "ERROR":
                logger.error(f"GLPI: {serial_number} - ошибка: {error}")

            return sync

    except GLPIAPIError as e:
        logger.error(f"GLPI API error for {serial_number}: {e}")

        sync = GLPISync.objects.create(
            contract_device=device, status="ERROR", searched_serial=serial_number, error_message=str(e), checked_by=user
        )
        return sync


def check_multiple_devices_in_glpi(device_ids: List[int], user: Optional[User] = None) -> Dict[str, int]:
    """
    Проверяет несколько устройств в GLPI.

    Args:
        device_ids: Список ID устройств для проверки
        user: Пользователь, инициировавший проверку

    Returns:
        Статистика проверки: {'total': N, 'found_single': N, 'found_multiple': N, ...}
    """
    devices = ContractDevice.objects.filter(id__in=device_ids)

    stats = {"total": devices.count(), "found_single": 0, "found_multiple": 0, "not_found": 0, "errors": 0}

    for device in devices:
        try:
            sync = check_device_in_glpi(device, user, force_check=True)

            if sync.status == "FOUND_SINGLE":
                stats["found_single"] += 1
            elif sync.status == "FOUND_MULTIPLE":
                stats["found_multiple"] += 1
            elif sync.status == "NOT_FOUND":
                stats["not_found"] += 1
            else:
                stats["errors"] += 1

        except Exception as e:
            logger.exception(f"Ошибка при проверке устройства {device.id}: {e}")
            stats["errors"] += 1

    logger.info(
        f'GLPI: массовая проверка завершена - {stats["total"]} устройств '
        f'(найдено: {stats["found_single"]}, конфликтов: {stats["found_multiple"]}, '
        f'не найдено: {stats["not_found"]}, ошибок: {stats["errors"]})'
    )

    return stats


def get_last_sync_for_device(device: ContractDevice) -> Optional[GLPISync]:
    """
    Получает последнюю синхронизацию для устройства.

    Args:
        device: Устройство

    Returns:
        Последний GLPISync или None
    """
    return GLPISync.objects.filter(contract_device=device).first()


def get_devices_with_conflicts() -> List[ContractDevice]:
    """
    Возвращает список устройств, для которых найдено несколько карточек в GLPI.

    Returns:
        QuerySet устройств с конфликтами
    """
    conflict_syncs = (
        GLPISync.objects.filter(status="FOUND_MULTIPLE").values_list("contract_device_id", flat=True).distinct()
    )

    return ContractDevice.objects.filter(id__in=conflict_syncs)


def get_devices_not_in_glpi() -> List[ContractDevice]:
    """
    Возвращает список устройств, не найденных в GLPI.

    Returns:
        QuerySet устройств, не найденных в GLPI
    """
    not_found_syncs = (
        GLPISync.objects.filter(status="NOT_FOUND").values_list("contract_device_id", flat=True).distinct()
    )

    return ContractDevice.objects.filter(id__in=not_found_syncs)


# ─────────────────────────────────────────────────────────────────────────────
# Кросс-проверка офлайн/неопрашиваемых устройств с GLPI
# ─────────────────────────────────────────────────────────────────────────────


def get_offline_printers():
    """
    Возвращает активные принтеры без SUCCESS InventoryTask за последние 24 часа.
    """
    from inventory.models import InventoryTask, Printer

    since = timezone.now() - timedelta(hours=24)

    online_ids = (
        InventoryTask.objects.filter(status="SUCCESS", task_timestamp__gte=since, printer__is_active=True)
        .values_list("printer_id", flat=True)
        .distinct()
    )

    return (
        Printer.objects.filter(is_active=True)
        .exclude(id__in=online_ids)
        .select_related("organization", "device_model", "device_model__manufacturer")
    )


def get_unpolled_network_devices():
    """
    Возвращает ContractDevice с сетевым портом, но без активного опроса.
    (printer=NULL или printer.is_active=False)
    """
    return (
        ContractDevice.objects.filter(model__has_network_port=True)
        .filter(Q(printer__isnull=True) | Q(printer__is_active=False))
        .select_related("organization", "model", "model__manufacturer")
    )


def _parse_glpi_date(date_str):
    """Парсит строку даты из GLPI в datetime."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return timezone.make_aware(datetime.strptime(date_str, fmt))
        except (ValueError, TypeError):
            continue
    return None


def cross_check_with_glpi(batch_id, freshness_days=None):
    """
    Основная функция кросс-проверки:
    1. Собирает офлайн принтеры + неопрашиваемые устройства
    2. Для каждого ищет в GLPI по серийному номеру
    3. Если найден — получает детальные данные (счётчик, дата обновления)
    4. Сохраняет результаты в GLPICrossCheck

    Returns:
        dict: Статистика проверки
    """
    if freshness_days is None:
        freshness_days = getattr(settings, "GLPI_FRESHNESS_DAYS", 7)

    freshness_cutoff = timezone.now() - timedelta(days=freshness_days)

    stats = {
        "total": 0,
        "glpi_active": 0,
        "glpi_stale": 0,
        "not_found": 0,
        "no_serial": 0,
        "errors": 0,
    }

    # Собираем устройства для проверки, дедупликация по серийнику
    devices_to_check = []  # list of (serial, category, printer, contract_device, ip, org_name)
    seen_serials = set()

    # 1. Офлайн принтеры (приоритет)
    for printer in get_offline_printers():
        serial = (printer.serial_number or "").strip()
        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            org_name = printer.organization.name if printer.organization else ""
            devices_to_check.append(
                {
                    "serial": serial,
                    "category": "OFFLINE",
                    "printer": printer,
                    "contract_device": None,
                    "ip": printer.ip_address,
                    "org_name": org_name,
                    "model": printer.device_model.name if printer.device_model else printer.model,
                }
            )

    # 2. Неопрашиваемые устройства с сетевым портом
    for device in get_unpolled_network_devices():
        serial = (device.serial_number or "").strip()
        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            org_name = device.organization.name if device.organization else ""
            devices_to_check.append(
                {
                    "serial": serial,
                    "category": "UNPOLLED",
                    "printer": None,
                    "contract_device": device,
                    "ip": None,
                    "org_name": org_name,
                    "model": str(device.model) if device.model else "",
                }
            )
        elif not serial:
            # Без серийника — сохраняем запись NO_SERIAL
            org_name = device.organization.name if device.organization else ""
            GLPICrossCheck.objects.create(
                contract_device=device,
                category="UNPOLLED",
                status="NO_SERIAL",
                serial_number="",
                organization_name=org_name,
                batch_id=batch_id,
            )
            stats["no_serial"] += 1
            stats["total"] += 1

    # Также записываем NO_SERIAL для офлайн принтеров без серийника
    for printer in get_offline_printers():
        serial = (printer.serial_number or "").strip()
        if not serial:
            org_name = printer.organization.name if printer.organization else ""
            GLPICrossCheck.objects.create(
                printer=printer,
                category="OFFLINE",
                status="NO_SERIAL",
                serial_number="",
                ip_address=printer.ip_address,
                organization_name=org_name,
                batch_id=batch_id,
            )
            stats["no_serial"] += 1
            stats["total"] += 1

    stats["total"] += len(devices_to_check)

    if not devices_to_check:
        logger.info("Кросс-проверка GLPI: нет устройств для проверки")
        return stats

    # Проверяем в GLPI
    try:
        with GLPIClient() as client:
            for idx, device_info in enumerate(devices_to_check, 1):
                try:
                    status_result, items, error = client.search_printer_by_serial(device_info["serial"])

                    if status_result in ("FOUND_SINGLE", "FOUND_MULTIPLE") and items:
                        # Берём первый найденный и получаем детальные данные
                        first_item = items[0]
                        glpi_id = first_item.get("2") or first_item.get("id")

                        glpi_name = ""
                        glpi_counter = None
                        glpi_date = None
                        glpi_state = ""

                        if glpi_id:
                            detail = client.get_printer(int(glpi_id))
                            if detail:
                                glpi_name = detail.get("name", "")
                                glpi_counter = detail.get("last_pages_counter")
                                if glpi_counter is not None:
                                    try:
                                        glpi_counter = int(glpi_counter)
                                    except (ValueError, TypeError):
                                        glpi_counter = None
                                glpi_state = detail.get("states_name", "") or ""

                            # Определяем дату по PrinterLog (SNMP-инвентаризация),
                            # а не по date_mod (обновляется и при USB)
                            printer_log = client.get_printer_log(int(glpi_id))
                            if printer_log and len(printer_log) > 0:
                                latest_log = printer_log[0]
                                log_counter = latest_log.get("total_pages")
                                if log_counter is not None:
                                    try:
                                        glpi_counter = int(log_counter)
                                    except (ValueError, TypeError):
                                        pass
                                glpi_date = _parse_glpi_date(latest_log.get("date"))

                        # Определяем статус свежести:
                        # GLPI_ACTIVE только если есть свежая запись в PrinterLog
                        # (реальный SNMP-опрос, а не просто USB-подключение)
                        if glpi_date and glpi_date >= freshness_cutoff and glpi_counter:
                            check_status = "GLPI_ACTIVE"
                            stats["glpi_active"] += 1
                        else:
                            check_status = "GLPI_STALE"
                            stats["glpi_stale"] += 1

                        GLPICrossCheck.objects.create(
                            printer=device_info["printer"],
                            contract_device=device_info["contract_device"],
                            category=device_info["category"],
                            status=check_status,
                            serial_number=device_info["serial"],
                            ip_address=device_info["ip"],
                            organization_name=device_info["org_name"],
                            glpi_printer_id=int(glpi_id) if glpi_id else None,
                            glpi_name=glpi_name,
                            glpi_last_pages_counter=glpi_counter,
                            glpi_date_mod=glpi_date,
                            glpi_state_name=glpi_state,
                            batch_id=batch_id,
                        )

                    elif status_result == "NOT_FOUND":
                        stats["not_found"] += 1
                        GLPICrossCheck.objects.create(
                            printer=device_info["printer"],
                            contract_device=device_info["contract_device"],
                            category=device_info["category"],
                            status="NOT_FOUND",
                            serial_number=device_info["serial"],
                            ip_address=device_info["ip"],
                            organization_name=device_info["org_name"],
                            batch_id=batch_id,
                        )

                    else:
                        stats["errors"] += 1
                        GLPICrossCheck.objects.create(
                            printer=device_info["printer"],
                            contract_device=device_info["contract_device"],
                            category=device_info["category"],
                            status="ERROR",
                            serial_number=device_info["serial"],
                            ip_address=device_info["ip"],
                            organization_name=device_info["org_name"],
                            batch_id=batch_id,
                        )

                except Exception as e:
                    logger.error(f"Ошибка проверки {device_info['serial']}: {e}")
                    stats["errors"] += 1
                    GLPICrossCheck.objects.create(
                        printer=device_info["printer"],
                        contract_device=device_info["contract_device"],
                        category=device_info["category"],
                        status="ERROR",
                        serial_number=device_info["serial"],
                        ip_address=device_info["ip"],
                        organization_name=device_info["org_name"],
                        batch_id=batch_id,
                    )

                # Rate limiting
                if idx < len(devices_to_check):
                    time.sleep(0.1)

                # Логируем прогресс каждые 20 устройств
                if idx % 20 == 0:
                    logger.info(f"Кросс-проверка GLPI: {idx}/{len(devices_to_check)} проверено")

    except GLPIAPIError as e:
        logger.error(f"Ошибка подключения к GLPI при кросс-проверке: {e}")

    # Очистка старых batch (оставляем 3 последних)
    old_batches = GLPICrossCheck.objects.values_list("batch_id", flat=True).distinct().order_by("-checked_at")
    # Получаем уникальные batch_id
    batch_ids = list(dict.fromkeys(old_batches))
    if len(batch_ids) > 3:
        GLPICrossCheck.objects.filter(batch_id__in=batch_ids[3:]).delete()

    logger.info(
        f"Кросс-проверка GLPI завершена: всего={stats['total']}, "
        f"активных в GLPI={stats['glpi_active']}, устаревших={stats['glpi_stale']}, "
        f"не найдено={stats['not_found']}, без серийника={stats['no_serial']}, "
        f"ошибок={stats['errors']}"
    )

    return stats


def get_cross_check_results(org_id=None, status_filter=None):
    """
    Возвращает результаты последней кросс-проверки.

    Args:
        org_id: ID организации для фильтрации
        status_filter: Фильтр по статусу ('GLPI_ACTIVE', 'GLPI_STALE', etc.)

    Returns:
        dict: {items: [...], summary: {total, offline_count, unpolled_count, last_checked}}
    """
    # Находим последний batch
    latest = GLPICrossCheck.objects.values_list("batch_id", flat=True).first()
    if not latest:
        return {"items": [], "summary": {"total": 0, "offline_count": 0, "unpolled_count": 0, "last_checked": None}}

    qs = GLPICrossCheck.objects.filter(batch_id=latest)

    if org_id:
        from inventory.models import Organization

        try:
            org_name = Organization.objects.get(pk=org_id).name
            qs = qs.filter(organization_name=org_name)
        except Organization.DoesNotExist:
            qs = qs.none()

    # По умолчанию показываем только GLPI_ACTIVE
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        qs = qs.filter(status="GLPI_ACTIVE")

    items = []
    for record in qs:
        items.append(
            {
                "id": record.id,
                "category": record.category,
                "category_display": record.get_category_display(),
                "serial_number": record.serial_number,
                "ip_address": record.ip_address or "",
                "organization": record.organization_name,
                "glpi_name": record.glpi_name,
                "glpi_last_pages_counter": record.glpi_last_pages_counter,
                "glpi_date_mod": record.glpi_date_mod.isoformat() if record.glpi_date_mod else None,
                "glpi_state_name": record.glpi_state_name,
                "checked_at": record.checked_at.isoformat(),
                "printer_id": record.printer_id,
                "contract_device_id": record.contract_device_id,
            }
        )

    # Summary по всему batch (не фильтрованный)
    all_batch = GLPICrossCheck.objects.filter(batch_id=latest, status="GLPI_ACTIVE")
    if org_id:
        from inventory.models import Organization

        try:
            org_name = Organization.objects.get(pk=org_id).name
            all_batch = all_batch.filter(organization_name=org_name)
        except Organization.DoesNotExist:
            all_batch = all_batch.none()

    last_checked_record = GLPICrossCheck.objects.filter(batch_id=latest).first()

    summary = {
        "total": all_batch.count(),
        "offline_count": all_batch.filter(category="OFFLINE").count(),
        "unpolled_count": all_batch.filter(category="UNPOLLED").count(),
        "last_checked": last_checked_record.checked_at.isoformat() if last_checked_record else None,
    }

    return {"items": items, "summary": summary}
