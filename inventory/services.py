# inventory/services.py
import concurrent.futures
import logging
import os
import platform
import tempfile
import threading
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Union

from asgiref.sync import async_to_sync

from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import InventoryTask, PageCounter, PollingMethod, Printer, PrinterChangeLog, WebParsingRule
from .utils import (
    extract_mac_address,
    extract_page_counters,
    run_glpi_command,
    send_device_get_request,
    validate_against_history,
    validate_inventory,
    xml_to_json,
)
from .web_parser import execute_web_parsing, export_to_xml

# ──────────────────────────────────────────────────────────────────────────────
# ПУТИ ВЫВОДА GLPI
# ──────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.join(settings.BASE_DIR, "inventory_output")
INV_DIR = os.path.join(OUTPUT_DIR, "netinventory")
DISC_DIR = os.path.join(OUTPUT_DIR, "netdiscovery")
os.makedirs(INV_DIR, exist_ok=True)
os.makedirs(DISC_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Платформа
PLATFORM = platform.system().lower()


# ──────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ
# ──────────────────────────────────────────────────────────────────────────────


def _get_glpi_executable_name(tool: str) -> str:
    """
    Возвращает имя бинаря для ОС.
    tool: 'netdiscovery' | 'netinventory'
    """
    if PLATFORM == "windows":
        return f"glpi-{tool}.bat"
    return f"glpi-{tool}"


def _get_glpi_paths() -> Tuple[str, str]:
    """Возвращает абсолютные пути к glpi-netdiscovery и glpi-netinventory."""
    glpi_path = getattr(settings, "GLPI_PATH", "")
    if not glpi_path:
        raise RuntimeError("GLPI_PATH не задан в настройках")

    base = glpi_path.replace("\\", "/")
    if any(key in base for key in ("netdiscovery", "netinventory")):
        if "netdiscovery" in base:
            disc_exe = glpi_path
            inv_exe = glpi_path.replace("netdiscovery", "netinventory")
        else:
            inv_exe = glpi_path
            disc_exe = glpi_path.replace("netinventory", "netdiscovery")
    else:
        disc_exe = os.path.join(glpi_path, _get_glpi_executable_name("netdiscovery"))
        inv_exe = os.path.join(glpi_path, _get_glpi_executable_name("netinventory"))

    return disc_exe, inv_exe


def _get_glpi_discovery_path() -> str:
    """Возвращает путь только к glpi-netdiscovery."""
    disc_exe, _ = _get_glpi_paths()
    return disc_exe


def _build_glpi_command(executable: str, ip: str, community: str = "public", extra_args: str = "") -> str:
    """Собирает команду запуска GLPI с учётом ОС, sudo и пользователя."""
    base_cmd = f'"{executable}" --host {ip} -i --community {community} --save="{OUTPUT_DIR}" --debug'

    if extra_args:
        base_cmd += f" {extra_args}"
    if PLATFORM in ("linux", "darwin"):
        use_sudo = getattr(settings, "GLPI_USE_SUDO", True)
        glpi_user = getattr(settings, "GLPI_USER", "")
        if os.geteuid() == 0:
            if glpi_user:
                base_cmd = f"/usr/bin/sudo -u {glpi_user} {base_cmd}"
            else:
                base_cmd = f"/usr/bin/sudo {base_cmd}"
        elif use_sudo:
            base_cmd = f"/usr/bin/sudo {base_cmd}"
    return base_cmd


def _validate_glpi_installation() -> Tuple[bool, str]:
    """Проверяет наличие и исполнимость glpi-netdiscovery."""
    try:
        disc_exe = _get_glpi_discovery_path()

        if not os.path.exists(disc_exe):
            return False, f"glpi-netdiscovery не найден: {disc_exe}"

        if PLATFORM != "windows":
            if not os.access(disc_exe, os.X_OK):
                return False, f"glpi-netdiscovery не исполняемый: {disc_exe}"

        return True, "GLPI Agent найден и доступен"
    except Exception as e:
        return False, f"Ошибка проверки GLPI Agent: {e}"


def _possible_xml_paths(ip: str, prefer: str) -> Tuple[str, ...]:
    """Кандидатные пути к XML для IP."""
    disc_xml = os.path.join(DISC_DIR, f"{ip}.xml")
    inv_xml = os.path.join(INV_DIR, f"{ip}.xml")
    direct = os.path.join(OUTPUT_DIR, f"{ip}.xml")
    if prefer == "disc":
        return (disc_xml, direct, inv_xml)
    return (inv_xml, direct, disc_xml)


def _cleanup_xml(ip: str):
    """Удаляет старые XML по всем местам для IP."""
    for p in _possible_xml_paths(ip, prefer="inv"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def _save_xml_export(printer, xml_content: str) -> None:
    """
    Сохраняет XML в папку xml_exports (для GLPI).
    Хранится только последний файл для каждого принтера.
    """
    try:
        xml_export_dir = os.path.join(settings.MEDIA_ROOT, "xml_exports")
        os.makedirs(xml_export_dir, exist_ok=True)

        # Формируем имя файла: только серийник, без даты
        xml_filename = f"{printer.serial_number}.xml"
        xml_filepath = os.path.join(xml_export_dir, xml_filename)

        # Сохраняем файл (перезаписываем если существует)
        with open(xml_filepath, "w", encoding="utf-8") as f:
            f.write(xml_content)

        logger.info(f"✓ XML exported: {xml_filename}")
        print(f"   💾 XML сохранён: {xml_filename}")

    except Exception as e:
        logger.error(f"XML export error for {printer.ip_address}: {e}")
        print(f"   ⚠️  Ошибка сохранения XML: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# ОБРАБОТКА ЗАМЕНЫ ОБОРУДОВАНИЯ
# ──────────────────────────────────────────────────────────────────────────────


def _deactivate_printer(printer: Printer, replaced_by: Printer, triggered_by: str = "auto_poll") -> None:
    """
    Деактивирует принтер и логирует изменение.

    Args:
        printer: Принтер для деактивации
        replaced_by: Принтер, который заменил данный
        triggered_by: Источник события ('auto_poll' или 'manual')
    """
    old_values = {
        "ip_address": printer.ip_address,
        "serial_number": printer.serial_number,
        "mac_address": printer.mac_address,
        "is_active": True,
    }

    printer.is_active = False
    printer.replaced_at = timezone.now()
    printer.replaced_by = replaced_by
    printer.save(update_fields=["is_active", "replaced_at", "replaced_by"])

    PrinterChangeLog.objects.create(
        printer=printer,
        action="deactivation",
        old_values=old_values,
        new_values={"is_active": False},
        related_printer=replaced_by,
        comment=f"Заменён принтером {replaced_by.serial_number} ({replaced_by.ip_address})",
        triggered_by=triggered_by,
    )

    logger.info(
        f"Printer deactivated: {printer.ip_address} (SN: {printer.serial_number}) "
        f"-> replaced by {replaced_by.ip_address} (SN: {replaced_by.serial_number})"
    )


def handle_device_replacement(
    current_printer: Printer, new_serial: str, new_mac: Optional[str], triggered_by: str = "auto_poll"
) -> Tuple[bool, Optional[Printer], str]:
    """
    Обработка замены оборудования при обнаружении несоответствия серийника/MAC.

    Сценарии:
    1. Серийник найден в ContractDevice → проверяем, есть ли принтер с этим серийником
       a) Есть активный принтер → он сменил IP, обновляем IP и деактивируем текущий
       b) Нет принтера → создаём новый, деактивируем текущий

    Args:
        current_printer: Текущий принтер (по IP)
        new_serial: Серийник из опроса
        new_mac: MAC из опроса
        triggered_by: Источник ('auto_poll' или 'manual')

    Returns:
        (success, target_printer, message):
        - success: Успешно ли обработана замена
        - target_printer: Принтер для продолжения опроса (или None)
        - message: Описание результата
    """
    from contracts.models import ContractDevice

    from .utils import normalize_mac

    if not new_serial:
        return False, None, "Серийник не указан"

    new_serial = new_serial.strip()

    # 1. Проверяем наличие устройства в договорах
    contract_device = (
        ContractDevice.objects.filter(serial_number__iexact=new_serial).select_related("model", "organization").first()
    )

    if not contract_device:
        return False, None, f"Серийник {new_serial} не найден в договорах"

    ip_address = current_printer.ip_address
    organization = current_printer.organization

    # Нормализуем MAC
    if new_mac:
        new_mac = normalize_mac(new_mac)

    # 2. Ищем активный принтер с таким серийником (кроме текущего)
    existing_printer = (
        Printer.objects.filter(serial_number__iexact=new_serial, is_active=True).exclude(id=current_printer.id).first()
    )

    try:
        with transaction.atomic():
            if existing_printer:
                # ═══════════════════════════════════════════════════════════════
                # Сценарий A: Принтер сменил IP
                # Нашли активный принтер с таким серийником на другом IP
                # ═══════════════════════════════════════════════════════════════
                old_ip = existing_printer.ip_address

                logger.info(f"Device replacement: Printer SN={new_serial} moved from {old_ip} to {ip_address}")

                # Деактивируем текущий принтер (на этом IP)
                _deactivate_printer(current_printer, existing_printer, triggered_by)

                # Обновляем IP у найденного принтера
                old_values = {"ip_address": old_ip, "mac_address": existing_printer.mac_address}
                new_values = {"ip_address": ip_address}

                existing_printer.ip_address = ip_address
                update_fields = ["ip_address"]

                if new_mac and new_mac != existing_printer.mac_address:
                    new_values["mac_address"] = new_mac
                    existing_printer.mac_address = new_mac
                    update_fields.append("mac_address")

                existing_printer.save(update_fields=update_fields)

                # Логируем смену IP
                PrinterChangeLog.objects.create(
                    printer=existing_printer,
                    action="ip_change",
                    old_values=old_values,
                    new_values=new_values,
                    related_printer=current_printer,
                    comment=f"Принтер переехал с {old_ip} на {ip_address}",
                    triggered_by=triggered_by,
                )

                message = f"IP обновлён: {old_ip} → {ip_address} (SN: {new_serial})"
                logger.info(f"Device replacement completed: {message}")

                return True, existing_printer, message

            else:
                # ═══════════════════════════════════════════════════════════════
                # Сценарий B: Новое устройство заменило старое
                # Создаём новый принтер, деактивируем старый
                # ═══════════════════════════════════════════════════════════════

                logger.info(
                    f"Device replacement: New printer SN={new_serial} replaces "
                    f"SN={current_printer.serial_number} at IP={ip_address}"
                )

                # Создаём новый принтер
                new_printer = Printer.objects.create(
                    ip_address=ip_address,
                    serial_number=new_serial,
                    mac_address=new_mac,
                    organization=organization or contract_device.organization,
                    snmp_community=current_printer.snmp_community,
                    device_model=contract_device.model,
                    polling_method=current_printer.polling_method,
                    is_active=True,
                )

                # Деактивируем старый принтер
                _deactivate_printer(current_printer, new_printer, triggered_by)

                # Связываем с ContractDevice (если ещё не связан)
                if not contract_device.printer:
                    contract_device.printer = new_printer
                    contract_device.save(update_fields=["printer"])
                    logger.info(f"ContractDevice ID={contract_device.id} linked to new printer ID={new_printer.id}")

                # Логируем создание нового принтера
                PrinterChangeLog.objects.create(
                    printer=new_printer,
                    action="replacement",
                    old_values={},
                    new_values={"ip_address": ip_address, "serial_number": new_serial, "mac_address": new_mac},
                    related_printer=current_printer,
                    comment=f"Заменил принтер {current_printer.serial_number} ({current_printer.ip_address})",
                    triggered_by=triggered_by,
                )

                message = f"Создан новый принтер (замена {current_printer.serial_number})"
                logger.info(f"Device replacement completed: {message}")

                return True, new_printer, message

    except Exception as e:
        logger.error(f"Device replacement failed: {e}", exc_info=True)
        return False, None, f"Ошибка при замене оборудования: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# DISCOVERY ДЛЯ КНОПКИ /printers/add/
# ──────────────────────────────────────────────────────────────────────────────


def run_discovery_for_ip(ip: str, community: str = "public") -> Tuple[bool, str]:
    """
    Запускает glpi-netdiscovery для IP и возвращает (ok, xml_path | error).
    БЕЗ кэширования - выполняется каждый раз.
    """
    disc_exe = _get_glpi_discovery_path()

    # чистим старые файлы
    for p in _possible_xml_paths(ip, prefer="disc"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    cmd = f'"{disc_exe}" --host {ip} --community {community} --save="{OUTPUT_DIR}" --debug'
    if PLATFORM in ("linux", "darwin"):
        use_sudo = getattr(settings, "GLPI_USE_SUDO", True)
        glpi_user = getattr(settings, "GLPI_USER", "")
        if os.geteuid() == 0:
            if glpi_user:
                cmd = f"/usr/bin/sudo -u {glpi_user} {cmd}"
            else:
                cmd = f"/usr/bin/sudo {cmd}"
        elif use_sudo:
            cmd = f"/usr/bin/sudo {cmd}"

    ok, out = run_glpi_command(cmd)
    if not ok:
        return False, out or "netdiscovery failed"

    for candidate in _possible_xml_paths(ip, prefer="disc"):
        if os.path.exists(candidate):
            return True, candidate

    return False, f"XML not found for {ip} (save={OUTPUT_DIR})"


def extract_serial_from_xml(xml_input: Union[str, os.PathLike, bytes]) -> Optional[str]:
    """
    Возвращает содержимое первого тега <SERIAL>.
    БЕЗ кэширования.
    """
    if isinstance(xml_input, (str, os.PathLike)) and os.path.exists(str(xml_input)):
        file_path = str(xml_input)
        try:
            for _, elem in ET.iterparse(file_path, events=("end",)):
                tag = str(elem.tag).split("}", 1)[-1]
                if tag.upper() == "SERIAL":
                    val = (elem.text or "").strip()
                    return val or None
            return None
        except ET.ParseError:
            return None

    try:
        root = ET.fromstring(xml_input if isinstance(xml_input, (str, bytes)) else str(xml_input))
        for elem in root.iter():
            tag = str(elem.tag).split("}", 1)[-1]
            if tag.upper() == "SERIAL":
                val = (elem.text or "").strip()
                return val or None
        return None
    except ET.ParseError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ С MONTHLY REPORT
# ──────────────────────────────────────────────────────────────────────────────


def sync_to_monthly_reports(printer, counters):
    """
    Автоматически обновляет MonthlyReport записи после успешного опроса.

    Обновляет только:
    - Записи в открытых для редактирования месяцах (MonthControl.edit_until > now)
    - Поля где manual_edit_* = False (не редактировались вручную)

    Отправляет WebSocket уведомления для real-time обновления.
    """
    try:

        from monthly_report.models import MonthControl, MonthlyReport
        from monthly_report.services import recompute_group

        # Получаем serial_number из printer
        serial = printer.serial_number
        if not serial:
            logger.debug("sync_to_monthly_reports: принтер без serial_number, пропускаем")
            return

        # Находим открытые для редактирования месяцы С ВКЛЮЧЕННОЙ АВТОСИНХРОНИЗАЦИЕЙ
        now = timezone.now()

        # Сначала найдем все открытые месяцы
        all_editable = MonthControl.objects.filter(edit_until__gt=now)
        logger.info(f"sync_to_monthly_reports: найдено {all_editable.count()} открытых месяцев")

        # Затем фильтруем по auto_sync_enabled
        editable_months = MonthControl.objects.filter(
            edit_until__gt=now, auto_sync_enabled=True  # Только месяцы с включенной автосинхронизацией
        ).values_list("month", flat=True)

        logger.info(f"sync_to_monthly_reports: из них {len(editable_months)} с включенной автосинхронизацией")

        if not editable_months:
            logger.info("sync_to_monthly_reports: нет открытых месяцев с включенной автосинхронизацией")
            return

        # Находим все MonthlyReport для этого serial_number в открытых месяцах
        reports = MonthlyReport.objects.filter(serial_number=serial, month__in=editable_months)

        if not reports.exists():
            logger.debug(f"sync_to_monthly_reports: нет записей для serial={serial} в открытых месяцах")
            return

        logger.info(f"sync_to_monthly_reports: найдено {reports.count()} записей для обновления (serial={serial})")

        # Определяем дубли - используем ту же логику, что в services_inventory_sync.py
        reports_list = list(reports)
        from collections import defaultdict

        duplicate_groups = defaultdict(list)

        # Группируем по (month, serial_number, inventory_number)
        # ВАЖНО: включаем month, т.к. обрабатываем несколько месяцев одновременно!
        # Каждый месяц имеет свои собственные пары дублей
        for report in reports_list:
            sn = (report.serial_number or "").strip()
            inv = (report.inventory_number or "").strip()
            if not sn and not inv:
                continue
            # Ключ: (month, serial, inventory) - месяц ОБЯЗАТЕЛЬНО включаем!
            duplicate_groups[(report.month, sn, inv)].append(report)

        # Сортируем записи внутри каждой группы по order_number и id
        for key in duplicate_groups:
            duplicate_groups[key].sort(key=lambda x: (getattr(x, "order_number", 0), x.id))

        # Создаем маппинг report_id -> позицию в группе дублей
        report_dup_info = {}
        for key, group_reports in duplicate_groups.items():
            if len(group_reports) >= 2:  # Только группы с 2+ записями = дубли
                for position, report in enumerate(group_reports):
                    report_dup_info[report.id] = {"is_duplicate": True, "position": position}
                    logger.info(
                        f"  Дубль: month={key[0]}, serial={key[1]}, inv={key[2]}, report_id={report.id}, position={position}"
                    )

        # Используем ту же логику, что и в ручной синхронизации
        from monthly_report.services_inventory_sync import _assign_autofields

        channel_layer = get_channel_layer()
        updated_reports = []

        for report in reports_list:
            # Определяем является ли запись дублем и её позицию
            dup_info = report_dup_info.get(report.id, {"is_duplicate": False, "position": 0})
            is_duplicate = dup_info["is_duplicate"]
            dup_position = dup_info["position"]

            logger.info(f"  Обработка report_id={report.id}: is_duplicate={is_duplicate}, position={dup_position}")
            logger.info(
                f"  Счетчики из принтера: bw_a4={counters.get('bw_a4')}, color_a4={counters.get('color_a4')}, bw_a3={counters.get('bw_a3')}, color_a3={counters.get('color_a3')}"
            )

            # Используем унифицированную функцию обновления полей
            # start=None т.к. автосинхронизация не трогает start поля
            changed, updated_fields_set = _assign_autofields(
                report=report,
                start=None,
                end=counters,
                only_empty=False,
                is_duplicate=is_duplicate,
                dup_position=dup_position,
            )

            # Обновляем метку последнего опроса
            report.inventory_last_ok = now
            updated_fields_set.add("inventory_last_ok")

            # Показываем итоговое состояние
            logger.info(
                f"  Итоговые значения report_id={report.id}: a4_bw_end={report.a4_bw_end}, a4_color_end={report.a4_color_end}, a3_bw_end={report.a3_bw_end}, a3_color_end={report.a3_color_end}"
            )
            logger.info(f"  Обновлено полей: {updated_fields_set}")

            if updated_fields_set:
                report.save(update_fields=list(updated_fields_set))

            # Пересчитываем total_prints для группы
            if changed:
                try:
                    recompute_group(report.month, report.serial_number, report.inventory_number)
                    report.refresh_from_db()
                    updated_reports.append(report)
                    logger.info(f"  Пересчитано total_prints для report_id={report.id}: {report.total_prints}")
                except Exception as e:
                    logger.error(f"  Ошибка пересчёта для report_id={report.id}: {e}")

        # Отправляем WebSocket уведомления для обновлённых записей
        for report in updated_reports:
            group_name = f"monthly_report_{report.month.year}_{report.month.month}"

            # Вычисляем информацию об аномалии
            from monthly_report.views import _annotate_anomalies_api

            anomaly_data = _annotate_anomalies_api([report], report.month, threshold=2000)
            anomaly_info = anomaly_data.get(report.id, {"is_anomaly": False, "has_history": False})

            message = {
                "type": "inventory_sync_update",
                "report_id": report.id,
                "a4_bw_end": report.a4_bw_end,
                "a4_color_end": report.a4_color_end,
                "a3_bw_end": report.a3_bw_end,
                "a3_color_end": report.a3_color_end,
                "total_prints": report.total_prints,
                "is_anomaly": anomaly_info["is_anomaly"],
                "anomaly_info": anomaly_info,
                "inventory_last_ok": report.inventory_last_ok.isoformat() if report.inventory_last_ok else None,
                "source": "inventory_auto_sync",
            }

            try:
                async_to_sync(channel_layer.group_send)(group_name, message)
                logger.info(f"  WebSocket отправлен в {group_name} для report_id={report.id}")
            except Exception as e:
                logger.error(f"  Ошибка отправки WebSocket: {e}")

        logger.info(f"sync_to_monthly_reports: обновлено {len(updated_reports)} записей")

    except Exception as e:
        logger.error(f"sync_to_monthly_reports: критическая ошибка: {e}", exc_info=True)


# ──────────────────────────────────────────────────────────────────────────────
# ПОЛНЫЙ ИНВЕНТАРЬ
# ──────────────────────────────────────────────────────────────────────────────


def run_inventory_for_printer(
    printer_id: int, xml_path: Optional[str] = None, triggered_by: str = "manual"
) -> Tuple[bool, str]:
    """
    Полный цикл инвентаризации с автоматическим выбором метода.
    Если у принтера есть правила веб-парсинга - используется WEB, иначе SNMP.

    Args:
        printer_id: ID принтера
        xml_path: Путь к XML файлу (опционально)
        triggered_by: 'manual' (ручной запуск) или 'daemon' (автоматический опрос)
    """
    start_time = timezone.now()
    printer = None
    temp_xml_path = None

    try:
        try:
            printer = Printer.objects.select_related("organization").get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer {printer_id} not found")
            return False, f"Printer {printer_id} not found"

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "inventory_updates",
            {"type": "inventory_start", "printer_id": printer.id, "triggered_by": triggered_by},
        )

        ip = printer.ip_address
        serial = printer.serial_number

        # ═══════════════════════════════════════════════════════════════
        # АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ МЕТОДА ОПРОСА
        # ═══════════════════════════════════════════════════════════════

        # 🔥 ПРОВЕРЯЕМ: есть ли правила веб-парсинга?
        web_rules = WebParsingRule.objects.filter(printer=printer)
        use_web_parsing = web_rules.exists()

        if use_web_parsing:
            # ───────────────────────────────────────────────────────────
            # ВЕБ-ПАРСИНГ
            # ───────────────────────────────────────────────────────────
            logger.info(f"🌐 Using WEB parsing for {ip} (found {web_rules.count()} rules)")

            # Выполняем веб-парсинг
            success, results, error_msg = execute_web_parsing(printer, list(web_rules))

            if not success:
                InventoryTask.objects.create(
                    printer=printer, status="FAILED", error_message=f"Web parsing: {error_msg}"
                )
                logger.error(f"Web parsing failed for {ip}: {error_msg}")
                return False, error_msg

            # Генерируем XML из результатов
            xml_content = export_to_xml(printer, results)

            # Сохраняем XML во временный файл для дальнейшей обработки
            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
                f.write(xml_content)
                temp_xml_path = f.name

            xml_path = temp_xml_path

            # Сохраняем XML экспорт для GLPI
            _save_xml_export(printer, xml_content)

            # Обновляем метод опроса
            if printer.polling_method != PollingMethod.WEB:
                printer.polling_method = PollingMethod.WEB
                printer.save(update_fields=["polling_method"])

        else:
            # ───────────────────────────────────────────────────────────
            # SNMP ОПРОС
            # ───────────────────────────────────────────────────────────
            logger.info(f"📡 Using SNMP for {ip} (no web rules found)")

            # Обновляем метод опроса
            if printer.polling_method != PollingMethod.SNMP:
                printer.polling_method = PollingMethod.SNMP
                printer.save(update_fields=["polling_method"])

            community = getattr(printer, "snmp_community", None) or "public"

            if not xml_path:
                # HTTP проверка (опционально)
                if getattr(settings, "HTTP_CHECK", True):
                    ok_check, err = send_device_get_request(ip)
                    if not ok_check:
                        logger.warning(f"HTTP check failed for {ip}: {err}")

                # Проверяем агент GLPI
                glpi_ok, glpi_msg = _validate_glpi_installation()
                if not glpi_ok:
                    InventoryTask.objects.create(printer=printer, status="FAILED", error_message=glpi_msg)
                    return False, glpi_msg

                disc_exe = _get_glpi_discovery_path()
                _cleanup_xml(ip)

                cmd = _build_glpi_command(disc_exe, ip, community)
                logger.info(f"Running GLPI discovery for {ip}")

                ok, out = run_glpi_command(cmd)
                if not ok:
                    error_msg = f"GLPI failed: {out}"
                    InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)
                    logger.error(f"GLPI failed for {ip}: {out}")
                    return False, error_msg

                xml_candidates = _possible_xml_paths(ip, prefer="inv")
                xml_path = None
                for candidate in xml_candidates:
                    if os.path.exists(candidate):
                        xml_path = candidate
                        logger.info(f"Found XML for {ip}: {xml_path}")
                        break

                if not xml_path:
                    msg = f"XML missing for {ip} after GLPI"
                    InventoryTask.objects.create(printer=printer, status="FAILED", error_message=msg)
                    logger.error(msg)
                    return False, msg

        # ═══════════════════════════════════════════════════════════════
        # ОБЩАЯ ОБРАБОТКА XML (одинакова для обоих методов)
        # ═══════════════════════════════════════════════════════════════

        data = xml_to_json(xml_path)

        if not data:
            error_msg = "XML parse error"
            InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)
            logger.error(f"XML parse error for {ip}")
            return False, error_msg

        # Проверка счётчиков
        page_counters = data.get("CONTENT", {}).get("DEVICE", {}).get("PAGECOUNTERS", {})
        if not page_counters or not any(
            page_counters.get(tag) for tag in ["TOTAL", "BW_A3", "BW_A4", "COLOR_A3", "COLOR_A4", "COLOR"]
        ):
            error_msg = "No valid page counters in XML"
            logger.warning(f"No valid page counters found for {ip}")
            InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)
            async_to_sync(channel_layer.group_send)(
                "inventory_updates",
                {
                    "type": "inventory_update",
                    "printer_id": printer.id,
                    "status": "FAILED",
                    "message": error_msg,
                    "triggered_by": triggered_by,
                },
            )
            return False, error_msg

        # Обновление MAC
        mac_address = extract_mac_address(data)
        if mac_address and not printer.mac_address:
            # Проверяем, не используется ли этот MAC другим АКТИВНЫМ принтером
            existing_printer = (
                Printer.objects.filter(mac_address=mac_address, is_active=True).exclude(id=printer.id).first()
            )
            if existing_printer:
                error_msg = (
                    f"MAC-адрес {mac_address} уже используется другим принтером "
                    f"(ID: {existing_printer.id}, IP: {existing_printer.ip_address}, "
                    f"Serial: {existing_printer.serial_number or 'N/A'}). "
                    f"Невозможно обновить MAC для текущего принтера."
                )
                logger.warning(f"MAC conflict for {ip}: {error_msg}")

                InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)

                async_to_sync(channel_layer.group_send)(
                    "inventory_updates",
                    {
                        "type": "inventory_update",
                        "printer_id": printer.id,
                        "status": "FAILED",
                        "message": error_msg,
                        "triggered_by": triggered_by,
                    },
                )

                return False, error_msg

            # MAC свободен, сохраняем
            try:
                printer.mac_address = mac_address
                printer.save(update_fields=["mac_address"])
                logger.info(f"Updated MAC address for {ip}: {mac_address}")
            except Exception as e:
                error_msg = f"Не удалось сохранить MAC-адрес: {str(e)}"
                logger.error(f"Error saving MAC for {ip}: {e}", exc_info=True)

                InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)

                async_to_sync(channel_layer.group_send)(
                    "inventory_updates",
                    {
                        "type": "inventory_update",
                        "printer_id": printer.id,
                        "status": "FAILED",
                        "message": error_msg,
                        "triggered_by": triggered_by,
                    },
                )

                return False, error_msg

        # Валидация
        valid, err, rule = validate_inventory(data, ip, serial, printer.mac_address)
        if not valid:
            # ═══════════════════════════════════════════════════════════════
            # ПОПЫТКА УМНОЙ ОБРАБОТКИ ЗАМЕНЫ ОБОРУДОВАНИЯ
            # Если серийник/MAC не совпадают, проверяем наличие в договорах
            # ═══════════════════════════════════════════════════════════════
            device_info = data.get("CONTENT", {}).get("DEVICE", {}).get("INFO", {})
            new_serial = (device_info.get("SERIAL") or "").strip()
            new_mac = extract_mac_address(data)

            replacement_handled = False
            if new_serial and new_serial != serial:
                logger.info(
                    f"Validation failed for {ip}: serial mismatch ({serial} -> {new_serial}). "
                    f"Attempting device replacement..."
                )

                success, target_printer, message = handle_device_replacement(
                    current_printer=printer, new_serial=new_serial, new_mac=new_mac, triggered_by=triggered_by
                )

                if success and target_printer:
                    # Замена успешна, продолжаем опрос с новым/обновлённым принтером
                    printer = target_printer
                    ip = printer.ip_address
                    serial = printer.serial_number
                    replacement_handled = True

                    logger.info(f"Device replacement handled: {message}")

                    # Перезапускаем валидацию для нового принтера
                    valid, err, rule = validate_inventory(data, ip, serial, printer.mac_address)

                    if not valid:
                        # Даже после замены валидация не прошла
                        error_msg = f"Validation failed after replacement: {err}"
                        InventoryTask.objects.create(printer=printer, status="VALIDATION_ERROR", error_message=err)
                        logger.error(f"Validation still failed for {ip} after replacement: {err}")
                        return False, error_msg
                else:
                    # Замена не удалась, логируем причину
                    logger.warning(f"Device replacement failed: {message}")

            if not valid and not replacement_handled:
                # Стандартная ошибка валидации (без успешной замены)
                error_msg = f"Validation failed: {err}"
                InventoryTask.objects.create(printer=printer, status="VALIDATION_ERROR", error_message=err)
                logger.error(f"Validation failed for {ip}: {err}")
                return False, error_msg

        # Извлечение счетчиков
        counters = extract_page_counters(data)

        # Историческая валидация
        try:
            historical_valid, historical_error, validation_rule = validate_against_history(printer, counters)
        except Exception as e:
            logger.error(f"Historical validation error for {ip}: {e}", exc_info=True)
            historical_valid = True
            historical_error = None

        if not historical_valid:
            task = InventoryTask.objects.create(
                printer=printer, status="HISTORICAL_INCONSISTENCY", error_message=historical_error, match_rule=rule
            )
            logger.warning(f"Historical validation failed for {ip}: {historical_error}")
            update_payload = {
                "type": "inventory_update",
                "printer_id": printer.id,
                "status": "HISTORICAL_INCONSISTENCY",
                "message": historical_error,
                "timestamp": int(task.task_timestamp.timestamp() * 1000),
                "triggered_by": triggered_by,
            }
            async_to_sync(channel_layer.group_send)("inventory_updates", update_payload)
            return False, f"Historical validation failed: {historical_error}"

        # Сохраняем данные
        task = InventoryTask.objects.create(printer=printer, status="SUCCESS", match_rule=rule)
        PageCounter.objects.create(task=task, **counters)

        # Обновляем последнее правило
        if rule:
            printer.last_match_rule = rule
            printer.save(update_fields=["last_match_rule"])

        # АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ С MONTHLY REPORT
        # Обновляем открытые месячные отчёты в реальном времени
        try:
            logger.info(
                f"run_inventory_for_printer: вызываем sync_to_monthly_reports для принтера {printer.id} (triggered_by={triggered_by})"
            )
            logger.info(
                f"  Счетчики для синхронизации: bw_a4={counters.get('bw_a4')}, color_a4={counters.get('color_a4')}, bw_a3={counters.get('bw_a3')}, color_a3={counters.get('color_a3')}"
            )
            sync_to_monthly_reports(printer, counters)
        except Exception as e:
            logger.error(f"Ошибка синхронизации с monthly_report: {e}", exc_info=True)
            # Не прерываем выполнение, просто логируем

        # WS-уведомление
        update_payload = {
            "type": "inventory_update",
            "printer_id": printer.id,
            "status": "SUCCESS",
            "match_rule": rule,
            "mac_address": printer.mac_address,  # Отправляем MAC (может быть обновлен)
            "bw_a3": counters.get("bw_a3"),
            "bw_a4": counters.get("bw_a4"),
            "color_a3": counters.get("color_a3"),
            "color_a4": counters.get("color_a4"),
            "total": counters.get("total_pages"),
            "drum_black": counters.get("drum_black"),
            "drum_cyan": counters.get("drum_cyan"),
            "drum_magenta": counters.get("drum_magenta"),
            "drum_yellow": counters.get("drum_yellow"),
            "toner_black": counters.get("toner_black"),
            "toner_cyan": counters.get("toner_cyan"),
            "toner_magenta": counters.get("toner_magenta"),
            "toner_yellow": counters.get("toner_yellow"),
            "fuser_kit": counters.get("fuser_kit"),
            "transfer_kit": counters.get("transfer_kit"),
            "waste_toner": counters.get("waste_toner"),
            "timestamp": int(task.task_timestamp.timestamp() * 1000),
            "triggered_by": triggered_by,
        }
        async_to_sync(channel_layer.group_send)("inventory_updates", update_payload)

        duration = (timezone.now() - start_time).total_seconds()
        method = "WEB" if use_web_parsing else "SNMP"
        logger.info(f"✓ Inventory completed for {ip} in {duration:.2f}s (method: {method})")

        return True, "Success"

    except Exception as e:
        ip_safe = getattr(printer, "ip_address", f"id={printer_id}") if printer else f"id={printer_id}"
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error in inventory for {ip_safe}: {e}", exc_info=True)

        try:
            if printer:
                InventoryTask.objects.create(printer=printer, status="FAILED", error_message=error_msg)

                # Отправляем WebSocket уведомление об ошибке
                try:
                    async_to_sync(channel_layer.group_send)(
                        "inventory_updates",
                        {
                            "type": "inventory_update",
                            "printer_id": printer.id,
                            "status": "FAILED",
                            "message": error_msg,
                            "triggered_by": triggered_by,
                        },
                    )
                except Exception as ws_error:
                    logger.error(f"Failed to send WebSocket notification: {ws_error}")

        except Exception as save_error:
            logger.error(f"Failed to save error task for {ip_safe}: {save_error}")

        return False, error_msg

    finally:
        # Очистка временного XML файла
        if temp_xml_path and os.path.exists(temp_xml_path):
            try:
                os.unlink(temp_xml_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp XML {temp_xml_path}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# DEPRECATED/СОВМЕСТИМОСТЬ
# ──────────────────────────────────────────────────────────────────────────────


def inventory_daemon():
    logger.warning("inventory_daemon() is deprecated. Use Celery tasks instead.")

    def worker():
        printers = Printer.objects.all()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(run_inventory_for_printer, p.id): p for p in printers}
            for future in concurrent.futures.as_completed(futures):
                printer = futures[future]
                try:
                    ok, msg = future.result()
                    logger.info(f"Inventory for {printer.ip_address}: {'OK' if ok else 'FAIL'} — {msg}")
                except Exception as e:
                    logger.error(f"Error polling {printer.ip_address}: {e}")

    threading.Thread(target=worker, daemon=True).start()


def start_scheduler():
    logger.warning("start_scheduler() is deprecated. Use Celery Beat instead.")
    return


# ──────────────────────────────────────────────────────────────────────────────
# СЕРВИСНЫЕ УТИЛИТЫ (УПРОЩЁННЫЕ)
# ──────────────────────────────────────────────────────────────────────────────


def get_printer_inventory_status(printer_id: int) -> dict:
    """
    Получает статус последней инвентаризации НАПРЯМУЮ ИЗ БД.
    """
    try:
        last_task = (
            InventoryTask.objects.filter(printer_id=printer_id, status="SUCCESS").order_by("-task_timestamp").first()
        )
        if last_task:
            counter = PageCounter.objects.filter(task=last_task).first()
            return {
                "task_id": last_task.id,
                "timestamp": last_task.task_timestamp.isoformat(),
                "status": last_task.status,
                "match_rule": last_task.match_rule,
                "counters": (
                    {
                        "bw_a4": getattr(counter, "bw_a4", None),
                        "color_a4": getattr(counter, "color_a4", None),
                        "bw_a3": getattr(counter, "bw_a3", None),
                        "color_a3": getattr(counter, "color_a3", None),
                        "total_pages": getattr(counter, "total_pages", None),
                        "drum_black": getattr(counter, "drum_black", ""),
                        "drum_cyan": getattr(counter, "drum_cyan", ""),
                        "drum_magenta": getattr(counter, "drum_magenta", ""),
                        "drum_yellow": getattr(counter, "drum_yellow", ""),
                        "toner_black": getattr(counter, "toner_black", ""),
                        "toner_cyan": getattr(counter, "toner_cyan", ""),
                        "toner_magenta": getattr(counter, "toner_magenta", ""),
                        "toner_yellow": getattr(counter, "toner_yellow", ""),
                        "fuser_kit": getattr(counter, "fuser_kit", ""),
                        "transfer_kit": getattr(counter, "transfer_kit", ""),
                        "waste_toner": getattr(counter, "waste_toner", ""),
                    }
                    if counter
                    else {}
                ),
                "is_fresh": False,
            }
    except Exception as e:
        logger.error(f"Error getting inventory status for printer {printer_id}: {e}")

    return {
        "task_id": None,
        "timestamp": None,
        "status": "NEVER_RUN",
        "match_rule": None,
        "counters": {},
        "is_fresh": False,
    }


def get_glpi_info() -> dict:
    """Диагностика конфигурации GLPI Agent."""
    try:
        disc_exe = _get_glpi_discovery_path()
        _, inv_exe = _get_glpi_paths()
        glpi_ok, glpi_msg = _validate_glpi_installation()

        return {
            "platform": PLATFORM,
            "glpi_path": getattr(settings, "GLPI_PATH", ""),
            "discovery_executable": disc_exe,
            "inventory_executable": inv_exe,
            "discovery_exists": os.path.exists(disc_exe),
            "inventory_exists": os.path.exists(inv_exe),
            "installation_valid": glpi_ok,
            "installation_message": glpi_msg,
            "output_directory": OUTPUT_DIR,
            "use_sudo": getattr(settings, "GLPI_USE_SUDO", False) if PLATFORM in ("linux", "darwin") else None,
            "glpi_user": getattr(settings, "GLPI_USER", "") if PLATFORM in ("linux", "darwin") else None,
            "note": "Only glpi-netdiscovery with -i flag is used (auto discovery+inventory)",
        }
    except Exception as e:
        return {"platform": PLATFORM, "error": str(e), "installation_valid": False}
