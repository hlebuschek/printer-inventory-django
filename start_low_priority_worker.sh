#!/bin/bash

echo "========================================================================"
echo "🚀 Запуск worker для low_priority очереди"
echo "========================================================================"
echo ""

# Проверяем не запущен ли уже
EXISTING=$(ps aux | grep "celery.*worker.*low_priority" | grep -v grep | wc -l)

if [ "$EXISTING" -gt 0 ]; then
    echo "⚠️  Worker для low_priority уже запущен ($EXISTING процессов)"
    echo ""
    echo "Процессы:"
    ps aux | grep "celery.*worker.*low_priority" | grep -v grep | awk '{print "   PID "$2": "$11" "$12" "$13}'
    echo ""
    echo "Хотите перезапустить? (y/N)"
    read -r response
    if [[ "$response" != "y" && "$response" != "Y" ]]; then
        echo "Отменено."
        exit 0
    fi

    echo "Останавливаем существующие процессы..."
    pkill -f "celery.*worker.*low_priority"
    sleep 2
fi

echo "Запускаем worker для low_priority..."
echo ""

celery -A printer_inventory worker \
    --queues=low_priority \
    --loglevel=INFO \
    --concurrency=2 \
    --max-tasks-per-child=200 \
    --hostname=worker_low@%h \
    --logfile=logs/celery_low.log \
    --detach

sleep 2

# Проверяем что запустился
NEW=$(ps aux | grep "celery.*worker.*low_priority" | grep -v grep | wc -l)

if [ "$NEW" -gt 0 ]; then
    echo "✅ Worker успешно запущен!"
    echo ""
    echo "Процессы:"
    ps aux | grep "celery.*worker.*low_priority" | grep -v grep | awk '{print "   PID "$2": "$11" "$12" "$13}'
    echo ""
    echo "Логи: logs/celery_low.log"
    echo ""
    echo "Размер очереди low_priority:"
    QUEUE=$(redis-cli -n 3 LLEN low_priority 2>/dev/null || echo "N/A")
    echo "   $(printf "%'d" $QUEUE 2>/dev/null || echo $QUEUE) задач"
    echo ""
    echo "Мониторинг:"
    echo "   tail -f logs/celery_low.log"
    echo "   watch -n 5 'redis-cli -n 3 LLEN low_priority'"
else
    echo "❌ Ошибка запуска!"
    echo ""
    echo "Проверьте логи:"
    echo "   tail -20 logs/celery_low.log"
fi

echo ""
echo "========================================================================"
