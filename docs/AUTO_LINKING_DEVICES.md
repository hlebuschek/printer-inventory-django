# Автоматическое связывание устройств между inventory и contracts

## Обзор

Система автоматически связывает устройства между двумя приложениями:
- **inventory.Printer** - принтеры для опроса по SNMP/WebParsing
- **contracts.ContractDevice** - устройства в договорах обслуживания

Связывание происходит по **серийному номеру** устройства.

## Зачем это нужно?

**Проблема:** Данные о принтерах хранятся в двух местах:
- В `inventory` — для технического опроса (IP, SNMP, счётчики)
- В `contracts` — для бизнес-процессов (организация, договор, модель)

**Решение:** Автоматическое связывание объединяет эти данные:
```
ContractDevice (организация, договор) ←→ Printer (IP, опрос)
           ↓ связь через serial_number ↓
```

**Результат:**
- ✅ Можно опрашивать принтеры из договоров
- ✅ Данные счётчиков доступны в monthly_report
- ✅ Синхронизация происходит автоматически

## Как это работает?

### 1. Автоматически при добавлении (Django Signals)

#### При создании ContractDevice
Когда добавляется новое устройство в contracts:

```python
# Создаём устройство с серийником
device = ContractDevice.objects.create(
    serial_number="ABC12345",
    organization=org,
    ...
)
# ← Срабатывает сигнал pre_save
# ← Автоматически ищется Printer с serial_number="ABC12345"
# ← Если найден, устанавливается device.printer = printer
```

**Код:** `contracts/signals.py:autolink_printer()`

#### При создании Printer
Когда добавляется новый принтер в inventory:

```python
# Создаём принтер с серийником
printer = Printer.objects.create(
    serial_number="ABC12345",
    ip_address="192.168.1.100",
    ...
)
# ← Срабатывает сигнал post_save
# ← Автоматически ищутся ContractDevice с serial_number="ABC12345"
# ← Если найдены, для них устанавливается printer = созданный принтер
```

**Код:** `contracts/signals.py:link_printer_on_save()`

### 2. Периодически (Celery Beat)

Раз в день в **04:00** запускается задача `auto_link_devices_task`:
- Находит все несвязанные устройства (ContractDevice без printer_id)
- Ищет для каждого соответствующий принтер по serial_number
- Устанавливает связи
- Логирует результаты

**Конфигурация:** `printer_inventory/settings.py:CELERY_BEAT_SCHEDULE`

```python
'auto-link-devices-daily': {
    'task': 'contracts.tasks.auto_link_devices_task',
    'schedule': crontab(hour=4, minute=0),  # 04:00 каждый день
}
```

**Код:** `contracts/tasks.py:auto_link_devices_task()`

### 3. Вручную (Management команда)

Администратор может запустить связывание вручную:

```bash
# Анализ без изменений
python manage.py link_devices_by_serial --dry-run

# Реальное связывание
python manage.py link_devices_by_serial

# С детальным выводом
python manage.py link_devices_by_serial --show-details

# Принудительное пересвязывание всех устройств
python manage.py link_devices_by_serial --force-relink
```

**Код:** `contracts/management/commands/link_devices_by_serial.py`

## Логика связывания

### Простой случай
```
ContractDevice (SN: ABC123, printer: null)
              ↓ поиск
Printer (SN: ABC123, IP: 192.168.1.100)
              ↓ связывание
ContractDevice.printer = Printer ✓
```

### Множественные принтеры (дубли)
```
ContractDevice (SN: ABC123, printer: null)
              ↓ поиск
Printer 1 (SN: ABC123, IP: 192.168.1.100)
Printer 2 (SN: ABC123, IP: 192.168.1.101)
              ↓ выбор
Выбирается первый найденный (Printer 1)
⚠️ Логируется WARNING о дублях
```

### Конфликт связей
```
ContractDevice 1 (SN: ABC123, printer: null)
ContractDevice 2 (SN: ABC123, printer: null)
              ↓ поиск
Printer (SN: ABC123, IP: 192.168.1.100)
              ↓ проверка
Printer уже занят устройством 2
              ↓ результат
Связывание пропускается для устройства 1
⚠️ Логируется конфликт
```

## Обработка проблемных ситуаций

### Дубли серийных номеров

**Проблема:** Несколько принтеров с одинаковым серийником в inventory.

**Поведение:**
- Используется первый найденный принтер
- Логируется WARNING
- В команде `link_devices_by_serial` показывается в разделе "ПРОБЛЕМЫ С ДУБЛЯМИ"

**Решение:**
1. Найти дубли: `python manage.py link_devices_by_serial --dry-run`
2. Проверить принтеры вручную
3. Удалить/исправить лишние записи

### Принтер не найден

**Проблема:** В contracts есть устройство, но нет соответствующего принтера в inventory.

**Поведение:**
- Связывание пропускается
- Логируется DEBUG сообщение
- Статистика: `not_found += 1`

**Решение:**
- Добавить принтер в inventory с правильным серийным номером
- При следующем связывании (следующий день или вручную) устройство будет связано

### Конфликт связей

**Проблема:** Принтер уже связан с другим устройством.

**Поведение:**
- Связывание пропускается (если не используется --force-relink)
- Логируется WARNING
- Статистика: `conflicts += 1`

**Решение:**
1. Проверить дубли серийников в contracts
2. Решить какое устройство должно быть связано
3. При необходимости использовать `--force-relink`

## Логирование

Все операции связывания логируются в `logs/django.log`:

### При автоматическом связывании через signals:
```
[INFO] Устройство с серийником ABC123 автоматически связано с принтером ID:42(192.168.1.100)
[WARNING] Найдено 2 принтеров с серийником ABC123, используем первый (ID:42)
[WARNING] Принтер ID:42 уже связан с устройством ID:10, пропускаем связывание для устройства ABC123
```

### При периодической задаче (04:00):
```
[INFO] ================================================================================
[INFO] ЗАПУСК АВТОМАТИЧЕСКОГО СВЯЗЫВАНИЯ УСТРОЙСТВ
[INFO] Task ID: abc-123-def
[INFO] Timestamp: 2025-12-14 04:00:00
[INFO] ================================================================================
[INFO] Запуск автоматического связывания устройств...
[INFO] Найдено 15 несвязанных устройств
[INFO] Связано: устройство ID:123 (Офис №5) -> принтер ID:42(192.168.1.100)
[INFO] ...
[INFO] Автоматическое связывание завершено: связано 12/15, не найдено 3, конфликтов 0, ошибок 0
[INFO] ================================================================================
[INFO] АВТОМАТИЧЕСКОЕ СВЯЗЫВАНИЕ ЗАВЕРШЕНО
[INFO] Всего обработано: 15
[INFO] Успешно связано: 12
[INFO] Принтер не найден: 3
[INFO] ================================================================================
```

## API для программного использования

### Связывание по серийному номеру

```python
from contracts.services_linking import link_device_by_serial

# Связать устройство с принтером по серийнику
success, message = link_device_by_serial("ABC12345")

if success:
    print(f"Успешно: {message}")
else:
    print(f"Ошибка: {message}")

# С принудительным пересвязыванием
success, message = link_device_by_serial("ABC12345", force_relink=True)
```

### Массовое связывание

```python
from contracts.services_linking import link_all_unlinked_devices

# Связать все несвязанные устройства
stats = link_all_unlinked_devices()

print(f"Обработано: {stats['total_devices']}")
print(f"Связано: {stats['linked']}")
print(f"Не найдено: {stats['not_found']}")
```

### Поиск устройств для принтера

```python
from contracts.services_linking import find_matching_devices_for_printer

# Найти устройства для принтера
devices = find_matching_devices_for_printer(printer_id=42)

for device in devices:
    print(f"Устройство ID:{device['device_id']}")
    print(f"  Организация: {device['organization']}")
    print(f"  Связано: {device['is_linked']}")
```

## Расписание периодических задач

| Время | Задача | Описание |
|-------|--------|----------|
| 00:00 каждый час | `inventory_daemon_task` | Опрос принтеров |
| 03:00 каждый день | `cleanup_old_inventory_data` | Очистка старых данных |
| **04:00 каждый день** | **`auto_link_devices_task`** | **Связывание устройств** |

Задача связывания запускается **после очистки данных**, чтобы работать с актуальными данными.

## Отключение автоматического связывания

### Отключить signals (при добавлении)

Если нужно временно отключить автоматическое связывание при создании:

```python
# В contracts/signals.py закомментировать:
# @receiver(pre_save, sender=ContractDevice)
# @receiver(post_save, sender=Printer)
```

**Не рекомендуется** - лучше оставить включенным.

### Отключить периодическую задачу

Удалить из `CELERY_BEAT_SCHEDULE` в `settings.py`:

```python
# Закомментировать эту секцию:
# 'auto-link-devices-daily': {
#     'task': 'contracts.tasks.auto_link_devices_task',
#     ...
# },
```

### Запустить задачу вручную

Вместо периодического запуска можно запускать вручную:

```bash
# Через management команду
python manage.py link_devices_by_serial

# Через Celery task напрямую
python manage.py shell
>>> from contracts.tasks import auto_link_devices_task
>>> auto_link_devices_task.delay()
```

## Мониторинг

### Проверить статус связей

```bash
# Анализ без изменений
python manage.py link_devices_by_serial --dry-run
```

Покажет:
- Сколько устройств несвязано
- Дубли серийников
- Конфликты
- Рекомендации

### Проверить логи

```bash
# Логи периодической задачи
grep "АВТОМАТИЧЕСКОЕ СВЯЗЫВАНИЕ" logs/django.log | tail -20

# Логи сигналов
grep "автоматически связано" logs/django.log | tail -20

# Проблемы
grep -E "WARNING|ERROR" logs/django.log | grep -i "связ" | tail -20
```

### Celery мониторинг

```bash
# Проверить что задача зарегистрирована
celery -A printer_inventory inspect registered | grep auto_link

# Проверить расписание
celery -A printer_inventory inspect scheduled

# Статистика задач
celery -A printer_inventory inspect stats
```

## Производительность

**Оценка времени выполнения:**
- 100 несвязанных устройств: ~2-3 секунды
- 1000 несвязанных устройств: ~15-20 секунд
- 5000 несвязанных устройств: ~60-90 секунд

**Оптимизации:**
- Используется `select_related()` для минимизации SQL запросов
- Предварительная загрузка всех принтеров в словарь
- Транзакция для пакетного сохранения

## Примеры использования

### Сценарий 1: Добавление нового договора

1. Администратор получает договор на обслуживание 50 принтеров
2. Импортирует устройства в contracts из Excel (с серийниками)
3. **Автоматически:** При создании каждого ContractDevice срабатывает signal
4. **Результат:** Устройства с существующими принтерами сразу связаны
5. **Для остальных:** Принтеры будут связаны при добавлении в inventory

### Сценарий 2: Массовое добавление принтеров

1. Инженер добавляет 100 новых принтеров в inventory (с серийниками)
2. **Автоматически:** При создании каждого Printer срабатывает signal
3. **Результат:** Принтеры связываются с существующими устройствами в contracts

### Сценарий 3: Ежедневная синхронизация

1. В течение дня добавляются устройства и принтеры
2. Некоторые связываются автоматически через signals
3. В **04:00** запускается периодическая задача
4. **Результат:** Все пропущенные связи устанавливаются

## Связанные файлы

- `contracts/signals.py` - Django signals для автоматического связывания
- `contracts/tasks.py` - Celery задачи
- `contracts/services_linking.py` - Сервисный модуль с логикой
- `contracts/management/commands/link_devices_by_serial.py` - Management команда
- `printer_inventory/settings.py` - Конфигурация Celery Beat

## История изменений

### 13 декабря 2025 - Автоматизация связывания

**Было:**
- Связывание только через management команду вручную
- Signal при создании ContractDevice (простая логика)

**Стало:**
- ✅ Signal при создании ContractDevice (улучшенная логика + логирование)
- ✅ Signal при создании Printer (новое)
- ✅ Периодическая задача Celery (04:00 каждый день)
- ✅ Сервисный модуль для переиспользования
- ✅ Детальное логирование
- ✅ Обработка конфликтов и дублей

**Автор:** Claude Code Assistant
