# Решение проблемы переполнения очереди Celery

## Проблема

Очередь `low_priority` растёт с 9,919 до 19,334+ задач, несмотря на защиту от переполнения.

## Диагностика

### Проверка 1: Workers запущены?

```bash
ps aux | grep "celery.*worker" | grep -v grep
```

**Если пусто →** Workers не запущены! Запустите их:

```bash
cd /var/www/printer-inventory
source .venv/bin/activate
nohup ./start_workers.sh > logs/celery.log 2>&1 &
```

### Проверка 2: Размер очереди

```bash
redis-cli -n 3 LLEN low_priority
```

### Проверка 3: Скорость обработки

```bash
# Запишите текущий размер
BEFORE=$(redis-cli -n 3 LLEN low_priority)
echo "Очередь: $BEFORE"

# Подождите 5 минут
sleep 300

# Проверьте снова
AFTER=$(redis-cli -n 3 LLEN low_priority)
PROCESSED=$((BEFORE - AFTER))
echo "Обработано за 5 минут: $PROCESSED задач"
echo "Скорость: $(($PROCESSED / 5)) задач/мин"
```

## Решение 1: Workers не запущены

```bash
./start_workers.sh
```

## Решение 2: Workers медленные

### Вариант А: Увеличить concurrency

Отредактируйте `start_workers.sh`:

```bash
# Было:
--concurrency=2

# Стало (для low_priority worker):
--concurrency=4
```

Перезапустите workers:

```bash
pkill -f "celery.*worker"
./start_workers.sh
```

### Вариант Б: Снизить частоту daemon

В `printer_inventory/settings.py`:

```python
'inventory-daemon': {
    'task': 'inventory.tasks.inventory_daemon_task',
    'schedule': crontab(minute=0),  # Было: каждые 60 минут
    # Стало: каждые 120 минут (2 часа)
    'schedule': crontab(minute=0, hour='*/2'),
    'options': {'queue': 'low_priority'}
},
```

Перезапустите Beat:

```bash
pkill -f "celery.*beat"
celery -A printer_inventory beat --loglevel=INFO > logs/beat.log 2>&1 &
```

### Вариант В: Снизить MAX_QUEUE_SIZE

В `.env`:

```bash
# Было:
MAX_QUEUE_SIZE=10000

# Стало:
MAX_QUEUE_SIZE=5000
```

Перезапустите все сервисы.

### Вариант Г: Принудительная очистка старых задач

```bash
python manage.py shell
```

```python
from inventory.tasks import cleanup_queue_if_needed
from inventory.models import InventoryTask
from django.utils import timezone
from datetime import timedelta

# Ручная очистка задач старше 7 дней
week_ago = timezone.now() - timedelta(days=7)
old_tasks = InventoryTask.objects.filter(created_at__lt=week_ago)
count = old_tasks.count()
print(f"Найдено старых задач: {count}")
old_tasks.delete()
print("Очищено!")

# Или используйте cleanup функцию
cleanup_queue_if_needed()
```

## Решение 3: Комбинированный подход (рекомендуется)

1. **Запустите workers** (если не запущены)
2. **Увеличьте concurrency** для low_priority с 2 до 4
3. **Снизьте MAX_QUEUE_SIZE** с 10000 до 5000
4. **Принудительно очистите** старые задачи

```bash
# Шаг 1: Остановите все
pkill -f celery

# Шаг 2: Отредактируйте start_workers.sh
nano start_workers.sh
# Измените --concurrency=2 на --concurrency=4 для low_priority worker

# Шаг 3: Отредактируйте .env
echo "MAX_QUEUE_SIZE=5000" >> .env

# Шаг 4: Очистите старые задачи
python manage.py shell << EOF
from inventory.models import InventoryTask
from django.utils import timezone
from datetime import timedelta
old = InventoryTask.objects.filter(created_at__lt=timezone.now() - timedelta(days=7))
count = old.count()
old.delete()
print(f"Удалено {count} старых задач")
EOF

# Шаг 5: Запустите workers
./start_workers.sh

# Шаг 6: Мониторинг
watch -n 10 'redis-cli -n 3 LLEN low_priority'
```

## Мониторинг

### Постоянный мониторинг очереди

```bash
cat > /var/www/printer-inventory/monitor_celery.sh << 'SCRIPT'
#!/bin/bash
while true; do
    QUEUE=$(redis-cli -n 3 LLEN low_priority 2>/dev/null || echo "0")
    WORKERS=$(ps aux | grep -c "celery.*worker.*low_priority" || echo "0")
    RATE_1M=$(redis-cli -n 3 LLEN low_priority)
    sleep 60
    RATE_2M=$(redis-cli -n 3 LLEN low_priority)
    PROCESSED=$((RATE_1M - RATE_2M))

    echo "[$(date '+%Y-%m-%d %H:%M:%S')]"
    echo "  Очередь: $(printf "%'d" $QUEUE)"
    echo "  Workers: $WORKERS"
    echo "  Обработано/мин: $PROCESSED"
    echo ""
done
SCRIPT

chmod +x /var/www/printer-inventory/monitor_celery.sh
```

Запустите в tmux:

```bash
tmux new -s celery-monitor
./monitor_celery.sh
# Ctrl+B, затем D для отсоединения
```

## Автоматический рестарт workers (systemd)

Если workers часто падают, настройте systemd для автоперезапуска:

```bash
# /etc/systemd/system/celery-worker-low.service
[Unit]
Description=Celery Worker (Low Priority)
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/printer-inventory
Environment="PATH=/var/www/printer-inventory/.venv/bin"
ExecStart=/var/www/printer-inventory/.venv/bin/celery -A printer_inventory worker \
    --queues=low_priority \
    --loglevel=INFO \
    --concurrency=4 \
    --max-tasks-per-child=200 \
    --hostname=worker_low@%h \
    --pidfile=/var/run/celery/worker_low.pid \
    --logfile=/var/www/printer-inventory/logs/celery_low.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker-low
sudo systemctl start celery-worker-low
sudo systemctl status celery-worker-low
```

## FAQ

**Q: Почему очередь растёт если защита работает?**

A: Защита блокирует daemon от добавления НОВЫХ задач, но НЕ останавливает уже добавленные задачи от накопления. Если workers не работают или медленные, очередь будет расти.

**Q: При каком размере очереди срабатывает auto-cleanup?**

A: При > 20,000 задач. Cleanup запускается каждый час в XX:55.

**Q: Нужно ли перезапускать workers после изменения .env?**

A: Да! Workers читают .env при запуске. После изменений:

```bash
pkill -f celery
./start_workers.sh
```

**Q: Как проверить что cleanup сработала?**

A: Смотрите логи:

```bash
grep -i "cleanup" logs/celery.log
grep -i "удалено задач" logs/celery.log
```
