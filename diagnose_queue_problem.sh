#!/bin/bash
# Диагностика проблемы с очередью Celery

echo "════════════════════════════════════════════════════════════════"
echo "ДИАГНОСТИКА ПРОБЛЕМЫ С ОЧЕРЕДЬЮ CELERY"
echo "════════════════════════════════════════════════════════════════"
echo ""

echo "🕐 Текущее время:"
date "+%Y-%m-%d %H:%M:%S"
echo ""

echo "📊 1. ПРОВЕРКА ПРОЦЕССОВ CELERY"
echo "────────────────────────────────────────────────────────────────"
WORKER_COUNT=$(ps aux | grep -E 'celery.*worker' | grep -v grep | wc -l)
BEAT_COUNT=$(ps aux | grep -E 'celery.*beat' | grep -v grep | wc -l)

echo "Celery Workers: $WORKER_COUNT"
echo "Celery Beat:    $BEAT_COUNT"
echo ""

if [ $WORKER_COUNT -eq 0 ]; then
    echo "❌ ПРОБЛЕМА: Celery Workers НЕ ЗАПУЩЕНЫ!"
    echo "   → Задачи добавляются в очередь, но не обрабатываются"
    echo ""
fi

if [ $BEAT_COUNT -gt 1 ]; then
    echo "⚠️  ПРЕДУПРЕЖДЕНИЕ: Запущено $BEAT_COUNT процессов Beat (должен быть 1)"
    echo "   → Это может создавать дублирующие задачи"
    echo ""
fi

echo "Детали процессов:"
ps aux | grep -E 'celery.*(worker|beat)' | grep -v grep || echo "Нет запущенных процессов Celery"
echo ""

echo "📦 2. РАЗМЕР ОЧЕРЕДЕЙ REDIS"
echo "────────────────────────────────────────────────────────────────"
LOW_PRI=$(redis-cli -n 3 LLEN low_priority 2>/dev/null || echo "ERROR")
HIGH_PRI=$(redis-cli -n 3 LLEN high_priority 2>/dev/null || echo "ERROR")
DAEMON=$(redis-cli -n 3 LLEN daemon 2>/dev/null || echo "ERROR")
DEFAULT=$(redis-cli -n 3 LLEN celery 2>/dev/null || echo "ERROR")

echo "low_priority:    $LOW_PRI задач"
echo "high_priority:   $HIGH_PRI задач"
echo "daemon:          $DAEMON задач"
echo "default:         $DEFAULT задач"
echo ""

if [ "$LOW_PRI" = "ERROR" ]; then
    echo "❌ ПРОБЛЕМА: Не удается подключиться к Redis!"
    echo "   Проверьте что Redis запущен: systemctl status redis"
    exit 1
fi

# Проверка переполнения
if [ "$LOW_PRI" != "ERROR" ] && [ "$LOW_PRI" -gt 10000 ]; then
    echo "⚠️  ПЕРЕПОЛНЕНИЕ: Очередь low_priority содержит $LOW_PRI задач!"
    echo "   Рекомендуется: MAX_QUEUE_SIZE=10000"
    echo ""
fi

echo "📄 3. ПРОВЕРКА ЛОГОВ"
echo "────────────────────────────────────────────────────────────────"

# Проверка логов воркеров
if [ -f "logs/celery.log" ]; then
    echo "✓ logs/celery.log существует"
    LAST_WORKER_LOG=$(tail -n 1 logs/celery.log 2>/dev/null)
    echo "  Последняя строка: $LAST_WORKER_LOG"
else
    echo "⚠️  logs/celery.log не найден"
fi

# Проверка логов Beat
if [ -f "/var/log/celery/beat.log" ]; then
    echo "✓ /var/log/celery/beat.log существует"
    BEAT_SIZE=$(ls -lh /var/log/celery/beat.log | awk '{print $5}')
    echo "  Размер: $BEAT_SIZE"

    # Ищем признаки работы
    if grep -q "Scheduler: Sending due task" /var/log/celery/beat.log 2>/dev/null; then
        echo "  ✓ Beat отправляет задачи (работает)"
    else
        echo "  ⚠️  Beat не отправлял задачи (зависание?)"
    fi
else
    echo "⚠️  /var/log/celery/beat.log не найден"
fi
echo ""

echo "🔍 4. СИСТЕМНЫЕ СЕРВИСЫ"
echo "────────────────────────────────────────────────────────────────"

# Проверка systemd сервисов (если доступен)
if command -v systemctl &> /dev/null; then
    echo "Статус celery-worker.service:"
    systemctl status celery-worker.service --no-pager -l 2>&1 | head -10
    echo ""

    echo "Статус celery-beat.service:"
    systemctl status celery-beat.service --no-pager -l 2>&1 | head -10
    echo ""
else
    echo "systemd недоступен (Docker/WSL?)"
fi

echo "⚙️  5. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ"
echo "────────────────────────────────────────────────────────────────"

if [ -f ".env" ]; then
    echo "MAX_QUEUE_SIZE:          $(grep MAX_QUEUE_SIZE .env 2>/dev/null || echo 'НЕ УСТАНОВЛЕНО')"
    echo "POLL_INTERVAL_MINUTES:   $(grep POLL_INTERVAL_MINUTES .env 2>/dev/null || echo 'НЕ УСТАНОВЛЕНО')"
    echo "REDIS_HOST:              $(grep -E '^REDIS_HOST=' .env 2>/dev/null || echo 'НЕ УСТАНОВЛЕНО')"
else
    echo "⚠️  .env файл не найден"
fi
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "💡 РЕКОМЕНДАЦИИ"
echo "════════════════════════════════════════════════════════════════"
echo ""

if [ $WORKER_COUNT -eq 0 ]; then
    echo "🔴 КРИТИЧНО: Запустите Celery Workers:"
    echo ""
    echo "   Вариант 1 (systemd):"
    echo "   sudo systemctl start celery-worker.service"
    echo ""
    echo "   Вариант 2 (вручную для теста):"
    echo "   cd /var/www/printer-inventory"
    echo "   source .venv/bin/activate"
    echo "   ./start_workers.sh"
    echo ""
fi

if [ "$LOW_PRI" != "ERROR" ] && [ "$LOW_PRI" -gt 20000 ]; then
    echo "🟡 РЕКОМЕНДУЕТСЯ: Очистить переполненную очередь:"
    echo ""
    echo "   cd /var/www/printer-inventory"
    echo "   bash clear_queues.sh"
    echo ""
fi

if [ $BEAT_COUNT -gt 1 ]; then
    echo "🟡 РЕКОМЕНДУЕТСЯ: Остановить дублирующие процессы Beat:"
    echo ""
    echo "   sudo pkill -9 -f 'celery.*beat'"
    echo "   sudo systemctl restart celery-beat.service"
    echo ""
fi

echo "📋 ПОРЯДОК ДЕЙСТВИЙ:"
echo "────────────────────────────────────────────────────────────────"
echo "1. Остановите всё:"
echo "   sudo systemctl stop celery-worker.service celery-beat.service"
echo "   sudo pkill -9 -f celery"
echo ""
echo "2. Очистите очередь (если > 20,000 задач):"
echo "   bash clear_queues.sh"
echo ""
echo "3. Запустите сервисы:"
echo "   sudo systemctl start celery-worker.service"
echo "   sudo systemctl start celery-beat.service"
echo ""
echo "4. Проверьте через 1 минуту:"
echo "   bash $0"
echo ""
echo "════════════════════════════════════════════════════════════════"
