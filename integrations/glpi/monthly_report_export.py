"""
Сервис для выгрузки счетчиков из monthly_report в GLPI.

Логика:
1. Берём последний заполненный (закрытый) месяц из monthly_report
2. Фильтруем устройства которые:
   - НЕ сетевые (has_network_port=False)
   - НЕ дублируются в отчете (уникальны по серийному номеру)
3. Проверяем что устройство есть в GLPI (статус FOUND_SINGLE)
4. Выгружаем суммарный счетчик *_end в GLPI
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from django.db.models import Count, Q

from monthly_report.models import MonthlyReport, MonthControl
from contracts.models import ContractDevice
from integrations.models import GLPISync
from .client import GLPIClient

logger = logging.getLogger(__name__)


def get_latest_closed_month() -> Optional[datetime]:
    """
    Получает последний закрытый месяц из monthly_report.

    Закрытый месяц = месяц где edit_until уже прошёл (месяц заполнен и закрыт).

    Returns:
        datetime: Дата последнего закрытого месяца (первый день месяца)
        None: Если нет закрытых месяцев
    """
    try:
        # Получаем последний месяц где edit_until < now
        latest_control = MonthControl.objects.filter(
            edit_until__lt=datetime.now()
        ).order_by('-month').first()

        if latest_control:
            logger.info(f"Latest closed month: {latest_control.month}")
            return latest_control.month
        else:
            logger.warning("No closed months found in MonthControl")
            return None

    except Exception as e:
        logger.error(f"Error getting latest closed month: {e}")
        return None


def get_devices_for_export(month: datetime) -> List[Dict]:
    """
    Получает список устройств для выгрузки в GLPI за указанный месяц.

    Фильтры:
    1. Устройства из monthly_report за указанный месяц
    2. НЕ стоят на автоматическом опросе (device_ip пустой)
    3. НЕ дублируются (уникальны по серийному номеру в отчете)
    4. Есть в GLPI со статусом FOUND_SINGLE

    Args:
        month: Месяц для выгрузки

    Returns:
        List[Dict]: Список словарей с данными устройств для выгрузки
    """
    devices_to_export = []

    try:
        # Получаем все записи из monthly_report за указанный месяц
        reports = MonthlyReport.objects.filter(month=month)

        logger.info(f"Found {reports.count()} total reports for {month}")

        # Группируем по серийному номеру и находим дубликаты
        duplicates = reports.values('serial_number').annotate(
            count=Count('id')
        ).filter(count__gt=1).values_list('serial_number', flat=True)

        duplicates_set = set(duplicates)
        logger.info(f"Found {len(duplicates_set)} duplicate serial numbers")

        # Фильтруем - только уникальные серийные номера и НЕ на опросе
        unique_reports = reports.exclude(serial_number__in=duplicates_set).filter(
            Q(device_ip__isnull=True) | Q(device_ip='')
        )
        logger.info(f"After removing duplicates and filtering non-polled: {unique_reports.count()} reports")

        # Для каждого отчета проверяем условия
        for report in unique_reports:
            try:
                # Находим устройство в contracts по серийному номеру
                try:
                    contract_device = ContractDevice.objects.get(
                        serial_number=report.serial_number
                    )
                except ContractDevice.DoesNotExist:
                    logger.debug(f"Device {report.serial_number} not found in contracts, skipping")
                    continue
                except ContractDevice.MultipleObjectsReturned:
                    logger.warning(f"Multiple devices with serial {report.serial_number} in contracts, skipping")
                    continue

                # Проверяем наличие в GLPI со статусом FOUND_SINGLE
                latest_glpi_sync = GLPISync.objects.filter(
                    contract_device=contract_device
                ).order_by('-checked_at').first()

                if not latest_glpi_sync:
                    logger.debug(f"Device {report.serial_number} has no GLPI sync, skipping")
                    continue

                if latest_glpi_sync.status != 'FOUND_SINGLE':
                    logger.debug(
                        f"Device {report.serial_number} GLPI status is {latest_glpi_sync.status}, "
                        f"not FOUND_SINGLE, skipping"
                    )
                    continue

                # Проверяем что есть ровно один GLPI ID
                if not latest_glpi_sync.glpi_ids or len(latest_glpi_sync.glpi_ids) != 1:
                    logger.warning(
                        f"Device {report.serial_number} has invalid GLPI IDs: {latest_glpi_sync.glpi_ids}, skipping"
                    )
                    continue

                glpi_id = latest_glpi_sync.glpi_ids[0]

                # Считаем общий счетчик (сумма всех *_end)
                total_counter = (
                    report.a4_bw_end +
                    report.a4_color_end +
                    report.a3_bw_end +
                    report.a3_color_end
                )

                # Добавляем в список для выгрузки
                devices_to_export.append({
                    'report_id': report.id,
                    'serial_number': report.serial_number,
                    'inventory_number': report.inventory_number,
                    'equipment_model': report.equipment_model,
                    'organization': report.organization,
                    'city': report.city,
                    'address': report.address,
                    'glpi_id': glpi_id,
                    'total_counter': total_counter,
                    'contract_device_id': contract_device.id,
                })

            except Exception as e:
                logger.error(f"Error processing report {report.id} ({report.serial_number}): {e}")
                continue

        logger.info(f"Total devices ready for export: {len(devices_to_export)}")
        return devices_to_export

    except Exception as e:
        logger.exception(f"Error getting devices for export: {e}")
        return []


def export_counters_to_glpi(
    month: Optional[datetime] = None,
    progress_callback: Optional[callable] = None
) -> Dict:
    """
    Выгружает счетчики из monthly_report в GLPI.

    Args:
        month: Месяц для выгрузки (если None, берётся последний закрытый)
        progress_callback: Функция для отслеживания прогресса (принимает current, total, message)

    Returns:
        Dict: Статистика выгрузки
        {
            'success': True/False,
            'month': datetime,
            'total': int,
            'exported': int,
            'skipped': int,
            'errors': int,
            'error_details': List[Dict],
            'message': str
        }
    """
    try:
        # Определяем месяц для выгрузки
        if month is None:
            month = get_latest_closed_month()
            if month is None:
                return {
                    'success': False,
                    'message': 'Нет закрытых месяцев для выгрузки',
                    'total': 0,
                    'exported': 0,
                    'skipped': 0,
                    'errors': 0,
                    'error_details': []
                }

        # Получаем список устройств для выгрузки
        devices = get_devices_for_export(month)

        if not devices:
            return {
                'success': True,
                'month': month,
                'message': 'Нет устройств для выгрузки',
                'total': 0,
                'exported': 0,
                'skipped': 0,
                'errors': 0,
                'error_details': []
            }

        # Инициализируем статистику
        stats = {
            'success': True,
            'month': month,
            'total': len(devices),
            'exported': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        # Создаём GLPI клиент
        with GLPIClient() as glpi:
            for idx, device in enumerate(devices):
                try:
                    # Отправляем прогресс
                    if progress_callback:
                        progress_callback(
                            current=idx + 1,
                            total=len(devices),
                            message=f"Выгрузка {device['serial_number']}"
                        )

                    # Обновляем счетчик в GLPI
                    success, error = glpi.update_printer_counter(
                        printer_id=device['glpi_id'],
                        page_counter=device['total_counter']
                    )

                    if success:
                        stats['exported'] += 1
                        logger.info(
                            f"Successfully exported {device['serial_number']} "
                            f"(GLPI ID {device['glpi_id']}): {device['total_counter']} pages"
                        )
                    else:
                        stats['errors'] += 1
                        stats['error_details'].append({
                            'serial_number': device['serial_number'],
                            'inventory_number': device['inventory_number'],
                            'glpi_id': device['glpi_id'],
                            'error': error or 'Unknown error'
                        })
                        logger.error(
                            f"Failed to export {device['serial_number']}: {error}"
                        )

                except Exception as e:
                    stats['errors'] += 1
                    stats['error_details'].append({
                        'serial_number': device['serial_number'],
                        'inventory_number': device['inventory_number'],
                        'glpi_id': device.get('glpi_id'),
                        'error': str(e)
                    })
                    logger.exception(f"Exception exporting {device['serial_number']}: {e}")

        # Формируем итоговое сообщение
        if stats['errors'] == 0:
            stats['message'] = f"Успешно выгружено {stats['exported']} устройств"
        else:
            stats['message'] = (
                f"Выгружено {stats['exported']} устройств, "
                f"ошибок: {stats['errors']}"
            )

        return stats

    except Exception as e:
        logger.exception(f"Fatal error in export_counters_to_glpi: {e}")
        return {
            'success': False,
            'message': f"Критическая ошибка: {str(e)}",
            'total': 0,
            'exported': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }
