"""
Celery задачи для интеграций.
"""

import logging
from celery import shared_task
from django.contrib.auth import get_user_model

from contracts.models import ContractDevice
from .glpi.services import check_device_in_glpi
from .glpi.monthly_report_export import export_counters_to_glpi

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, queue='high_priority')
def export_monthly_report_to_glpi(self, month=None):
    """
    Выгружает счетчики из monthly_report в GLPI с отслеживанием прогресса.

    Args:
        month: Месяц для выгрузки (ISO format string) или None для последнего закрытого

    Returns:
        dict: Результат выгрузки со статистикой
    """
    from datetime import datetime

    logger.info(f"Starting GLPI export task, month={month}")

    # Конвертируем month из строки в datetime если указан
    month_dt = None
    if month:
        try:
            month_dt = datetime.fromisoformat(month)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid month format: {month}, error: {e}")
            return {
                'success': False,
                'message': f'Неверный формат месяца: {month}'
            }

    # Callback для обновления прогресса
    def progress_callback(current, total, message):
        """Обновляет состояние задачи с текущим прогрессом"""
        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'message': message,
                'percent': int((current / total) * 100) if total > 0 else 0
            }
        )
        logger.debug(f"Progress: {current}/{total} - {message}")

    try:
        # Запускаем выгрузку
        result = export_counters_to_glpi(
            month=month_dt,
            progress_callback=progress_callback
        )

        logger.info(
            f"GLPI export completed: exported={result.get('exported', 0)}, "
            f"errors={result.get('errors', 0)}"
        )

        return result

    except Exception as exc:
        logger.exception(f"Fatal error in GLPI export task: {exc}")
        return {
            'success': False,
            'message': f'Критическая ошибка: {str(exc)}',
            'total': 0,
            'exported': 0,
            'errors': 0,
            'error_details': []
        }


@shared_task(bind=True, max_retries=3, queue='high_priority')
def check_all_devices_in_glpi(self):
    """
    Ежедневная задача: проверяет все устройства в GLPI.

    Проходит по всем активным устройствам из ContractDevice,
    проверяет их наличие в GLPI и сохраняет результаты.

    Динамически получает актуальный список устройств при каждом запуске.
    """
    import time
    start_time = time.time()

    logger.info("=" * 70)
    logger.info("🚀 НАЧАЛО ПРОВЕРКИ УСТРОЙСТВ В GLPI")
    logger.info("=" * 70)

    try:
        # Получаем системного пользователя для фоновых задач
        # Или создаем специального пользователя 'glpi_sync'
        try:
            system_user = User.objects.get(username='glpi_sync')
            logger.info(f"✓ Используется пользователь: glpi_sync")
        except User.DoesNotExist:
            # Используем первого суперпользователя
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                logger.error("❌ No superuser found for GLPI sync task")
                return {
                    'status': 'error',
                    'message': 'No user available for sync'
                }
            logger.info(f"✓ Используется суперпользователь: {system_user.username}")

        # Динамически получаем все устройства с серийными номерами
        devices = ContractDevice.objects.filter(
            serial_number__isnull=False
        ).exclude(
            serial_number=''
        ).select_related('organization', 'model')

        total_devices = devices.count()
        logger.info(f"📊 Найдено устройств для проверки: {total_devices}")
        logger.info("-" * 70)

        # Статистика
        stats = {
            'total': total_devices,
            'checked': 0,
            'found_single': 0,
            'found_multiple': 0,
            'not_found': 0,
            'errors': 0,
            'conflicts': []  # Список ID устройств с конфликтами
        }

        # Обновляем состояние задачи
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': total_devices,
                'status': 'Начало проверки...'
            }
        )

        # Проверяем каждое устройство
        for idx, device in enumerate(devices, 1):
            try:
                logger.debug(f"Checking device {device.id}: {device.serial_number}")

                sync = check_device_in_glpi(
                    device,
                    user=system_user,
                    force_check=False  # Используем кэш если есть свежие данные
                )

                stats['checked'] += 1

                # Обновляем статистику
                if sync.status == 'FOUND_SINGLE':
                    stats['found_single'] += 1
                elif sync.status == 'FOUND_MULTIPLE':
                    stats['found_multiple'] += 1
                    stats['conflicts'].append({
                        'device_id': device.id,
                        'serial': device.serial_number,
                        'count': sync.glpi_count,
                        'glpi_ids': sync.glpi_ids
                    })
                elif sync.status == 'NOT_FOUND':
                    stats['not_found'] += 1
                elif sync.status == 'ERROR':
                    stats['errors'] += 1

                # Логируем прогресс каждые 10 устройств
                if idx % 10 == 0:
                    progress_percent = int((idx / total_devices) * 100)
                    logger.info(
                        f"📈 Прогресс: {idx}/{total_devices} ({progress_percent}%) | "
                        f"Найдено: {stats['found_single']}, Конфликтов: {stats['found_multiple']}, "
                        f"Не найдено: {stats['not_found']}, Ошибок: {stats['errors']}"
                    )

                    # Обновляем состояние задачи
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': idx,
                            'total': total_devices,
                            'percent': progress_percent,
                            'status': f'Проверено {idx} из {total_devices} устройств',
                            'stats': stats
                        }
                    )

            except Exception as e:
                logger.error(f"❌ Error checking device {device.id}: {e}")
                stats['errors'] += 1

        # Финальный отчет
        elapsed_time = time.time() - start_time
        logger.info("=" * 70)
        logger.info("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        logger.info("=" * 70)
        logger.info(f"⏱️  Время выполнения: {elapsed_time:.1f}с ({elapsed_time/60:.1f}м)")
        logger.info(f"📊 Проверено устройств: {stats['checked']}/{stats['total']}")
        logger.info(f"✓  Найдено (1 карточка): {stats['found_single']}")
        logger.info(f"⚠️  Конфликты (>1 карточки): {stats['found_multiple']}")
        logger.info(f"❌ Не найдено в GLPI: {stats['not_found']}")
        logger.info(f"❗ Ошибок при проверке: {stats['errors']}")

        # Если есть конфликты, логируем их детали
        if stats['conflicts']:
            logger.warning("-" * 70)
            logger.warning(f"⚠️  ОБНАРУЖЕНО {len(stats['conflicts'])} КОНФЛИКТОВ:")
            for conflict in stats['conflicts']:
                logger.warning(
                    f"  • Device #{conflict['device_id']} ({conflict['serial']}): "
                    f"{conflict['count']} карточек в GLPI - IDs: {conflict['glpi_ids']}"
                )

        logger.info("=" * 70)

        return stats

    except Exception as exc:
        elapsed_time = time.time() - start_time
        logger.error("=" * 70)
        logger.exception(f"❌ КРИТИЧЕСКАЯ ОШИБКА после {elapsed_time:.1f}с: {exc}")
        logger.error("=" * 70)
        # Retry with exponential backoff: 5min, 15min, 45min
        raise self.retry(exc=exc, countdown=60 * 5 * (2 ** self.request.retries))


@shared_task
def check_single_device_in_glpi(device_id, user_id=None, force_check=False):
    """
    Проверяет одно устройство в GLPI (асинхронная версия).

    Args:
        device_id: ID устройства
        user_id: ID пользователя, запустившего проверку
        force_check: Принудительная проверка (игнорировать кэш)

    Returns:
        dict: Результат проверки
    """
    try:
        device = ContractDevice.objects.get(id=device_id)

        # Получаем пользователя
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        # Если пользователь не указан, используем системного
        if not user:
            user = User.objects.filter(is_superuser=True).first()

        sync = check_device_in_glpi(device, user=user, force_check=force_check)

        return {
            'ok': True,
            'device_id': device_id,
            'status': sync.status,
            'glpi_count': sync.glpi_count,
            'glpi_ids': sync.glpi_ids,
        }

    except ContractDevice.DoesNotExist:
        logger.error(f"Device {device_id} not found")
        return {
            'ok': False,
            'error': 'Device not found'
        }
    except Exception as e:
        logger.exception(f"Error checking device {device_id}: {e}")
        return {
            'ok': False,
            'error': str(e)
        }
