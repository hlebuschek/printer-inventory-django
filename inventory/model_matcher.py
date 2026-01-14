"""
Утилиты для работы с моделями принтеров: извлечение из XML, fuzzy matching в справочнике.
"""

import re
import logging
from difflib import SequenceMatcher
from typing import Optional, Tuple, List, Dict
import xml.etree.ElementTree as ET

from contracts.models import DeviceModel, Manufacturer

logger = logging.getLogger(__name__)


# ─── Нормализация названий ─────────────────────────────────────────────────

MANUFACTURER_ALIASES = {
    'hp': ['hp', 'hewlett-packard', 'hewlett packard', 'hp inc', 'hp inc.'],
    'canon': ['canon'],
    'epson': ['epson', 'seiko epson'],
    'ricoh': ['ricoh'],
    'kyocera': ['kyocera', 'kyocera mita'],
    'brother': ['brother'],
    'samsung': ['samsung'],
    'xerox': ['xerox'],
    'konica': ['konica', 'konica minolta', 'konica-minolta'],
    'sharp': ['sharp'],
    'oki': ['oki', 'okidata'],
    'dell': ['dell'],
    'lexmark': ['lexmark'],
    'toshiba': ['toshiba', 'toshiba tec'],
}

# Суффиксы моделей, которые можно игнорировать при сравнении
MODEL_SUFFIXES_TO_IGNORE = [
    'mfp', 'mf', 'multifunction', 'adf', 'duplex', 'network',
    'wireless', 'wifi', 'usb', 'ethernet', 'color', 'mono',
    'series', 'plus', 'pro', 'enterprise', 'office',
    'n', 'dn', 'nf', 'dnf', 'fn', 'df', 'dw', 'ne',  # HP суффиксы
    'a', 'b', 'c', 'd', 'e', 'f',  # одинарные буквы
]


def normalize_manufacturer_name(name: str) -> str:
    """
    Нормализует название производителя.
    Например: "Hewlett-Packard" → "hp"
    """
    if not name:
        return ''

    name_lower = name.strip().lower()

    # Ищем в алиасах
    for canonical, aliases in MANUFACTURER_ALIASES.items():
        if name_lower in aliases:
            return canonical

    return name_lower


def normalize_model_name(model: str, manufacturer: str = '') -> str:
    """
    Нормализует название модели для fuzzy matching.

    - Убирает производителя из начала строки
    - Приводит к lowercase
    - Убирает лишние пробелы и спецсимволы
    - Убирает типовые суффиксы (MFP, ADF, и т.д.)

    Примеры:
    - "HP LaserJet Pro M404dn" → "laserjet pro m404"
    - "Ricoh MP C2004" → "mp c2004"
    - "Kyocera TASKalfa 3252ci MFP" → "taskalfa 3252ci"
    """
    if not model:
        return ''

    # Lowercase
    result = model.strip().lower()

    # Убираем производителя из начала
    if manufacturer:
        mfr_norm = normalize_manufacturer_name(manufacturer)
        # Убираем все варианты алиасов
        for alias in MANUFACTURER_ALIASES.get(mfr_norm, [mfr_norm]):
            if result.startswith(alias):
                result = result[len(alias):].strip()

    # Убираем спецсимволы, оставляем буквы, цифры, пробелы
    result = re.sub(r'[^\w\s]', ' ', result)

    # Убираем множественные пробелы
    result = re.sub(r'\s+', ' ', result).strip()

    # Убираем типовые суффиксы в конце
    words = result.split()
    filtered_words = []

    for word in words:
        # Пропускаем одинарные буквы в конце
        if len(word) == 1 and word.isalpha() and filtered_words:
            continue
        # Пропускаем суффиксы
        if word in MODEL_SUFFIXES_TO_IGNORE:
            continue
        filtered_words.append(word)

    return ' '.join(filtered_words)


# ─── Извлечение данных из XML ──────────────────────────────────────────────

def extract_model_from_xml(xml_path: str) -> Optional[str]:
    """
    Извлекает модель из XML файла SNMP опроса.
    Ищет в <INFO><MODEL> или в <INFO><COMMENTS>.

    Примеры:
    - <MODEL>HP LaserJet M1522nf MFP</MODEL> → "HP LaserJet M1522nf MFP"
    - <COMMENTS>...PID:HP LaserJet M1522nf MFP</COMMENTS> → "HP LaserJet M1522nf MFP"
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Поиск <MODEL>
        for elem in root.iter('MODEL'):
            value = (elem.text or '').strip()
            if value:
                return value

        # Поиск в <COMMENTS> (HP часто пишет там: PID:...)
        for elem in root.iter('COMMENTS'):
            comments = (elem.text or '').strip()
            # Ищем паттерн "PID:..."
            match = re.search(r'PID:\s*([^,\n]+)', comments)
            if match:
                return match.group(1).strip()

        return None
    except Exception as e:
        logger.error(f"Error extracting model from XML {xml_path}: {e}")
        return None


def extract_manufacturer_from_xml(xml_path: str) -> Optional[str]:
    """
    Извлекает производителя из XML файла SNMP опроса.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for elem in root.iter('MANUFACTURER'):
            value = (elem.text or '').strip()
            if value:
                return value

        return None
    except Exception as e:
        logger.error(f"Error extracting manufacturer from XML {xml_path}: {e}")
        return None


def extract_serial_from_xml(xml_path: str) -> Optional[str]:
    """
    Извлекает серийный номер из XML файла SNMP опроса.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for elem in root.iter('SERIAL'):
            value = (elem.text or '').strip()
            if value:
                return value

        # Также ищем в <COMMENTS> (HP часто пишет: SN:...)
        for elem in root.iter('COMMENTS'):
            comments = (elem.text or '').strip()
            match = re.search(r'SN:\s*([^,\n]+)', comments)
            if match:
                return match.group(1).strip()

        return None
    except Exception as e:
        logger.error(f"Error extracting serial from XML {xml_path}: {e}")
        return None


# ─── Fuzzy matching моделей ────────────────────────────────────────────────

def fuzzy_match_model(
    model_text: str,
    manufacturer_text: Optional[str] = None,
    threshold: float = 0.75,
    top_n: int = 5
) -> List[Tuple[DeviceModel, float]]:
    """
    Нечеткий поиск модели в справочнике DeviceModel.

    Args:
        model_text: Текст модели из SNMP (например, "HP LaserJet M1522nf MFP")
        manufacturer_text: Текст производителя из SNMP (опционально)
        threshold: Минимальный порог схожести (0.0 - 1.0)
        top_n: Сколько лучших совпадений вернуть

    Returns:
        Список кортежей (DeviceModel, score) отсортированный по убыванию score
    """
    if not model_text:
        return []

    # Нормализуем входную модель
    model_normalized = normalize_model_name(model_text, manufacturer_text or '')

    # Нормализуем название производителя
    mfr_normalized = normalize_manufacturer_name(manufacturer_text) if manufacturer_text else None

    logger.debug(f"Fuzzy matching: '{model_text}' (normalized: '{model_normalized}')")
    if mfr_normalized:
        logger.debug(f"Manufacturer: '{manufacturer_text}' (normalized: '{mfr_normalized}')")

    # Получаем все модели из справочника
    queryset = DeviceModel.objects.select_related('manufacturer').filter(device_type='printer')

    # Если знаем производителя - фильтруем
    if mfr_normalized:
        # Ищем производителя в алиасах
        matching_manufacturers = []
        for mfr in Manufacturer.objects.all():
            if normalize_manufacturer_name(mfr.name) == mfr_normalized:
                matching_manufacturers.append(mfr.id)

        if matching_manufacturers:
            queryset = queryset.filter(manufacturer_id__in=matching_manufacturers)
            logger.debug(f"Filtered to {queryset.count()} models from matching manufacturers")

    # Вычисляем схожесть для каждой модели
    matches = []

    for device_model in queryset:
        # Полное название модели
        full_name = f"{device_model.manufacturer.name} {device_model.name}"
        full_name_normalized = normalize_model_name(full_name)

        # Только название модели (без производителя)
        model_only_normalized = normalize_model_name(device_model.name)

        # Вычисляем схожесть
        score_full = SequenceMatcher(None, model_normalized, full_name_normalized).ratio()
        score_model_only = SequenceMatcher(None, model_normalized, model_only_normalized).ratio()

        # Берем лучший результат
        score = max(score_full, score_model_only)

        # Бонус если производитель совпадает
        if mfr_normalized:
            if normalize_manufacturer_name(device_model.manufacturer.name) == mfr_normalized:
                score *= 1.1  # +10% бонус

        # Ограничиваем score в пределах [0, 1]
        score = min(score, 1.0)

        if score >= threshold:
            matches.append((device_model, score))
            logger.debug(f"  {device_model} → score={score:.2f}")

    # Сортируем по убыванию score
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches[:top_n]


def find_best_model_match(
    model_text: str,
    manufacturer_text: Optional[str] = None,
    threshold: float = 0.75
) -> Optional[DeviceModel]:
    """
    Находит лучшее совпадение модели в справочнике.

    Returns:
        DeviceModel или None если совпадение не найдено
    """
    matches = fuzzy_match_model(model_text, manufacturer_text, threshold, top_n=1)

    if matches:
        device_model, score = matches[0]
        logger.info(f"Best match for '{model_text}': {device_model} (score={score:.2f})")
        return device_model

    logger.warning(f"No match found for '{model_text}' (threshold={threshold})")
    return None


# ─── Извлечение данных из XML и поиск модели ───────────────────────────────

def extract_and_match_model(xml_path: str, threshold: float = 0.75) -> Tuple[Optional[str], Optional[str], Optional[DeviceModel]]:
    """
    Извлекает модель и производителя из XML, ищет совпадение в справочнике.

    Returns:
        (model_text, manufacturer_text, device_model)
        - model_text: Текстовое название модели из XML
        - manufacturer_text: Текстовое название производителя из XML
        - device_model: Найденная модель из справочника (или None)
    """
    model_text = extract_model_from_xml(xml_path)
    manufacturer_text = extract_manufacturer_from_xml(xml_path)

    if not model_text:
        return None, manufacturer_text, None

    device_model = find_best_model_match(model_text, manufacturer_text, threshold)

    return model_text, manufacturer_text, device_model
