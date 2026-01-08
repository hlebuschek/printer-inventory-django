# Исправление проблемы множественных процессов Celery в systemd

## 🔴 Проблема

**Симптомы:**
1. При `systemctl restart celery-worker` количество процессов **растёт** вместо замены:
   - 1-й restart: 22 процесса
   - 2-й restart: 34 процесса (+12)
   - 3-й restart: 46 процессов (+12)

2. Очередь `low_priority` **не уменьшается** (workers медленно обрабатывают):
   - 19,240 → 19,233 → 19,223 (всего -17 задач за 3 restart!)

3. Дубликаты `celery-beat.service`:
   - 2 разных файла конфигурации в `/etc/systemd/system/`

## 🔍 Причина

### Причина #1: KillMode=process

В файле `/etc/systemd/system/celery-worker.service`:

```ini
KillMode=process  # ← ПРОБЛЕМА!
```

**Что происходит:**
- `start_workers.sh` запускает celery процессы в фоне с `&`
- При `systemctl restart` systemd убивает **только главный bash процесс**
- **Дочерние celery процессы продолжают работать!**
- Новый restart добавляет ЕЩЁ процессы → накопление

### Причина #2: Дубликаты Beat

Два файла `celery-beat.service` → Beat запускается **дважды** → двойная нагрузка

### Причина #3: Медленная обработка

Workers обрабатывают ~0.1 задачи/минуту вместо 10-50:
- Возможно недостаточно `concurrency`
- Возможно задачи долго выполняются
- Возможно workers зависают

---

## 🚀 Решение: Автоматическое исправление

### Быстрое исправление (10 минут)

На production сервере:

```bash
cd /var/www/printer-inventory
git pull origin claude/fork-report-pagination-bmDUR

# Запустите экстренное исправление
./fix_celery_emergency.sh
```

Скрипт выполнит:
1. ✅ Остановит **все** процессы Celery (включая зависшие)
2. ✅ Удалит дубликаты `celery-beat.service`
3. ✅ Исправит `KillMode=process` → `KillMode=mixed`
4. ✅ Перезапустит сервисы
5. ✅ Проверит результат

---

## 🛠 Ручное исправление (если нужно)

### Шаг 1: Полная остановка

```bash
# Остановить systemd сервисы
sudo systemctl stop celery-worker.service celery-beat.service

# Убить все процессы celery принудительно
sudo pkill -9 -f celery

# Проверить что все остановлены
ps aux | grep celery | grep -v grep
# Должно быть пусто!
```

### Шаг 2: Исправить celery-worker.service

```bash
# Открыть файл
sudo nano /etc/systemd/system/celery-worker.service
```

**Найдите строку:**
```ini
KillMode=process
```

**Замените на:**
```ini
KillMode=mixed
```

**Или используйте готовый файл:**

```bash
sudo cp systemd/celery-worker.service.correct /etc/systemd/system/celery-worker.service
```

### Шаг 3: Удалить дубликаты Beat

```bash
# Проверить сколько файлов
ls -la /etc/systemd/system/celery-beat*

# Если больше 1 - удалить лишние
sudo rm /etc/systemd/system/celery-beat.service.d  # если есть

# Использовать правильный конфиг
sudo cp systemd/celery-beat.service.correct /etc/systemd/system/celery-beat.service
```

### Шаг 4: Перезагрузить systemd

```bash
sudo systemctl daemon-reload
```

### Шаг 5: Запустить сервисы

```bash
sudo systemctl start celery-worker.service
sleep 5
sudo systemctl start celery-beat.service
sleep 3

# Проверить
./diagnose_workers.sh
```

---

## 📊 Проверка исправления

### Тест 1: Количество процессов стабильно

```bash
# Запишите количество процессов
./diagnose_workers.sh

# Сделайте restart
sudo systemctl restart celery-worker.service
sleep 5

# Проверьте снова
./diagnose_workers.sh

# Количество процессов НЕ должно расти!
# Должно быть ~6-8 процессов (не 40+)
```

### Тест 2: Очередь уменьшается

```bash
# Мониторинг очереди (5 минут)
BEFORE=$(redis-cli -n 3 LLEN low_priority)
echo "Начало: $BEFORE"

sleep 300  # 5 минут

AFTER=$(redis-cli -n 3 LLEN low_priority)
PROCESSED=$((BEFORE - AFTER))

echo "Конец: $AFTER"
echo "Обработано: $PROCESSED задач"
echo "Скорость: $(($PROCESSED / 5)) задач/мин"
```

**Нормальная скорость:** 10-50 задач/мин

**Если медленно:**
- Увеличьте concurrency в `start_workers.sh`
- Проверьте логи на ошибки

### Тест 3: Логи без ошибок

```bash
# Логи workers
tail -100 logs/celery.log | grep -i error

# Системные логи
sudo journalctl -u celery-worker -n 100 --no-pager | grep -i error
```

---

## 🔧 Дополнительные оптимизации

### Увеличение concurrency для low_priority

Если очередь уменьшается медленно:

```bash
nano start_workers.sh
```

**Найдите секцию low_priority worker:**

```bash
# Было:
celery -A printer_inventory worker \
    --queues=low_priority \
    --concurrency=2 \     # ← Изменить
    ...

# Стало:
celery -A printer_inventory worker \
    --queues=low_priority \
    --concurrency=4 \     # ← Удвоили!
    ...
```

**Перезапустите:**

```bash
sudo systemctl restart celery-worker.service
```

### Снижение частоты daemon

В `printer_inventory/settings.py`:

```python
'inventory-daemon': {
    'task': 'inventory.tasks.inventory_daemon_task',
    # Было: каждый час
    'schedule': crontab(minute=0),

    # Стало: каждые 2 часа
    'schedule': crontab(minute=0, hour='*/2'),

    'options': {'queue': 'low_priority'}
},
```

**Перезапустите Beat:**

```bash
sudo systemctl restart celery-beat.service
```

---

## 📋 Правильная конфигурация systemd

### celery-worker.service

```ini
[Unit]
Description=Celery Workers for Printer Inventory
After=network.target redis.service postgresql.service
Requires=redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/printer-inventory

EnvironmentFile=/var/www/printer-inventory/.env
Environment="PATH=/var/www/printer-inventory/.venv/bin:..."
Environment="PYTHONUNBUFFERED=1"

ExecStart=/bin/bash /var/www/printer-inventory/start_workers.sh

# ВАЖНО: Правильная остановка всех процессов
ExecStop=/usr/bin/pkill -TERM -f "celery.*worker"
ExecStop=/bin/sleep 5
ExecStopPost=/usr/bin/pkill -9 -f "celery.*worker"

# КРИТИЧНО: mixed убивает и родителя и детей!
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Ключевые параметры:**

- `KillMode=mixed` - убивает главный процесс и дочерние
- `ExecStop` - явно убивает все celery процессы
- `ExecStopPost` - принудительное завершение (SIGKILL)
- `TimeoutStopSec=30` - ждёт 30 секунд перед SIGKILL

### celery-beat.service

```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service celery-worker.service
Requires=redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/printer-inventory

EnvironmentFile=/var/www/printer-inventory/.env

# Удаление старого schedule
ExecStartPre=/bin/sh -c 'rm -f /var/run/celery/celerybeat-schedule*'

ExecStart=/var/www/printer-inventory/.venv/bin/celery -A printer_inventory beat \
    --loglevel=INFO \
    --pidfile=/var/run/celery/beat.pid \
    --schedule=/var/run/celery/celerybeat-schedule

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## ❓ FAQ

**Q: Почему процессы множились?**

A: `KillMode=process` убивает только главный bash процесс. Дочерние celery workers (запущенные с `&`) остаются работать. При restart новые процессы добавляются к старым.

**Q: Что делает KillMode=mixed?**

A: Отправляет SIGTERM главному процессу И всем дочерним процессам в control group. Гарантирует полную остановку.

**Q: Можно ли использовать KillMode=control-group?**

A: Да, это аналог `mixed`, но без явной остановки главного процесса первым. `mixed` предпочтительнее для корректного shutdown.

**Q: Сколько процессов celery должно быть в норме?**

A: При настройках из `start_workers.sh`:
- high_priority: concurrency=4 → 4-5 процессов
- low_priority: concurrency=2 → 2-3 процесса
- daemon: concurrency=1 → 1-2 процесса
- **Итого: 7-10 процессов** (не 40+!)

**Q: Как избежать проблемы в будущем?**

A:
1. Используйте правильный `KillMode=mixed`
2. Периодически проверяйте `./diagnose_workers.sh`
3. Настройте мониторинг (Grafana/Prometheus)
4. Не делайте частые restart без необходимости

**Q: Что если очередь всё равно растёт?**

A:
1. Увеличьте concurrency с 2 до 4 для low_priority
2. Снизьте частоту daemon (каждые 2 часа вместо 1)
3. Проверьте логи на ошибки выполнения задач
4. Возможно задачи слишком долго выполняются - оптимизируйте код опроса

---

## 🔗 Связанные документы

- `docs/FIX_LOW_PRIORITY_WORKER.md` - Запуск отсутствующего worker
- `docs/CELERY_QUEUE_OVERFLOW.md` - Переполнение очереди
- `docs/TROUBLESHOOTING_QUEUE.md` - Общие проблемы с очередью
- `start_workers.sh` - Скрипт запуска workers
- `diagnose_workers.sh` - Диагностика состояния workers

---

## 📞 Поддержка

При проблемах предоставьте:

1. Вывод `./diagnose_workers.sh` ДО и ПОСЛЕ restart
2. Содержимое `/etc/systemd/system/celery-*.service`
3. Логи: `sudo journalctl -u celery-worker -n 200`
4. Вывод: `ps aux | grep celery | wc -l`
5. Размер очереди: `redis-cli -n 3 LLEN low_priority`
