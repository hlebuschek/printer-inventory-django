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


def get_devices_for_export(month: datetime) -> Tuple[List[Dict], Dict, Dict]:
    """
    Получает список устройств для выгрузки в GLPI за указанный месяц.

    Фильтры:
    1. Устройства из monthly_report за указанный месяц
    2. НЕ стоят на автоматическом опросе (device_ip пустой)
    3. Группируются по серийному номеру (для A3 устройств может быть несколько строк)
    4. Есть в GLPI со статусом FOUND_SINGLE

    Args:
        month: Месяц для выгрузки

    Returns:
        Tuple[List[Dict], Dict, Dict]:
            - Список словарей с данными устройств для выгрузки
            - Статистика пропущенных устройств
            - Детализация пропущенных устройств
    """
    devices_to_export = []
    skip_stats = {
        'on_polling': 0,
        'not_in_contracts': 0,
        'no_glpi_sync': 0,
        'glpi_not_found': 0,
        'glpi_multiple': 0,
        'glpi_error': 0,
        'invalid_glpi_ids': 0,
    }
    skip_details = {
        'on_polling': [],
        'not_in_contracts': [],
        'no_glpi_sync': [],
        'glpi_not_found': [],
        'glpi_multiple': [],
        'glpi_error': [],
        'invalid_glpi_ids': [],
    }

    try:
        # Получаем все записи из monthly_report за указанный месяц
        reports = MonthlyReport.objects.filter(month=month)

        logger.info(f"Found {reports.count()} total reports for {month}")

        # Группируем по серийному номеру
        # Для устройств с A3 может быть несколько строк - объединяем их
        from collections import defaultdict
        grouped_devices = defaultdict(list)

        for report in reports:
            if report.serial_number:
                grouped_devices[report.serial_number].append(report)

        logger.info(f"Found {len(grouped_devices)} unique devices (grouped by serial number)")

        # Обрабатываем каждую группу устройств
        for serial_number, device_reports in grouped_devices.items():
            try:
                # Проверяем что хотя бы одна строка НЕ на опросе
                has_non_polling = any(
                    not r.device_ip for r in device_reports
                )

                if not has_non_polling:
                    # Все строки этого устройства на опросе - пропускаем
                    skip_stats['on_polling'] += 1
                    first_report = device_reports[0]
                    skip_details['on_polling'].append({
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'device_ip': first_report.device_ip,
                        'rows_count': len(device_reports),
                    })
                    logger.debug(f"Device {serial_number} is on polling, skipping ({len(device_reports)} rows)")
                    continue

                # Берём данные из первой строки для общей информации
                first_report = device_reports[0]

                # Суммируем счётчики из всех строк группы (A4 + A3)
                total_a4_bw = sum(r.a4_bw_end for r in device_reports)
                total_a4_color = sum(r.a4_color_end for r in device_reports)
                total_a3_bw = sum(r.a3_bw_end for r in device_reports)
                total_a3_color = sum(r.a3_color_end for r in device_reports)

                if len(device_reports) > 1:
                    logger.debug(
                        f"Device {serial_number}: merged {len(device_reports)} rows - "
                        f"A4_bw={total_a4_bw}, A4_color={total_a4_color}, "
                        f"A3_bw={total_a3_bw}, A3_color={total_a3_color}"
                    )

                # Находим устройство в contracts по серийному номеру
                try:
                    contract_device = ContractDevice.objects.get(
                        serial_number=serial_number
                    )
                except ContractDevice.DoesNotExist:
                    skip_stats['not_in_contracts'] += 1
                    skip_details['not_in_contracts'].append({
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'reason': 'Не найдено в модуле Договоров',
                    })
                    logger.debug(f"Device {serial_number} not found in contracts, skipping")
                    continue
                except ContractDevice.MultipleObjectsReturned:
                    skip_stats['not_in_contracts'] += 1
                    skip_details['not_in_contracts'].append({
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'reason': 'Найдено несколько устройств с таким серийным номером',
                    })
                    logger.warning(f"Multiple devices with serial {serial_number} in contracts, skipping")
                    continue

                # Проверяем наличие в GLPI со статусом FOUND_SINGLE
                latest_glpi_sync = GLPISync.objects.filter(
                    contract_device=contract_device
                ).order_by('-checked_at').first()

                if not latest_glpi_sync:
                    skip_stats['no_glpi_sync'] += 1
                    skip_details['no_glpi_sync'].append({
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'reason': 'Никогда не проверялось в GLPI',
                    })
                    logger.debug(f"Device {serial_number} has no GLPI sync, skipping")
                    continue

                if latest_glpi_sync.status != 'FOUND_SINGLE':
                    # Подсчитываем статистику по типам статусов
                    detail = {
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'checked_at': latest_glpi_sync.checked_at.strftime('%Y-%m-%d %H:%M:%S'),
                    }

                    if latest_glpi_sync.status == 'NOT_FOUND':
                        skip_stats['glpi_not_found'] += 1
                        detail['reason'] = 'Не найдено в GLPI'
                        skip_details['glpi_not_found'].append(detail)
                    elif latest_glpi_sync.status == 'FOUND_MULTIPLE':
                        skip_stats['glpi_multiple'] += 1
                        detail['reason'] = f"Найдено несколько карточек ({len(latest_glpi_sync.glpi_ids or [])})"
                        detail['glpi_ids'] = ', '.join(map(str, latest_glpi_sync.glpi_ids or []))
                        skip_details['glpi_multiple'].append(detail)
                    elif latest_glpi_sync.status == 'ERROR':
                        skip_stats['glpi_error'] += 1
                        detail['reason'] = 'Ошибка при проверке в GLPI'
                        detail['error'] = latest_glpi_sync.error_message or 'Нет описания ошибки'
                        skip_details['glpi_error'].append(detail)

                    logger.debug(
                        f"Device {serial_number} GLPI status is {latest_glpi_sync.status}, "
                        f"not FOUND_SINGLE, skipping"
                    )
                    continue

                # Проверяем что есть ровно один GLPI ID
                if not latest_glpi_sync.glpi_ids or len(latest_glpi_sync.glpi_ids) != 1:
                    skip_stats['invalid_glpi_ids'] += 1
                    skip_details['invalid_glpi_ids'].append({
                        'serial_number': serial_number,
                        'inventory_number': first_report.inventory_number,
                        'equipment_model': first_report.equipment_model,
                        'reason': 'Некорректный GLPI ID',
                        'glpi_status': latest_glpi_sync.status,
                        'glpi_ids': str(latest_glpi_sync.glpi_ids),
                        'glpi_ids_count': len(latest_glpi_sync.glpi_ids) if latest_glpi_sync.glpi_ids else 0,
                        'checked_at': latest_glpi_sync.checked_at.strftime('%Y-%m-%d %H:%M:%S'),
                    })
                    logger.warning(
                        f"Device {serial_number} has invalid GLPI IDs: {latest_glpi_sync.glpi_ids}, skipping"
                    )
                    continue

                glpi_id = latest_glpi_sync.glpi_ids[0]

                # Считаем общий счетчик в эквиваленте A4 (A3 = 2×A4)
                total_counter = (
                    total_a4_bw +
                    total_a4_color +
                    (total_a3_bw * 2) +
                    (total_a3_color * 2)
                )

                # Добавляем в список для выгрузки
                devices_to_export.append({
                    'report_id': first_report.id,
                    'serial_number': serial_number,
                    'inventory_number': first_report.inventory_number,
                    'equipment_model': first_report.equipment_model,
                    'organization': first_report.organization,
                    'city': first_report.city,
                    'address': first_report.address,
                    'glpi_id': glpi_id,
                    'total_counter': total_counter,
                    'contract_device_id': contract_device.id,
                    'rows_merged': len(device_reports),  # Для отладки
                })

            except Exception as e:
                logger.error(f"Error processing device {serial_number}: {e}")
                continue

        total_skipped = sum(skip_stats.values())
        logger.info(f"Total devices ready for export: {len(devices_to_export)}")
        logger.info(f"Total skipped devices: {total_skipped} - {skip_stats}")

        return devices_to_export, skip_stats, skip_details

    except Exception as e:
        logger.exception(f"Error getting devices for export: {e}")
        return [], {}, {}


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
        devices, skip_stats, skip_details = get_devices_for_export(month)

        if not devices:
            return {
                'success': True,
                'month': month,
                'message': 'Нет устройств для выгрузки',
                'total': 0,
                'exported': 0,
                'skipped': sum(skip_stats.values()) if skip_stats else 0,
                'skip_reasons': skip_stats,
                'skip_details': skip_details,
                'errors': 0,
                'error_details': []
            }

        # Инициализируем статистику
        stats = {
            'success': True,
            'month': month,
            'total': len(devices),
            'exported': 0,
            'skipped': sum(skip_stats.values()) if skip_stats else 0,
            'skip_reasons': skip_stats,
            'skip_details': skip_details,
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
            'skip_reasons': {},
            'errors': 0,
            'error_details': []
        }
