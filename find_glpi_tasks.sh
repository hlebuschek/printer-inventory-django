#!/bin/bash

# Быстрый поиск GLPI задач в очереди

QUEUE="${1:-low_priority}"
REDIS_DB="${2:-3}"

echo "🔍 Поиск GLPI задач в очереди '$QUEUE'..."
echo ""

# Общее количество задач
TOTAL=$(redis-cli -n $REDIS_DB LLEN $QUEUE 2>/dev/null || echo "0")
echo "Всего задач в очереди: $(printf "%'d" $TOTAL)"

# Поиск GLPI
GLPI_COUNT=$(redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 2>/dev/null | grep -ci glpi || echo "0")

echo "GLPI задач найдено:    $GLPI_COUNT"
echo ""

if [ "$GLPI_COUNT" -eq 0 ]; then
    echo "❌ GLPI задач в очереди НЕТ"
    exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Найдены GLPI задачи! ($GLPI_COUNT шт.)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Извлекаем имена GLPI задач
echo "Типы GLPI задач:"
redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 2>/dev/null | \
    grep -i glpi | \
    grep -o '"task":"[^"]*"' | \
    sed 's/"task":"//; s/"$//' | \
    sort | uniq -c | sort -rn

echo ""
echo "Первые 3 GLPI задачи (детали):"
echo ""

redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 2>/dev/null | \
    grep -i glpi | \
    head -3 | \
    python3 -m json.tool 2>/dev/null || \
    redis-cli -n $REDIS_DB LRANGE $QUEUE 0 -1 | grep -i glpi | head -3

echo ""
