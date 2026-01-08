#!/bin/bash

echo "========================================================================"
echo "🔍 ДИАГНОСТИКА CELERY"
echo "========================================================================"
echo ""

# Проверка Redis
echo "1️⃣ Проверка Redis..."
if redis-cli -h ${REDIS_HOST:-localhost} -p ${REDIS_PORT:-6379} ping > /dev/null 2>&1; then
    echo "   ✅ Redis доступен"
else
    echo "   ❌ Redis недоступен!"
    exit 1
fi
echo ""

# Проверка размера очереди
echo "2️⃣ Размер очереди low_priority:"
QUEUE_SIZE=$(redis-cli -h ${REDIS_HOST:-localhost} -p ${REDIS_PORT:-6379} -n 3 LLEN low_priority 2>/dev/null || echo "0")
echo "   📊 Задач в очереди: $(printf "%'d" $QUEUE_SIZE)"
echo ""

# Проверка работающих workers
echo "3️⃣ Проверка Celery Workers..."
WORKER_COUNT=$(ps aux | grep -E "celery.*worker" | grep -v grep | wc -l)
if [ "$WORKER_COUNT" -gt 0 ]; then
    echo "   ✅ Запущено workers: $WORKER_COUNT"
    ps aux | grep -E "celery.*worker" | grep -v grep | awk '{print "      - "$11" "$12" "$13" "$14}'
else
    echo "   ❌ Workers НЕ ЗАПУЩЕНЫ!"
fi
echo ""

# Проверка Celery Beat
echo "4️⃣ Проверка Celery Beat..."
BEAT_COUNT=$(ps aux | grep -E "celery.*beat" | grep -v grep | wc -l)
if [ "$BEAT_COUNT" -gt 0 ]; then
    echo "   ✅ Beat запущен"
else
    echo "   ⚠️  Beat не запущен (периодические задачи не будут выполняться)"
fi
echo ""

# Рекомендации
echo "========================================================================"
echo "💡 РЕКОМЕНДАЦИИ"
echo "========================================================================"

if [ "$WORKER_COUNT" -eq 0 ]; then
    echo ""
    echo "❌ Workers не запущены! Задачи накапливаются в очереди."
    echo ""
    echo "🚀 Запустите workers:"
    echo "   ./start_workers.sh"
    echo ""
    echo "   Или в фоне:"
    echo "   nohup ./start_workers.sh > logs/celery.log 2>&1 &"
    echo ""
elif [ "$QUEUE_SIZE" -gt 20000 ]; then
    echo ""
    echo "⚠️  Очередь переполнена! Рекомендуется очистка старых задач."
    echo ""
    echo "🧹 Ручная очистка:"
    echo "   python manage.py shell"
    echo "   >>> from inventory.tasks import cleanup_queue_if_needed"
    echo "   >>> cleanup_queue_if_needed()"
    echo ""
elif [ "$QUEUE_SIZE" -gt 10000 ]; then
    echo ""
    echo "⚠️  Очередь большая, но в пределах нормы."
    echo "   Защита от переполнения работает."
    echo "   Workers обрабатывают задачи."
    echo ""
else
    echo ""
    echo "✅ Всё в порядке!"
    echo "   Очередь в норме, workers работают."
    echo ""
fi

echo "========================================================================"
