# Исправление переполнения очереди Celery

**Дата:** 2026-01-08
**Проблема:** Очередь `low_priority` накапливает задачи быстрее, чем Workers успевают обрабатывать
**Причина:** Отсутствует защита от переполнения в `inventory_daemon_task`

---

## 🔍 Что было добавлено

### 1. Защита в `inventory_daemon_task` (inventory/tasks.py)

**Проверка размера очереди перед созданием задач:**
```python
current_queue_size = redis_client.llen('low_priority')

if current_queue_size > max_queue_size:
    logger.error("⚠️ QUEUE OVERFLOW PROTECTION: Skipping this run")
    return {'success': False, 'error': 'Queue overflow'}
```

**Фильтрация принтеров по активным организациям:**
```python
printers = Printer.objects.filter(
    Q(organization__active=True) | Q(organization__isnull=True)
)
```

### 2. Задача `cleanup_queue_if_needed` (inventory/tasks.py)

Автоматически очищает очередь если она превышает критический размер:
- **Порог:** `MAX_QUEUE_SIZE × 2` (по умолчанию 20,000)
- **Действие:** Удаляет старые задачи, оставляя `MAX_QUEUE_SIZE`
- **Расписание:** Каждый час в XX:55 (за 5 минут до демона)

### 3. Обновлено расписание Celery Beat (settings.py)

Добавлена задача `cleanup-queue-before-daemon`:
```python
'cleanup-queue-before-daemon': {
    'task': 'inventory.tasks.cleanup_queue_if_needed',
    'schedule': crontab(minute=55),  # XX:55
    'options': {'queue': 'daemon', 'priority': 9}
}
```

---

## 🚀 Инструкция по развёртыванию на ПРОДАКШН

### Шаг 1: Синхронизация кода

На **локальной машине**:
```bash
# Убедитесь что вы на правильной ветке
cd ~/printer-inventory-django
git status  # Должно показать: claude/fork-report-pagination-bmDUR

# Синхронизируйте с продакшном
rsync -avz --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='logs/' \
  --exclude='staticfiles/' \
  --exclude='media/' \
  ./ user@production-server:/var/www/printer-inventory/
```

### Шаг 2: Добавить переменную окружения

На **продакшн-сервере**:
```bash
cd /var/www/printer-inventory

# Добавьте в .env файл
cat >> .env <<'EOF'

# ===== ЗАЩИТА ОТ ПЕРЕПОЛНЕНИЯ ОЧЕРЕДИ =====
# Максимальный размер очереди low_priority
MAX_QUEUE_SIZE=10000

# При превышении MAX_QUEUE_SIZE × 2 автоматически очищается до MAX_QUEUE_SIZE
# Задача cleanup_queue_if_needed запускается каждый час в XX:55
EOF

# Проверьте что добавилось
tail -5 .env
```

### Шаг 3: Перезапустить Celery сервисы

```bash
# Остановить всё
sudo systemctl stop celery-worker.service celery-beat.service

# Убить зависшие процессы
sudo pkill -9 -f celery

# Очистить schedule файлы Beat
sudo rm -f /var/run/celery/celerybeat-schedule*
sudo rm -f /var/www/printer-inventory/celerybeat-schedule.db*

# Запустить Workers
sudo systemctl start celery-worker.service

# Подождать инициализации
sleep 10

# Запустить Beat
sudo systemctl start celery-beat.service
```

### Шаг 4: Проверка

```bash
# 1. Проверить что сервисы запущены
sudo systemctl status celery-worker.service --no-pager
sudo systemctl status celery-beat.service --no-pager

# 2. Проверить процессы
ps aux | grep 'celery' | grep -v grep

# 3. Проверить размер очереди
redis-cli -n 3 LLEN low_priority

# 4. Проверить логи Workers (должна быть обработка задач)
tail -f logs/celery.log | grep -E "(Starting inventory|completed)"

# 5. Проверить логи Beat (ждать до XX:55 или XX:00)
tail -f /var/log/celery/beat.log
```

### Шаг 5: Мониторинг в течение часа

**Ждать до XX:55** и проверить:
```bash
# Должна запуститься cleanup-queue-before-daemon
tail -20 /var/log/celery/beat.log | grep cleanup

# Должно быть в логах (если очередь > 20,000):
# "⚠️  QUEUE CLEANUP TRIGGERED: low_priority has X tasks"
# "✅ Queue cleanup completed: removed Y tasks, new size: 10,000"
```

**Ждать до XX:00** и проверить:
```bash
# Должна запуститься inventory-daemon-every-hour
tail -50 logs/celery.log | grep -A 10 "STARTING INVENTORY DAEMON"

# Должно быть в логах:
# "Current low_priority queue size: X"
# "Found N printers in active organizations"
# "Queue size before: X"
# "Queue size after: ~Y"
```

---

## 📊 Ожидаемое поведение

### ✅ Нормальная работа

**XX:55 - Задача cleanup_queue_if_needed:**
```
Queue low_priority size: 8,234 (critical threshold: 20,000)
✓ Queue size OK (8,234 < 20,000)
```

**XX:00 - Задача inventory_daemon_task:**
```
Current low_priority queue size: 8,234
Found 2,345 printers in active organizations
Successfully queued: 2,345/2,345
Queue size before: 8,234
Queue size after: ~10,579
```

**Через 30 минут - Workers обрабатывают:**
```bash
$ redis-cli -n 3 LLEN low_priority
(integer) 3456  # Очередь уменьшается
```

### ⚠️ Переполнение (>20,000 задач)

**XX:55 - Автоочистка:**
```
⚠️  QUEUE CLEANUP TRIGGERED: low_priority has 23,456 tasks (limit: 20,000)
Removing 13,456 old tasks from queue...
✅ Queue cleanup completed: removed 13,456 tasks, new size: 10,000
```

**XX:00 - Демон создаёт задачи:**
```
Current low_priority queue size: 10,000
Found 2,345 printers in active organizations
Successfully queued: 2,345/2,345
Queue size after: ~12,345
```

### 🛡️ Защита срабатывает (>10,000 задач)

**XX:00 - Демон пропускает запуск:**
```
Current low_priority queue size: 12,456
⚠️  QUEUE OVERFLOW PROTECTION: Queue size (12,456) exceeds limit (10,000).
Skipping this run to prevent Redis overflow.
```

---

## 🔧 Настройка MAX_QUEUE_SIZE

### Расчёт оптимального значения

**Формула:**
```
Worker Capacity = Количество воркеров × Concurrency × 360 задач/час
MAX_QUEUE_SIZE = Worker Capacity × 3-5 часов запаса
```

Где **360** = (60 мин × 60 сек) / 10 сек на задачу

**Примеры:**

| Принтеров | Воркеров | Concurrency | Capacity/час | MAX_QUEUE_SIZE |
|-----------|----------|-------------|--------------|----------------|
| 1,000 | 1 | 2 | 720 | 2,000-3,600 |
| 2,000 | 2 | 2 | 1,440 | 4,300-7,200 |
| 5,000 | 3 | 4 | 4,320 | 13,000-21,600 |

**Рекомендация:** `MAX_QUEUE_SIZE = 10000` подходит для большинства установок (1,000-3,000 принтеров).

### Изменение MAX_QUEUE_SIZE

В `.env`:
```bash
# Для небольших установок (< 1,000 принтеров)
MAX_QUEUE_SIZE=5000

# Для средних установок (1,000-3,000 принтеров) - ПО УМОЛЧАНИЮ
MAX_QUEUE_SIZE=10000

# Для крупных установок (> 5,000 принтеров)
MAX_QUEUE_SIZE=20000
```

После изменения:
```bash
sudo systemctl restart celery-worker.service celery-beat.service
```

---

## 🧹 Если очередь УЖЕ переполнена

Если на момент развёртывания очередь > 20,000:

```bash
# Проверьте размер
redis-cli -n 3 LLEN low_priority

# Если > 20,000 - очистите вручную
cd /var/www/printer-inventory
bash clear_queues.sh
# Введите 'yes' для подтверждения

# Или через Redis напрямую
redis-cli -n 3 DEL low_priority
```

---

## 📝 Изменения в коде

### inventory/tasks.py
- ✅ Добавлена проверка размера очереди в `inventory_daemon_task`
- ✅ Добавлена фильтрация по активным организациям
- ✅ Добавлено логирование размера очереди
- ✅ Добавлена задача `cleanup_queue_if_needed`

### printer_inventory/settings.py
- ✅ Добавлена задача `cleanup-queue-before-daemon` в `CELERY_BEAT_SCHEDULE`

### .env (требует ручного добавления)
- ✅ Добавить `MAX_QUEUE_SIZE=10000`

---

## 🆘 Если что-то пошло не так

### Проблема: "Task not registered"

```bash
# Проверьте что задача импортируется
cd /var/www/printer-inventory
source .venv/bin/activate
python manage.py shell

>>> from inventory.tasks import cleanup_queue_if_needed
>>> cleanup_queue_if_needed()
```

Если ошибка → проверьте синтаксис в `inventory/tasks.py`

### Проблема: Очередь продолжает расти

```bash
# Проверьте переменную окружения
grep MAX_QUEUE_SIZE .env

# Проверьте что Workers работают
ps aux | grep 'celery.*worker'

# Проверьте логи на наличие проверки размера
grep "Current low_priority queue size" logs/celery.log

# Если проверки нет → код не обновился, перезапустите Workers
sudo systemctl restart celery-worker.service
```

### Проблема: cleanup_queue_if_needed не запускается

```bash
# Проверьте логи Beat
tail -50 /var/log/celery/beat.log | grep cleanup

# Проверьте расписание
cd /var/www/printer-inventory
source .venv/bin/activate
python -c "from django.conf import settings; import pprint; pprint.pprint(settings.CELERY_BEAT_SCHEDULE)"

# Если задачи нет → settings.py не обновился
```

---

## ✅ Контрольный список развёртывания

- [ ] Код синхронизирован с продакшном
- [ ] `MAX_QUEUE_SIZE=10000` добавлен в `.env`
- [ ] Celery Workers перезапущены
- [ ] Celery Beat перезапущен
- [ ] Процессы запущены (проверено через `ps aux`)
- [ ] Размер очереди отслеживается (в логах есть "Current low_priority queue size")
- [ ] Задача `cleanup-queue-before-daemon` в расписании Beat
- [ ] Ждём до XX:55 и проверяем запуск cleanup
- [ ] Ждём до XX:00 и проверяем запуск daemon с проверкой размера
- [ ] Очередь стабилизируется в течение часа

---

**Автор:** Claude AI
**Дата:** 2026-01-08
**Коммит:** См. git log
