#!/bin/bash

echo "========================================================================"
echo "🔍 АНАЛИЗ ОЧЕРЕДИ CELERY"
echo "========================================================================"
echo ""

QUEUE="${1:-low_priority}"
REDIS_DB="${2:-3}"

echo "Очередь: $QUEUE"
echo "Redis DB: $REDIS_DB"
echo ""

# Размер очереди
QUEUE_SIZE=$(redis-cli -n $REDIS_DB LLEN $QUEUE 2>/dev/null || echo "0")
echo "📊 Размер очереди: $(printf "%'d" $QUEUE_SIZE)"
echo ""

if [ "$QUEUE_SIZE" -eq 0 ]; then
    echo "✅ Очередь пустая!"
    exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ТИПЫ ЗАДАЧ В ОЧЕРЕДИ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Получаем первые 100 задач для анализа
SAMPLE_SIZE=100
if [ "$QUEUE_SIZE" -lt "$SAMPLE_SIZE" ]; then
    SAMPLE_SIZE=$QUEUE_SIZE
fi

echo "Анализируем первые $SAMPLE_SIZE задач..."
echo ""

# Временный файл для результатов
TMPFILE=$(mktemp)

# Получаем задачи и извлекаем имена
redis-cli -n $REDIS_DB LRANGE $QUEUE 0 $((SAMPLE_SIZE - 1)) | \
    grep -o '"task":"[^"]*"' | \
    sed 's/"task":"//; s/"$//' | \
    sort | uniq -c | sort -rn > $TMPFILE

# Подсчёт типов задач
TOTAL_TYPES=$(wc -l < $TMPFILE)
echo "Найдено уникальных типов задач: $TOTAL_TYPES"
echo ""

# Вывод статистики
while read count task; do
    # Подсветка GLPI задач
    if echo "$task" | grep -qi glpi; then
        echo "  🔴 $count × $task  ← GLPI ЗАДАЧА!"
    elif echo "$task" | grep -qi inventory; then
        echo "  📦 $count × $task"
    elif echo "$task" | grep -qi sync; then
        echo "  🔄 $count × $task"
    else
        echo "     $count × $task"
    fi
done < $TMPFILE

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 ПОИСК GLPI ЗАДАЧ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Поиск GLPI задач во всей очереди
GLPI_COUNT=$(redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 | grep -i glpi | wc -l)

if [ "$GLPI_COUNT" -gt 0 ]; then
    echo "✅ Найдено GLPI задач: $GLPI_COUNT"
    echo ""

    # Показываем первые 5 GLPI задач
    echo "Первые GLPI задачи:"
    echo ""

    redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 | \
        grep -i glpi | \
        head -5 | \
        python3 -c "
import sys
import json

for i, line in enumerate(sys.stdin, 1):
    try:
        data = json.loads(line)
        task_name = data.get('task', 'Unknown')
        args = data.get('args', [])
        kwargs = data.get('kwargs', {})

        print(f'{i}. {task_name}')
        if args:
            print(f'   Args: {args}')
        if kwargs:
            print(f'   Kwargs: {kwargs}')
        print()
    except:
        print(f'{i}. (ошибка парсинга)')
        print(f'   Raw: {line[:100]}...')
        print()
" 2>/dev/null || {
        # Если python парсинг не сработал - показываем сырые данные
        redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 | \
            grep -i glpi | \
            head -5 | \
            while read -r line; do
                echo "$line" | grep -o '"task":"[^"]*"' | sed 's/"task":"//; s/"$//'
            done
    }
else
    echo "❌ GLPI задач НЕ найдено"
    echo ""
    echo "Это нормально, если:"
    echo "  • GLPI интеграция не используется"
    echo "  • GLPI задачи уже обработаны"
    echo "  • GLPI задачи находятся в другой очереди"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 ДЕТАЛЬНАЯ СТАТИСТИКА"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Распределение по категориям (в выборке из $SAMPLE_SIZE):"
echo ""

# Подсчёт по категориям
INVENTORY_COUNT=$(grep -i inventory $TMPFILE | awk '{sum += $1} END {print sum+0}')
GLPI_SAMPLE_COUNT=$(grep -i glpi $TMPFILE | awk '{sum += $1} END {print sum+0}')
SYNC_COUNT=$(grep -i sync $TMPFILE | awk '{sum += $1} END {print sum+0}')
DAEMON_COUNT=$(grep -i daemon $TMPFILE | awk '{sum += $1} END {print sum+0}')

echo "  📦 Inventory задачи:  $INVENTORY_COUNT"
echo "  🔴 GLPI задачи:       $GLPI_SAMPLE_COUNT"
echo "  🔄 Sync задачи:       $SYNC_COUNT"
echo "  ⚙️  Daemon задачи:     $DAEMON_COUNT"

# Очистка
rm -f $TMPFILE

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Просмотр первой задачи в очереди:"
echo "  redis-cli -n $REDIS_DB LINDEX $QUEUE 0"
echo ""
echo "Поиск конкретного типа задачи:"
echo "  redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 | grep 'task_name'"
echo ""
echo "Очистка очереди (ОСТОРОЖНО!):"
echo "  redis-cli -n $REDIS_DB DEL $QUEUE"
echo ""
echo "========================================================================"
