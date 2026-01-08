# 🚨 БЫСТРОЕ РЕШЕНИЕ: Очередь Celery не очищается

**Проблема:** `redis-cli -n 3 LLEN low_priority` показывает большое число (17,972+)

**Основная причина:** Celery Workers не запущены или не обрабатывают задачи

---

## ⚡ БЫСТРОЕ ИСПРАВЛЕНИЕ (5 минут)

Выполните на **продакшн-сервере** (`/var/www/printer-inventory`):

```bash
# 1. Диагностика (покажет причину проблемы)
bash scripts/utils/diagnose_queue_problem.sh

# 2. Остановить всё
sudo systemctl stop celery-worker.service celery-beat.service
sudo pkill -9 -f celery

# 3. Очистить очередь (если > 20,000 задач)
bash scripts/celery/clear_queues.sh
# Введите 'yes' для подтверждения

# 4. Запустить Workers
sudo systemctl start celery-worker.service

# 5. Подождать 10 секунд
sleep 10

# 6. Запустить Beat
sudo systemctl start celery-beat.service

# 7. Проверить результат
ps aux | grep celery | grep -v grep
redis-cli -n 3 LLEN low_priority
```

---

## 📊 Что должно произойти

### ✅ Правильная работа:

```bash
# Процессы (должно быть 4+)
$ ps aux | grep celery | grep -v grep
www-data  1234  celery worker ... high_priority
www-data  1235  celery worker ... low_priority
www-data  1236  celery worker ... daemon
www-data  1237  celery beat ...

# Очередь (должна постепенно уменьшаться)
$ redis-cli -n 3 LLEN low_priority
(integer) 450    # через 5 минут
(integer) 180    # через 10 минут
(integer) 0      # через 20-30 минут
```

### ❌ Если не работает:

**Проблема 1: Workers не запускаются**
```bash
# Проверьте логи
sudo journalctl -u celery-worker.service -n 50
tail -f /var/www/printer-inventory/logs/celery.log

# Попробуйте вручную
cd /var/www/printer-inventory
source .venv/bin/activate
./start_workers.sh
```

**Проблема 2: Очередь не уменьшается**
```bash
# Проверьте что Workers видят очереди
redis-cli -n 3 LLEN low_priority
redis-cli -n 3 LLEN high_priority

# Проверьте что воркеры активны
tail -f /var/www/printer-inventory/logs/celery.log
# Должны видеть: "Starting inventory for printer..."
```

---

## 📚 Полная документация

Если быстрое решение не помогло:

1. **Полная диагностика и решение:** `docs/TROUBLESHOOTING_QUEUE.md`
2. **Управление очередями:** `docs/QUEUE_MANAGEMENT.md`
3. **Исправление Beat:** `docs/CELERY_BEAT_FIX_DEPLOYMENT.md`

---

## 🔧 Настройка защиты от повторения

После исправления добавьте в `/var/www/printer-inventory/.env`:

```bash
# Защита от переполнения очереди
MAX_QUEUE_SIZE=10000

# Интервал опроса (можно увеличить если Workers не успевают)
POLL_INTERVAL_MINUTES=60
```

Перезапустите сервисы:
```bash
sudo systemctl restart celery-worker.service celery-beat.service
```

---

## 💡 Мониторинг

Следите за очередью:

```bash
# Размер очереди
watch -n 60 'redis-cli -n 3 LLEN low_priority'

# Логи Workers (должна быть активность)
tail -f /var/www/printer-inventory/logs/celery.log

# Логи Beat
tail -f /var/log/celery/beat.log
```

---

**Если проблема повторяется** → см. `docs/TROUBLESHOOTING_QUEUE.md` раздел "Расчёт производительности Workers"
