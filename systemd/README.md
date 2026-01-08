# Systemd Service Configurations

Эта папка содержит **правильные** конфигурации systemd для Celery сервисов.

## Файлы

### `celery-worker.service.correct`
Правильная конфигурация для Celery workers с корректным `KillMode=mixed`.

**Установка:**
```bash
sudo cp systemd/celery-worker.service.correct /etc/systemd/system/celery-worker.service
sudo systemctl daemon-reload
sudo systemctl restart celery-worker.service
```

### `celery-beat.service.correct`
Правильная конфигурация для Celery Beat без дубликатов.

**Установка:**
```bash
sudo cp systemd/celery-beat.service.correct /etc/systemd/system/celery-beat.service
sudo systemctl daemon-reload
sudo systemctl restart celery-beat.service
```

## Ключевые отличия от проблемной конфигурации

### ❌ Проблемная конфигурация

```ini
KillMode=process  # ← Убивает только главный процесс!
```

**Проблема:** При restart старые celery процессы продолжают работать, новые добавляются → накопление процессов (22 → 34 → 46+)

### ✅ Правильная конфигурация

```ini
KillMode=mixed    # ← Убивает и главный и дочерние!

ExecStop=/usr/bin/pkill -TERM -f "celery.*worker"
ExecStop=/bin/sleep 5
ExecStopPost=/usr/bin/pkill -9 -f "celery.*worker"
```

**Решение:** Все celery процессы корректно завершаются при restart.

## Проверка после установки

### Тест 1: Количество процессов стабильно

```bash
# Проверка ДО
./diagnose_workers.sh

# Restart
sudo systemctl restart celery-worker.service
sleep 5

# Проверка ПОСЛЕ
./diagnose_workers.sh

# Количество процессов НЕ должно расти!
```

### Тест 2: Полная остановка работает

```bash
# Остановка
sudo systemctl stop celery-worker.service
sleep 3

# Проверка
ps aux | grep celery | grep -v grep

# Должно быть ПУСТО!
```

## Документация

Подробности в `docs/SYSTEMD_CELERY_FIX.md`
