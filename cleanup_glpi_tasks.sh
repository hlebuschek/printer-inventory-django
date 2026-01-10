#!/bin/bash

# ============================================================================
# Скрипт для очистки застрявших GLPI задач из очереди Redis
# ============================================================================

set -e

QUEUE_NAME="low_priority"
TASK_PATTERN="check_all_devices_in_glpi"

echo "=================================================="
echo "🧹 Очистка застрявших GLPI задач"
echo "=================================================="
echo ""

# Подсчет задач до очистки
TOTAL_BEFORE=$(redis-cli -n 3 LLEN $QUEUE_NAME)
echo "📊 Всего задач в очереди '$QUEUE_NAME': $TOTAL_BEFORE"

# Подсчет GLPI задач
GLPI_COUNT=$(redis-cli -n 3 LRANGE $QUEUE_NAME 0 -1 | grep -c "$TASK_PATTERN" || echo "0")
echo "🔍 Найдено GLPI задач: $GLPI_COUNT"
echo ""

if [ "$GLPI_COUNT" -eq "0" ]; then
    echo "✓ Застрявших GLPI задач не найдено"
    exit 0
fi

# Получаем все элементы очереди
echo "🔧 Сохраняем все задачи..."
redis-cli -n 3 LRANGE $QUEUE_NAME 0 -1 > /tmp/all_tasks.txt

# Фильтруем задачи без GLPI
echo "🔧 Фильтруем задачи..."
grep -v "$TASK_PATTERN" /tmp/all_tasks.txt > /tmp/filtered_tasks.txt || true

# Подсчитываем оставшиеся задачи
REMAINING=$(wc -l < /tmp/filtered_tasks.txt)
echo "📊 Задач после фильтрации: $REMAINING"
echo ""

# Очищаем очередь
echo "🗑️  Очищаем очередь..."
redis-cli -n 3 DEL $QUEUE_NAME

# Восстанавливаем отфильтрованные задачи
if [ -s /tmp/filtered_tasks.txt ]; then
    echo "♻️  Восстанавливаем не-GLPI задачи..."
    while IFS= read -r task; do
        redis-cli -n 3 RPUSH $QUEUE_NAME "$task" > /dev/null
    done < /tmp/filtered_tasks.txt
fi

# Проверяем финальное состояние
TOTAL_AFTER=$(redis-cli -n 3 LLEN $QUEUE_NAME)
REMOVED=$((TOTAL_BEFORE - TOTAL_AFTER))

echo ""
echo "=================================================="
echo "✓ Очистка завершена"
echo "=================================================="
echo "Было задач:       $TOTAL_BEFORE"
echo "Стало задач:      $TOTAL_AFTER"
echo "Удалено:          $REMOVED"
echo "=================================================="
echo ""

# Очистка временных файлов
rm -f /tmp/all_tasks.txt /tmp/filtered_tasks.txt

echo "💡 Теперь перезапустите workers для применения изменений:"
echo "   sudo systemctl restart celery-worker*"
echo ""
