"""
Сервисы для работы с GLPI интеграцией.
Содержат бизнес-логику проверки и синхронизации.
"""

import logging
from typing import Dict, List, Optional
from django.contrib.auth.models import User
from django.utils import timezone

from contracts.models import ContractDevice
from integrations.models import GLPISync
from .client import GLPIClient, GLPIAPIError

logger = logging.getLogger(__name__)


def check_device_in_glpi(
    device: ContractDevice,
    user: Optional[User] = None,
    force_check: bool = False
) -> GLPISync:
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
            status='ERROR',
            searched_serial='',
            error_message='Серийный номер отсутствует',
            checked_by=user
        )
        logger.warning(f'Попытка проверки устройства без серийного номера: {device} (ID: {device.id})')
        return sync

    # Проверяем, не проверяли ли недавно (в течение часа)
    if not force_check:
        recent_sync = GLPISync.objects.filter(
            contract_device=device,
            checked_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).first()

        if recent_sync:
            logger.info(f"Используем кэшированный результат для {device.serial_number}")
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
                item_id = item.get('2') or item.get('id')
                if item_id:
                    glpi_ids.append(item_id)
                else:
                    logger.warning(f"Could not extract ID from GLPI item for {serial_number}: {item}")

            # Извлекаем state_name из первого найденного устройства
            state_name = None
            if items and len(items) > 0:
                first_item = items[0]
                # Вариант 1: Берем название состояния из поля '31' (search API)
                state_name = first_item.get('31', '').strip() if first_item.get('31') else None
                # Вариант 2: Если нет поля '31', берем из states_id (detail API)
                if not state_name:
                    state_id = first_item.get('states_id')
                    if state_id:
                        state_name = client.get_state_name(state_id)

            # Сохраняем результат
            sync = GLPISync.objects.create(
                contract_device=device,
                status=status,
                searched_serial=serial_number,
                glpi_ids=glpi_ids,
                glpi_data={'items': items} if items else {},
                glpi_state_id=None,  # ID состояния не используется
                glpi_state_name=state_name or '',
                error_message=error,
                checked_by=user
            )

            # Логируем только проблемы
            if status == 'FOUND_MULTIPLE':
                logger.warning(f'GLPI: {serial_number} - найдено {len(glpi_ids)} карточек (конфликт)')
            elif status == 'ERROR':
                logger.error(f'GLPI: {serial_number} - ошибка: {error}')

            return sync

    except GLPIAPIError as e:
        logger.error(f"GLPI API error for {serial_number}: {e}")

        sync = GLPISync.objects.create(
            contract_device=device,
            status='ERROR',
            searched_serial=serial_number,
            error_message=str(e),
            checked_by=user
        )
        return sync


def check_multiple_devices_in_glpi(
    device_ids: List[int],
    user: Optional[User] = None
) -> Dict[str, int]:
    """
    Проверяет несколько устройств в GLPI.

    Args:
        device_ids: Список ID устройств для проверки
        user: Пользователь, инициировавший проверку

    Returns:
        Статистика проверки: {'total': N, 'found_single': N, 'found_multiple': N, ...}
    """
    devices = ContractDevice.objects.filter(id__in=device_ids)

    stats = {
        'total': devices.count(),
        'found_single': 0,
        'found_multiple': 0,
        'not_found': 0,
        'errors': 0
    }

    for device in devices:
        try:
            sync = check_device_in_glpi(device, user, force_check=True)

            if sync.status == 'FOUND_SINGLE':
                stats['found_single'] += 1
            elif sync.status == 'FOUND_MULTIPLE':
                stats['found_multiple'] += 1
            elif sync.status == 'NOT_FOUND':
                stats['not_found'] += 1
            else:
                stats['errors'] += 1

        except Exception as e:
            logger.exception(f"Ошибка при проверке устройства {device.id}: {e}")
            stats['errors'] += 1

    logger.info(f'GLPI: массовая проверка завершена - {stats["total"]} устройств '
                f'(найдено: {stats["found_single"]}, конфликтов: {stats["found_multiple"]}, '
                f'не найдено: {stats["not_found"]}, ошибок: {stats["errors"]})')

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
    conflict_syncs = GLPISync.objects.filter(
        status='FOUND_MULTIPLE'
    ).values_list('contract_device_id', flat=True).distinct()

    return ContractDevice.objects.filter(id__in=conflict_syncs)


def get_devices_not_in_glpi() -> List[ContractDevice]:
    """
    Возвращает список устройств, не найденных в GLPI.

    Returns:
        QuerySet устройств, не найденных в GLPI
    """
    not_found_syncs = GLPISync.objects.filter(
        status='NOT_FOUND'
    ).values_list('contract_device_id', flat=True).distinct()

    return ContractDevice.objects.filter(id__in=not_found_syncs)
