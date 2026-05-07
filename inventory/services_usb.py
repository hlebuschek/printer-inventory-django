"""Обработка readings от USB-агентов: дедупликация, валидация, привязка к ContractDevice."""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from dateutil import parser as dateparser
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from contracts.models import ContractDevice
from .models import (
    ConnectionType,
    DataSource,
    InventoryTask,
    MatchRule,
    PageCounter,
    PollingMethod,
    Printer,
    USBAgent,
)
from .utils import validate_against_history

logger = logging.getLogger(__name__)

REPLAY_WINDOW_HOURS = 72
DEDUP_TTL_SECONDS = REPLAY_WINDOW_HOURS * 3600
USB_PLACEHOLDER_IP = "0.0.0.0"
# Допустимый перекос часов на агенте (защищает dedup-окно от manipulation
# через timestamp в будущем — иначе можно «застолбить» dedup-ключ на 72ч вперёд).
FUTURE_CLOCK_SKEW_MINUTES = 5

COUNTER_KEYS = ("total_pages", "bw_a4", "color_a4", "bw_a3", "color_a3")


def hash_token(plaintext: str) -> str:
    """SHA-256 hex для хранения токена в БД. Plaintext отдаётся только агенту."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


class USBReadingError(Exception):
    """Бизнес-ошибка обработки reading'а — текст пойдёт агенту в ответ."""


def register_or_get_agent(registration_key: str, expected_key: str, agent_id: str, hostname: str, agent_version: str):
    """
    Регистрирует или возвращает существующий USBAgent.
    Возвращает (agent, plaintext_token): plaintext_token — None для существующих агентов
    (мы не храним plaintext в БД), новый — только для свежесозданных.
    """
    if not expected_key:
        raise USBReadingError("server registration key not configured")
    # constant-time сравнение master-key для защиты от timing-attack
    if not hmac.compare_digest(registration_key, expected_key):
        raise USBReadingError("invalid registration key")
    if not agent_id:
        raise USBReadingError("agent_id is required")

    try:
        agent = USBAgent.objects.get(agent_id=agent_id)
    except USBAgent.DoesNotExist:
        plaintext = secrets.token_hex(32)
        agent = USBAgent.objects.create(
            agent_id=agent_id,
            token_hash=hash_token(plaintext),
            hostname=hostname or "",
            agent_version=agent_version or "",
            is_active=True,
        )
        return agent, plaintext

    # Существующий агент: ротация токена при повторной регистрации
    # (агент потерял настройки или вернулся с master key)
    if not agent.is_active:
        raise USBReadingError("agent is deactivated")

    plaintext = secrets.token_hex(32)
    agent.token_hash = hash_token(plaintext)
    update_fields = ["token_hash"]
    if hostname and agent.hostname != hostname:
        agent.hostname = hostname
        update_fields.append("hostname")
    if agent_version and agent.agent_version != agent_version:
        agent.agent_version = agent_version
        update_fields.append("agent_version")
    agent.save(update_fields=update_fields)
    return agent, plaintext


def _parse_timestamp(value):
    if not value:
        raise USBReadingError("timestamp is required")
    try:
        ts = dateparser.isoparse(value)
    except (ValueError, TypeError):
        raise USBReadingError(f"invalid timestamp: {value!r}")
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone.utc)
    return ts


def _extract_counters(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in COUNTER_KEYS:
        val = raw.get(key)
        if val is None:
            continue
        try:
            out[key] = int(val)
        except (TypeError, ValueError):
            raise USBReadingError(f"counter {key!r} is not an integer: {val!r}")
    return out


def _resolve_printer(serial: str, contract_device, device_instance_id: str, model_text: str) -> Printer:
    """Найти/создать Printer для USB-reading'а. Поднимает USBReadingError при конфликте.

    Должен вызываться внутри transaction.atomic(): использует select_for_update()
    + partial UniqueConstraint(unique_active_usb_serial) для защиты от race
    при одновременных reading'ах от одного агента.
    """
    # of=("self",) — блокируем только Printer, не nullable FK (organization),
    # иначе Postgres ругается "FOR UPDATE на NULL-стороне OUTER JOIN".
    existing = (
        Printer.objects.select_related("organization")
        .filter(serial_number__iexact=serial, is_active=True)
        .select_for_update(of=("self",))
        .first()
    )
    if existing is not None:
        if existing.polling_method != PollingMethod.USB_API:
            raise USBReadingError(
                f"S/N {serial} конфликтует с сетевым принтером (polling_method="
                f"{existing.polling_method}); USB-опрос отклонён"
            )
        # подтягиваем usb_identifier, если его не было
        if device_instance_id and existing.usb_identifier != device_instance_id:
            existing.usb_identifier = device_instance_id
            existing.save(update_fields=["usb_identifier"])
        return existing

    # Принтера нет — авто-создание из ContractDevice
    printer = Printer.objects.create(
        ip_address=USB_PLACEHOLDER_IP,
        serial_number=serial,
        model=model_text or "",
        device_model=contract_device.model,
        snmp_community="",
        organization=contract_device.organization,
        polling_method=PollingMethod.USB_API,
        connection_type=ConnectionType.USB,
        usb_identifier=device_instance_id or "",
        is_active=True,
    )
    # связываем ContractDevice
    if contract_device.printer_id != printer.id:
        contract_device.printer = printer
        contract_device.save(update_fields=["printer"])
    logger.info("USB: auto-created Printer id=%s S/N=%s org=%s", printer.id, serial, contract_device.organization_id)
    return printer


def _ws_notify(printer: Printer, task: InventoryTask, counters: dict, reading_ts):
    """Отправляет WS-уведомление только для свежих readings (last hour)."""
    if (timezone.now() - reading_ts) > timedelta(hours=1):
        return
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            "inventory_updates",
            {
                "type": "inventory_update",
                "printer_id": printer.id,
                "status": "SUCCESS",
                "match_rule": MatchRule.SN_ONLY,
                "data_source": DataSource.USB_AGENT,
                "bw_a3": counters.get("bw_a3"),
                "bw_a4": counters.get("bw_a4"),
                "color_a3": counters.get("color_a3"),
                "color_a4": counters.get("color_a4"),
                "total": counters.get("total_pages"),
                "timestamp": int(task.task_timestamp.timestamp() * 1000),
                "triggered_by": "usb_agent",
            },
        )
    except Exception as e:  # pragma: no cover — WS-сбой не должен ломать reading
        logger.warning("USB: WS notify failed: %s", e)


def process_usb_reading(agent: USBAgent, reading: dict) -> dict:
    """
    Обрабатывает один reading от USB-агента.
    Возвращает dict, который кладётся в массив `results` ответа.
    """
    serial_block = reading.get("serial_number") or {}
    serial = (serial_block.get("value") or "").strip()
    timestamp_raw = reading.get("timestamp")
    counters_raw = reading.get("counters") or {}
    device_instance_id = (reading.get("device_instance_id") or "").strip()
    model_text = (reading.get("model") or "").strip()

    base = {"serial_number": serial, "status": "error"}

    if not serial:
        base["error"] = "serial_number is empty"
        return base

    # 1. timestamp + replay-окно 72ч + защита от future-timestamp
    try:
        reading_ts = _parse_timestamp(timestamp_raw)
    except USBReadingError as e:
        base["error"] = str(e)
        return base

    now = timezone.now()
    if (now - reading_ts) > timedelta(hours=REPLAY_WINDOW_HOURS):
        base["error"] = f"reading older than {REPLAY_WINDOW_HOURS}h replay window"
        return base
    if (reading_ts - now) > timedelta(minutes=FUTURE_CLOCK_SKEW_MINUTES):
        base["error"] = f"reading timestamp is in the future (clock skew > {FUTURE_CLOCK_SKEW_MINUTES} min)"
        return base

    # 2. дедупликация (serial + timestamp), Redis cache TTL=72h
    dedup_key = f"usb_dedup:{serial}:{timestamp_raw}"
    cached_task_id = cache.get(dedup_key)
    if cached_task_id:
        return {"serial_number": serial, "status": "duplicate", "task_id": cached_task_id}

    # 3. парсинг счётчиков
    try:
        counters = _extract_counters(counters_raw)
    except USBReadingError as e:
        base["error"] = str(e)
        return base
    if not counters:
        base["error"] = "no counters provided"
        return base

    # 4. поиск ContractDevice по серийнику
    contract_device = (
        ContractDevice.objects.select_related("organization", "model").filter(serial_number__iexact=serial).first()
    )

    try:
        with transaction.atomic():
            if contract_device is None:
                # есть ли уже USB-принтер с таким S/N (без CD) — переиспользуем
                printer = Printer.objects.filter(
                    serial_number__iexact=serial,
                    is_active=True,
                    polling_method=PollingMethod.USB_API,
                ).first()
                if printer is None:
                    raise USBReadingError(
                        f"S/N {serial} не найден ни в contracts, ни среди USB-принтеров; "
                        f"добавьте устройство в /contracts/"
                    )
            else:
                printer = _resolve_printer(serial, contract_device, device_instance_id, model_text)

            # 5. историческая валидация
            try:
                ok, err, _rule = validate_against_history(printer, counters)
            except Exception as e:
                logger.error("USB: validate_against_history failed for %s: %s", serial, e, exc_info=True)
                ok, err = True, None

            if not ok:
                task = InventoryTask.objects.create(
                    printer=printer,
                    status="HISTORICAL_INCONSISTENCY",
                    error_message=err,
                    match_rule=MatchRule.SN_ONLY,
                    data_source=DataSource.USB_AGENT,
                    agent_id=agent.agent_id,
                )
                cache.set(dedup_key, task.id, DEDUP_TTL_SECONDS)
                return {
                    "serial_number": serial,
                    "status": "validation_error",
                    "task_id": task.id,
                    "error": err,
                }

            # 6. сохраняем
            task = InventoryTask.objects.create(
                printer=printer,
                status="SUCCESS",
                match_rule=MatchRule.SN_ONLY,
                data_source=DataSource.USB_AGENT,
                agent_id=agent.agent_id,
            )
            PageCounter.objects.create(task=task, **counters)
            cache.set(dedup_key, task.id, DEDUP_TTL_SECONDS)
    except USBReadingError as e:
        base["error"] = str(e)
        return base

    _ws_notify(printer, task, counters, reading_ts)
    return {"serial_number": serial, "status": "success", "task_id": task.id}
