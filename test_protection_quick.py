#!/usr/bin/env python
"""
Быстрый тест защиты от переполнения очереди
Без лишнего вывода - только результат
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')
django.setup()

import redis
from django.conf import settings
from inventory.tasks import inventory_daemon_task

def test_protection():
    """Тест защиты с временным уменьшением MAX_QUEUE_SIZE"""

    # Подключаемся к Redis
    rc = redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=3,
        decode_responses=True
    )

    current_size = rc.llen('low_priority')

    print("=" * 70)
    print("БЫСТРЫЙ ТЕСТ ЗАЩИТЫ ОТ ПЕРЕПОЛНЕНИЯ")
    print("=" * 70)
    print()
    print(f"📊 Текущий размер очереди: {current_size:,} задач")
    print()

    # Временно уменьшим порог
    original_max = os.getenv('MAX_QUEUE_SIZE', '10000')
    test_max = '5000'

    os.environ['MAX_QUEUE_SIZE'] = test_max

    print(f"🧪 Тест: MAX_QUEUE_SIZE = {test_max}")
    print(f"   Очередь {current_size:,} > {test_max} → защита должна сработать")
    print()
    print("⏳ Запускаем inventory_daemon_task()...")
    print()

    # Запускаем daemon
    result = inventory_daemon_task()

    # Восстанавливаем
    os.environ['MAX_QUEUE_SIZE'] = original_max

    # Проверяем результат
    print("=" * 70)
    print("📋 РЕЗУЛЬТАТ:")
    print("=" * 70)

    if result.get('success') == False and 'overflow' in str(result.get('error', '')).lower():
        print()
        print("✅ ЗАЩИТА РАБОТАЕТ!")
        print()
        print(f"   ✓ Daemon НЕ создал новые задачи")
        print(f"   ✓ Размер очереди: {result.get('queue_size', 'N/A'):,}")
        print(f"   ✓ MAX_QUEUE_SIZE: {result.get('max_queue_size', 'N/A'):,}")
        print(f"   ✓ Причина: Queue overflow")
        print()

        # Проверяем что очередь не изменилась
        final_size = rc.llen('low_priority')
        if final_size == current_size:
            print(f"   ✓ Очередь не изменилась: {current_size:,} → {final_size:,}")
        else:
            print(f"   ⚠️  Очередь изменилась: {current_size:,} → {final_size:,}")

        print()
        print("=" * 70)
        print("✅ ТЕСТ ПРОЙДЕН!")
        print("=" * 70)
        return True

    elif result.get('success') == True:
        print()
        print("❌ ЗАЩИТА НЕ СРАБОТАЛА!")
        print()
        print(f"   ✗ Daemon создал задачи: {result.get('queued_tasks', 0)}")
        print(f"   ✗ Размер очереди до: {result.get('previous_queue_size', 0):,}")
        print()

        final_size = rc.llen('low_priority')
        print(f"   ✗ Очередь увеличилась: {current_size:,} → {final_size:,}")
        print()
        print("=" * 70)
        print("❌ ТЕСТ НЕ ПРОЙДЕН!")
        print("=" * 70)
        return False
    else:
        print()
        print("⚠️  НЕОЖИДАННЫЙ РЕЗУЛЬТАТ:")
        print(f"   {result}")
        print()
        return False

if __name__ == '__main__':
    test_protection()
