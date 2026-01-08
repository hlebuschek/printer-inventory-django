#!/bin/bash

echo "========================================================================"
echo "🔍 ДИАГНОСТИКА CELERY WORKERS"
echo "========================================================================"
echo ""

echo "1️⃣ Запущенные workers по очередям:"
echo ""

HIGH=$(ps aux | grep "celery.*worker.*high_priority" | grep -v grep | wc -l)
LOW=$(ps aux | grep "celery.*worker.*low_priority" | grep -v grep | wc -l)
DAEMON=$(ps aux | grep "celery.*worker.*daemon" | grep -v grep | wc -l)
TOTAL=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)

echo "   high_priority: $HIGH процессов"
echo "   low_priority:  $LOW процессов  ← ДОЛЖНО БЫТЬ 2+"
echo "   daemon:        $DAEMON процессов"
echo "   ─────────────────────────"
echo "   ВСЕГО:         $TOTAL процессов"
echo ""

if [ "$LOW" -eq 0 ]; then
    echo "❌ КРИТИЧЕСКАЯ ПРОБЛЕМА!"
    echo "   Worker для low_priority НЕ ЗАПУЩЕН!"
    echo "   Задачи накапливаются в очереди без обработки!"
    echo ""
fi

echo "2️⃣ Размер очередей в Redis:"
echo ""

REDIS_HIGH=$(redis-cli -n 3 LLEN high_priority 2>/dev/null || echo "N/A")
REDIS_LOW=$(redis-cli -n 3 LLEN low_priority 2>/dev/null || echo "N/A")
REDIS_DAEMON=$(redis-cli -n 3 LLEN daemon 2>/dev/null || echo "N/A")

echo "   high_priority: $(printf "%'d" $REDIS_HIGH 2>/dev/null || echo $REDIS_HIGH)"
echo "   low_priority:  $(printf "%'d" $REDIS_LOW 2>/dev/null || echo $REDIS_LOW)"
echo "   daemon:        $(printf "%'d" $REDIS_DAEMON 2>/dev/null || echo $REDIS_DAEMON)"
echo ""

echo "3️⃣ Celery Beat (планировщик):"
echo ""

BEAT=$(ps aux | grep "celery.*beat" | grep -v grep | wc -l)
if [ "$BEAT" -gt 0 ]; then
    echo "   ✅ Beat запущен ($BEAT процесс)"
else
    echo "   ⚠️  Beat НЕ запущен"
fi
echo ""

echo "========================================================================"
echo "💡 РЕШЕНИЕ"
echo "========================================================================"
echo ""

if [ "$LOW" -eq 0 ]; then
    echo "🚨 СРОЧНО: Запустите worker для low_priority очереди!"
    echo ""
    echo "Вариант 1: Перезапустить всё"
    echo "   pkill -f celery"
    echo "   ./start_workers.sh"
    echo ""
    echo "Вариант 2: Запустить только low_priority worker"
    echo "   celery -A printer_inventory worker \\"
    echo "       --queues=low_priority \\"
    echo "       --loglevel=INFO \\"
    echo "       --concurrency=2 \\"
    echo "       --max-tasks-per-child=200 \\"
    echo "       --hostname=worker_low@%h &"
    echo ""
elif [ "$TOTAL" -gt 50 ]; then
    echo "⚠️  Слишком много процессов ($TOTAL)!"
    echo "   Рекомендуется перезапуск:"
    echo ""
    echo "   pkill -f celery"
    echo "   ./start_workers.sh"
    echo ""
else
    echo "✅ Workers в порядке!"
fi

echo "========================================================================"
