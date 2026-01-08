#!/bin/bash

echo "========================================================================"
echo "🚨 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ CELERY"
echo "========================================================================"
echo ""

echo "Проблемы:"
echo "  ❌ Процессы множатся при restart (46 процессов!)"
echo "  ❌ Очередь не уменьшается (19,240 задач)"
echo "  ❌ Дубликаты celery-beat.service"
echo ""
echo "Решение:"
echo "  1. Полностью остановить все Celery процессы"
echo "  2. Удалить дубликат celery-beat.service"
echo "  3. Исправить systemd конфигурацию"
echo "  4. Запустить заново с правильными настройками"
echo ""

read -p "Продолжить? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено."
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 1: Остановка всех Celery процессов"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Останавливаем systemd сервисы
echo "Останавливаем systemd сервисы..."
sudo systemctl stop celery-worker.service celery-beat.service 2>/dev/null || true
sleep 2

# Считаем процессы ПЕРЕД
BEFORE=$(ps aux | grep -E "celery" | grep -v grep | wc -l)
echo "Процессов Celery: $BEFORE"

# Убиваем все процессы celery
echo "Принудительное завершение всех Celery процессов..."
sudo pkill -9 -f celery 2>/dev/null || true
sleep 3

# Считаем процессы ПОСЛЕ
AFTER=$(ps aux | grep -E "celery" | grep -v grep | wc -l)

if [ "$AFTER" -eq 0 ]; then
    echo "✅ Все процессы Celery остановлены ($BEFORE → $AFTER)"
else
    echo "⚠️  Остались процессы: $AFTER"
    ps aux | grep celery | grep -v grep
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 2: Проверка systemd конфигурации"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Проверяем файлы celery-beat
echo "Проверка celery-beat файлов..."
ls -la /etc/systemd/system/celery-beat* 2>/dev/null || echo "  (нет файлов)"

BEAT_COUNT=$(ls /etc/systemd/system/celery-beat* 2>/dev/null | wc -l)

if [ "$BEAT_COUNT" -gt 1 ]; then
    echo ""
    echo "❌ Найдено $BEAT_COUNT файлов celery-beat!"
    echo ""
    echo "Файлы:"
    ls -la /etc/systemd/system/celery-beat*
    echo ""
    echo "Какой файл оставить?"
    echo "  1) celery-beat.service (первый)"
    echo "  2) Второй файл"
    echo "  3) Удалить оба и создать новый"
    read -p "Выберите (1-3): " choice

    case $choice in
        3)
            echo "Удаляем оба файла..."
            sudo rm -f /etc/systemd/system/celery-beat*.service
            echo "✅ Удалены"
            ;;
        *)
            echo "Оставляем как есть. ВАЖНО: удалите дубликаты вручную!"
            ;;
    esac
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 3: Исправление celery-worker.service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

WORKER_FILE="/etc/systemd/system/celery-worker.service"

if grep -q "KillMode=process" "$WORKER_FILE" 2>/dev/null; then
    echo "⚠️  Найдена проблема: KillMode=process"
    echo "   Это НЕ УБИВАЕТ дочерние процессы celery!"
    echo ""
    echo "Исправляем на KillMode=mixed..."

    sudo sed -i 's/KillMode=process/KillMode=mixed/' "$WORKER_FILE"

    if grep -q "KillMode=mixed" "$WORKER_FILE"; then
        echo "✅ Исправлено!"
    else
        echo "❌ Ошибка исправления. Исправьте вручную:"
        echo "   sudo nano $WORKER_FILE"
        echo "   Измените: KillMode=process → KillMode=mixed"
    fi
else
    echo "✅ KillMode корректный"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 4: Перезагрузка systemd"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Перезагружаем systemd конфигурацию..."
sudo systemctl daemon-reload
echo "✅ Готово"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 5: Запуск сервисов"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Запускаем celery-worker.service..."
sudo systemctl start celery-worker.service
sleep 5

echo "Запускаем celery-beat.service..."
sudo systemctl start celery-beat.service
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ШАГ 6: Проверка результата"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Проверка процессов
WORKERS=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)
BEAT=$(ps aux | grep "celery.*beat" | grep -v grep | wc -l)
TOTAL=$(ps aux | grep celery | grep -v grep | wc -l)

echo "Запущено процессов:"
echo "  Workers: $WORKERS"
echo "  Beat:    $BEAT"
echo "  Всего:   $TOTAL"
echo ""

if [ "$WORKERS" -gt 0 ] && [ "$BEAT" -gt 0 ]; then
    echo "✅ Сервисы запущены!"
else
    echo "❌ Проблема при запуске!"
    echo ""
    echo "Проверьте статус:"
    echo "  sudo systemctl status celery-worker.service"
    echo "  sudo systemctl status celery-beat.service"
    exit 1
fi

# Размер очереди
QUEUE=$(redis-cli -n 3 LLEN low_priority 2>/dev/null || echo "N/A")
echo "Очередь low_priority: $(printf "%'d" $QUEUE 2>/dev/null || echo $QUEUE)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📊 Следующие шаги:"
echo ""
echo "1. Мониторинг очереди (5 минут):"
echo "   watch -n 5 'redis-cli -n 3 LLEN low_priority'"
echo ""
echo "2. Проверка логов:"
echo "   tail -f logs/celery.log"
echo "   sudo journalctl -u celery-worker -f"
echo ""
echo "3. Если очередь НЕ уменьшается - увеличьте concurrency:"
echo "   nano start_workers.sh"
echo "   # Найдите low_priority worker"
echo "   # Измените: --concurrency=2 на --concurrency=4"
echo "   sudo systemctl restart celery-worker.service"
echo ""
echo "4. Тест повторного restart (через 2 минуты):"
echo "   sudo systemctl restart celery-worker.service"
echo "   ./diagnose_workers.sh"
echo "   # Количество процессов НЕ должно расти!"
echo ""

echo "========================================================================"
