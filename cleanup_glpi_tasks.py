#!/usr/bin/env python3
"""
Скрипт для очистки застрявших GLPI задач из очереди Redis.

Использование:
    python cleanup_glpi_tasks.py [--dry-run]

    --dry-run: Показать что будет удалено, но не удалять
"""

import sys
import json
import argparse
import redis

# Настройки Redis для Celery
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 3  # Celery broker DB
QUEUE_NAME = "low_priority"
TASK_PATTERN="check_all_devices_in_glpi"


def parse_task(task_data):
    """Парсит JSON задачи из Redis"""
    try:
        task = json.loads(task_data)
        task_name = task.get("headers", {}).get("task", "")
        task_id = task.get("headers", {}).get("id", "")
        retries = task.get("headers", {}).get("retries", 0)
        eta = task.get("headers", {}).get("eta", "")
        return {"name": task_name, "id": task_id, "retries": retries, "eta": eta, "raw": task_data}
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Очистка застрявших GLPI задач")
    parser.add_argument("--dry-run", action="store_true", help="Показать что будет удалено, но не удалять")
    args = parser.parse_args()

    print("=" * 70)
    print("🧹 ОЧИСТКА ЗАСТРЯВШИХ GLPI ЗАДАЧ")
    print("=" * 70)
    print()

    # Подключаемся к Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r.ping()
        print(f"✓ Подключение к Redis: {REDIS_HOST}:{REDIS_PORT} (DB {REDIS_DB})")
    except Exception as e:
        print(f"✗ Ошибка подключения к Redis: {e}")
        sys.exit(1)

    # Получаем все задачи из очереди
    total_tasks = r.llen(QUEUE_NAME)
    print(f"📊 Всего задач в очереди '{QUEUE_NAME}': {total_tasks}")
    print()

    if total_tasks == 0:
        print("✓ Очередь пуста")
        return

    # Анализируем задачи
    print("🔍 Анализ задач...")
    all_tasks = r.lrange(QUEUE_NAME, 0, -1)

    glpi_tasks = []
    other_tasks = []

    for task_data in all_tasks:
        task_info = parse_task(task_data)
        if task_info and TASK_PATTERN in task_info["name"]:
            glpi_tasks.append(task_info)
        else:
            other_tasks.append(task_data)

    print(f"   Найдено GLPI задач: {len(glpi_tasks)}")
    print(f"   Других задач:       {len(other_tasks)}")
    print()

    if len(glpi_tasks) == 0:
        print("✓ Застрявших GLPI задач не найдено")
        return

    # Показываем детали GLPI задач
    print("📋 Детали GLPI задач:")
    print("-" * 70)
    for i, task in enumerate(glpi_tasks, 1):
        print(f"{i}. ID: {task['id']}")
        print(f"   Имя: {task['name']}")
        print(f"   Попыток: {task['retries']}")
        print(f"   ETA: {task['eta']}")
        print()

    if args.dry_run:
        print("⚠️  DRY-RUN режим: задачи НЕ будут удалены")
        print()
        print(f"Будет удалено: {len(glpi_tasks)} задач")
        print(f"Останется:     {len(other_tasks)} задач")
        return

    # Запрашиваем подтверждение
    print("⚠️  Внимание! Эта операция удалит застрявшие GLPI задачи.")
    confirm = input(f"Удалить {len(glpi_tasks)} задач? (yes/no): ")

    if confirm.lower() not in ["yes", "y", "да"]:
        print("❌ Отменено пользователем")
        return

    print()
    print("🗑️  Очистка очереди...")

    # Удаляем старую очередь
    r.delete(QUEUE_NAME)

    # Восстанавливаем не-GLPI задачи
    if other_tasks:
        print(f"♻️  Восстановление {len(other_tasks)} задач...")
        for task_data in other_tasks:
            r.rpush(QUEUE_NAME, task_data)

    # Проверяем результат
    final_count = r.llen(QUEUE_NAME)
    removed = total_tasks - final_count

    print()
    print("=" * 70)
    print("✓ ОЧИСТКА ЗАВЕРШЕНА")
    print("=" * 70)
    print(f"Было задач:    {total_tasks}")
    print(f"Стало задач:   {final_count}")
    print(f"Удалено:       {removed}")
    print("=" * 70)
    print()
    print("💡 Рекомендации:")
    print("   1. Перезапустите workers: sudo systemctl restart celery-worker*")
    print("   2. Проверьте логи workers после перезапуска")
    print("   3. Задача будет выполнена автоматически в 02:00 по расписанию")
    print()


if __name__ == "__main__":
    main()
