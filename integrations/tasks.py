"""
Celery задачи для интеграций.
"""

import logging
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from contracts.models import ContractDevice

from .glpi.monthly_report_export import export_counters_to_glpi
from .glpi.services import check_device_in_glpi, cross_check_with_glpi

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, queue="high_priority")
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
            return {"success": False, "message": f"Неверный формат месяца: {month}"}

    # Callback для обновления прогресса
    def progress_callback(current, total, message):
        """Обновляет состояние задачи с текущим прогрессом"""
        self.update_state(
            state="PROGRESS",
            meta={
                "current": current,
                "total": total,
                "message": message,
                "percent": int((current / total) * 100) if total > 0 else 0,
            },
        )
        logger.debug(f"Progress: {current}/{total} - {message}")

    try:
        # Запускаем выгрузку
        result = export_counters_to_glpi(month=month_dt, progress_callback=progress_callback)

        logger.info(
            f"GLPI export completed: exported={result.get('exported', 0)}, " f"errors={result.get('errors', 0)}"
        )

        return result

    except Exception as exc:
        logger.exception(f"Fatal error in GLPI export task: {exc}")
        return {
            "success": False,
            "message": f"Критическая ошибка: {str(exc)}",
            "total": 0,
            "exported": 0,
            "errors": 0,
            "error_details": [],
        }


@shared_task(bind=True, max_retries=3, queue="high_priority", time_limit=3600)
def check_all_devices_in_glpi(self, update_contract_field=False, skip_check=False):
    """
    Ежедневная задача: проверяет все устройства в GLPI.

    Проходит по всем активным устройствам из ContractDevice,
    проверяет их наличие в GLPI и сохраняет результаты.

    Args:
        update_contract_field: Если True, обновляет поле "Заявлен в договоре" в GLPI
        skip_check: Если True, пропускает проверку наличия и только обновляет договор
                    (использует сохраненные ранее GLPI ID)

    Динамически получает актуальный список устройств при каждом запуске.
    """
    import time

    from integrations.glpi.client import GLPIClient

    start_time = time.time()

    logger.info("=" * 70)
    logger.info("🚀 НАЧАЛО ПРОВЕРКИ УСТРОЙСТВ В GLPI")
    if skip_check and update_contract_field:
        logger.info("   📝 Режим: Только обновление поля договора (без проверки)")
    elif update_contract_field:
        logger.info("   📝 Режим: Проверка + обновление поля договора")
    else:
        logger.info("   📝 Режим: Только проверка наличия")
    logger.info("=" * 70)

    try:
        # Получаем системного пользователя для фоновых задач
        # Или создаем специального пользователя 'glpi_sync'
        try:
            system_user = User.objects.get(username="glpi_sync")
            logger.info("✓ Используется пользователь: glpi_sync")
        except User.DoesNotExist:
            # Используем первого суперпользователя
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                logger.error("❌ No superuser found for GLPI sync task")
                return {"status": "error", "message": "No user available for sync"}
            logger.info(f"✓ Используется суперпользователь: {system_user.username}")

        # Динамически получаем все устройства с серийными номерами
        devices = (
            ContractDevice.objects.filter(serial_number__isnull=False)
            .exclude(serial_number="")
            .select_related("organization", "model")
        )

        total_devices = devices.count()
        logger.info(f"📊 Найдено устройств для проверки: {total_devices}")
        logger.info("-" * 70)

        # Инициализация GLPI клиента для обновления поля договора
        glpi_client = None
        if update_contract_field:
            try:
                glpi_client = GLPIClient()
                glpi_client.init_session()
                logger.info("✓ GLPI клиент инициализирован для обновления договоров")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к GLPI: {e}")
                logger.warning("⚠️  Продолжаем без обновления поля договора")
                glpi_client = None

        # Статистика
        stats = {
            "total": total_devices,
            "checked": 0,
            "found_single": 0,
            "found_multiple": 0,
            "not_found": 0,
            "errors": 0,
            "conflicts": [],  # Список ID устройств с конфликтами
            "contract_updated": 0,  # Количество обновленных договоров
            "contract_errors": 0,  # Ошибки при обновлении договоров
            "contract_error_details": [],  # Детали ошибок для вывода
        }

        # Обновляем состояние задачи
        self.update_state(state="PROGRESS", meta={"current": 0, "total": total_devices, "status": "Начало проверки..."})

        # Проверяем каждое устройство
        for idx, device in enumerate(devices, 1):
            try:
                logger.debug(f"Checking device {device.id}: {device.serial_number}")

                if skip_check:
                    # Режим "только обновление" - берем существующую запись из БД
                    from integrations.models import GLPISync

                    try:
                        sync = GLPISync.objects.filter(contract_device=device).latest("checked_at")
                        stats["checked"] += 1
                        logger.debug(f"Используем кэшированную запись от {sync.checked_at}")
                    except GLPISync.DoesNotExist:
                        logger.warning(f"⚠️  Устройство {device.serial_number} не найдено в кэше, пропускаем")
                        stats["errors"] += 1
                        continue
                else:
                    # Обычный режим - проверяем в GLPI
                    sync = check_device_in_glpi(
                        device, user=system_user, force_check=False  # Используем кэш если есть свежие данные
                    )
                    stats["checked"] += 1

                # Обновляем статистику
                if sync.status == "FOUND_SINGLE":
                    stats["found_single"] += 1

                    # Обновляем поле "Заявлен в договоре" если включена опция
                    if glpi_client and sync.glpi_ids:
                        try:
                            glpi_printer_id = sync.glpi_ids[0]
                            success, error = glpi_client.update_contract_field(
                                printer_id=glpi_printer_id, is_in_contract=True
                            )

                            if success:
                                stats["contract_updated"] += 1
                                logger.debug(
                                    f"✓ Договор обновлен для устройства {device.serial_number} (GLPI ID: {glpi_printer_id})"
                                )
                            else:
                                stats["contract_errors"] += 1
                                logger.error(f"❌ Ошибка обновления договора для {device.serial_number}: {error}")
                                # Сохраняем детали первых 5 ошибок для вывода
                                if len(stats["contract_error_details"]) < 5:
                                    stats["contract_error_details"].append(
                                        {"serial": device.serial_number, "glpi_id": glpi_printer_id, "error": error}
                                    )
                        except Exception as e:
                            stats["contract_errors"] += 1
                            logger.error(f"❌ Исключение при обновлении договора для {device.serial_number}: {e}")
                            # Сохраняем детали первых 5 ошибок для вывода
                            if len(stats["contract_error_details"]) < 5:
                                stats["contract_error_details"].append(
                                    {
                                        "serial": device.serial_number,
                                        "glpi_id": glpi_printer_id if "glpi_printer_id" in locals() else "N/A",
                                        "error": str(e),
                                    }
                                )

                elif sync.status == "FOUND_MULTIPLE":
                    stats["found_multiple"] += 1
                    stats["conflicts"].append(
                        {
                            "device_id": device.id,
                            "serial": device.serial_number,
                            "count": sync.glpi_count,
                            "glpi_ids": sync.glpi_ids,
                        }
                    )
                elif sync.status == "NOT_FOUND":
                    stats["not_found"] += 1
                elif sync.status == "ERROR":
                    stats["errors"] += 1

                # Логируем прогресс каждые 10 устройств
                if idx % 10 == 0:
                    progress_percent = int((idx / total_devices) * 100)
                    progress_msg = (
                        f"📈 Прогресс: {idx}/{total_devices} ({progress_percent}%) | "
                        f"Найдено: {stats['found_single']}, Конфликтов: {stats['found_multiple']}, "
                        f"Не найдено: {stats['not_found']}, Ошибок: {stats['errors']}"
                    )
                    if glpi_client:
                        progress_msg += f" | Договоров обновлено: {stats['contract_updated']}"
                    logger.info(progress_msg)

                    # Обновляем состояние задачи
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx,
                            "total": total_devices,
                            "percent": progress_percent,
                            "status": f"Проверено {idx} из {total_devices} устройств",
                            "stats": stats,
                        },
                    )

            except Exception as e:
                logger.error(f"❌ Error checking device {device.id}: {e}")
                stats["errors"] += 1

        # Закрываем GLPI сессию
        if glpi_client:
            try:
                glpi_client.kill_session()
                logger.info("✓ GLPI сессия завершена")
            except Exception as e:
                logger.warning(f"⚠️  Ошибка при закрытии GLPI сессии: {e}")

        # Финальный отчет
        elapsed_time = time.time() - start_time
        logger.info("=" * 70)
        logger.info("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        logger.info("=" * 70)
        logger.info(f"⏱️  Время выполнения: {elapsed_time:.1f}с ({elapsed_time / 60:.1f}м)")
        logger.info(f"📊 Проверено устройств: {stats['checked']}/{stats['total']}")
        logger.info(f"✓  Найдено (1 карточка): {stats['found_single']}")
        logger.info(f"⚠️  Конфликты (>1 карточки): {stats['found_multiple']}")
        logger.info(f"❌ Не найдено в GLPI: {stats['not_found']}")
        logger.info(f"❗ Ошибок при проверке: {stats['errors']}")

        # Статистика обновления договоров
        if update_contract_field:
            logger.info("-" * 70)
            logger.info("📝 ОБНОВЛЕНИЕ ПОЛЯ ДОГОВОРА:")
            logger.info(f"✓  Обновлено успешно: {stats['contract_updated']}")
            if stats["contract_errors"] > 0:
                logger.error(f"❌ Ошибок обновления: {stats['contract_errors']}")

                # Выводим детали первых ошибок
                if stats["contract_error_details"]:
                    logger.error("")
                    logger.error(f"Примеры ошибок (первые {len(stats['contract_error_details'])}):")
                    for detail in stats["contract_error_details"]:
                        logger.error(
                            f"  • Serial: {detail['serial']} | GLPI ID: {detail['glpi_id']}\n"
                            f"    Ошибка: {detail['error']}"
                        )

        # Если есть конфликты, логируем их детали
        if stats["conflicts"]:
            logger.warning("-" * 70)
            logger.warning(f"⚠️  ОБНАРУЖЕНО {len(stats['conflicts'])} КОНФЛИКТОВ:")
            for conflict in stats["conflicts"]:
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
        raise self.retry(exc=exc, countdown=60 * 5 * (2**self.request.retries))


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
            "ok": True,
            "device_id": device_id,
            "status": sync.status,
            "glpi_count": sync.glpi_count,
            "glpi_ids": sync.glpi_ids,
        }

    except ContractDevice.DoesNotExist:
        logger.error(f"Device {device_id} not found")
        return {"ok": False, "error": "Device not found"}
    except Exception as e:
        logger.exception(f"Error checking device {device_id}: {e}")
        return {"ok": False, "error": str(e)}


@shared_task(bind=True, max_retries=2, queue="low_priority", time_limit=7200)
def cross_check_glpi_task(self):
    """
    Кросс-проверка: находит офлайн/неопрашиваемые устройства,
    которые при этом активно опрашиваются в GLPI.

    Запускается ежедневно по расписанию или вручную.
    """
    batch_id = str(uuid4())
    freshness_days = getattr(settings, "GLPI_FRESHNESS_DAYS", 7)

    logger.info(f"Запуск кросс-проверки GLPI (batch={batch_id}, freshness={freshness_days} дней)")

    self.update_state(state="PROGRESS", meta={"status": "Начало кросс-проверки...", "batch_id": batch_id})

    try:
        stats = cross_check_with_glpi(batch_id=batch_id, freshness_days=freshness_days)
        logger.info(f"Кросс-проверка GLPI завершена: {stats}")
        return {"ok": True, "batch_id": batch_id, "stats": stats}

    except Exception as exc:
        logger.exception(f"Ошибка кросс-проверки GLPI: {exc}")
        raise self.retry(exc=exc, countdown=60 * 5 * (2**self.request.retries))
