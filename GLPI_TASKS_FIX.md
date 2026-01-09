# Исправление проблемы с застрявшими GLPI задачами в Celery

## Проблема

Задачи `check_all_devices_in_glpi` застревают в очереди `low_priority` и не выполняются, несмотря на то, что:
- Workers запущены и работают
- Команда `python manage.py sync_glpi` выполняется успешно
- Время выполнения (ETA) задач уже прошло

## Причина

В `printer_inventory/celery.py` задача `check_all_devices_in_glpi` не была явно импортирована, из-за чего workers не могли её обработать. Были импортированы только:

```python
from integrations.tasks import export_monthly_report_to_glpi  # noqa: F401
```

Но не были импортированы:
- `check_all_devices_in_glpi`
- `check_single_device_in_glpi`

## Решение

### 1. Исправление кода

Добавлен явный импорт всех задач из `integrations.tasks` в `printer_inventory/celery.py`:

```python
from integrations.tasks import (  # noqa: F401
    export_monthly_report_to_glpi,
    check_all_devices_in_glpi,
    check_single_device_in_glpi
)
```

### 2. Очистка застрявших задач

Создано два скрипта для очистки застрявших задач:

#### Вариант 1: Bash скрипт (быстрый)

```bash
./cleanup_glpi_tasks.sh
```

#### Вариант 2: Python скрипт (рекомендуемый)

```bash
# Предварительный просмотр
python cleanup_glpi_tasks.py --dry-run

# Очистка
python cleanup_glpi_tasks.py
```

### 3. Перезапуск workers

После очистки задач необходимо перезапустить workers:

```bash
# Если используется systemd
sudo systemctl restart celery-worker*

# Или через start_workers.sh
./stop_workers.sh
./start_workers.sh
```

### 4. Проверка

После перезапуска проверьте:

```bash
# Проверка задач в очереди
./find_glpi_tasks.sh

# Проверка workers
./diagnose_workers.sh

# Проверка логов
tail -f logs/celery.log | grep -i glpi
```

## Тестирование

### Ручной запуск задачи

Вы можете вручную запустить задачу для проверки:

```bash
python manage.py shell
```

```python
from integrations.tasks import check_all_devices_in_glpi

# Запуск задачи в фоне
result = check_all_devices_in_glpi.delay()
print(f"Task ID: {result.id}")

# Проверка статуса
print(f"Status: {result.status}")

# Получение результата (ждет завершения)
print(result.get(timeout=300))
```

### Проверка расписания

Задача настроена на выполнение каждый день в 02:00:

```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'glpi-check-all-devices-daily': {
        'task': 'integrations.tasks.check_all_devices_in_glpi',
        'schedule': crontab(hour=2, minute=0),  # 02:00 каждый день
        'options': {
            'queue': 'low_priority',
            'priority': 1
        }
    },
}
```

## Профилактика

### Регулярный мониторинг

Добавьте в cron проверку застрявших задач:

```bash
# Каждые 6 часов
0 */6 * * * cd /path/to/project && ./find_glpi_tasks.sh >> logs/glpi_tasks_monitor.log 2>&1
```

### Алерты

Настройте алерты в вашей системе мониторинга:
- Количество задач в очереди > 15000
- Задачи с `retries > 2`
- Задачи с истекшим ETA

## Дополнительная информация

### Структура задачи

```python
@shared_task(bind=True, max_retries=3)
def check_all_devices_in_glpi(self):
    """
    Ежедневная задача: проверяет все устройства в GLPI.

    - Получает все устройства с серийными номерами
    - Проверяет каждое устройство через GLPI API
    - Сохраняет результаты в модель GLPISync
    - В случае ошибки делает retry с экспоненциальной задержкой
    """
```

### Retry политика

- **max_retries**: 3
- **Задержка**: экспоненциальная
  - 1-я попытка: сразу
  - 2-я попытка: через 5 минут (300s)
  - 3-я попытка: через 20 минут (1200s)
  - 4-я попытка: через 80 минут (4800s)

### Логирование

Задача логирует:
- Начало выполнения: `"Starting daily GLPI check for all devices"`
- Количество устройств: `"Found {N} devices to check"`
- Конфликты: `"Found {N} devices with conflicts"`
- Ошибки: `"Fatal error in GLPI check task: {exc}"`

Логи можно посмотреть в:
- Django logs: `tail -f logs/django.log`
- Celery logs: `tail -f logs/celery.log`

## Связанные файлы

- `printer_inventory/celery.py` - конфигурация Celery
- `integrations/tasks.py` - определение задач
- `integrations/glpi/services.py` - бизнес-логика GLPI
- `integrations/glpi/client.py` - GLPI API клиент
- `integrations/models.py` - модель GLPISync
- `printer_inventory/settings.py` - настройки расписания (CELERY_BEAT_SCHEDULE)

## Контакты

При возникновении проблем:
1. Проверьте логи workers: `journalctl -u celery-worker* -n 100`
2. Проверьте подключение к GLPI: `python manage.py sync_glpi --limit 1 --force`
3. Проверьте Redis: `redis-cli -n 3 INFO`
