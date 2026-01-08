#!/usr/bin/env python
"""
Тест защиты от переполнения очереди Celery
Запускает задачи вручную и показывает результат
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')
django.setup()

import redis
from django.conf import settings
from inventory.tasks import cleanup_queue_if_needed, inventory_daemon_task
from django.db.models import Q
from inventory.models import Printer

def check_redis_connection():
    """Проверка подключения к Redis"""
    try:
        redis_url = settings.CACHES['default']['LOCATION']
        redis_host = redis_url.split(':')[0].replace('redis://', '')
        redis_port = int(redis_url.split(':')[1].split('/')[0])
        redis_client = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            db=3,
            decode_responses=True
        )
        redis_client.ping()
        return redis_client
    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
        return None

def get_queue_size(redis_client):
    """Получить размер очереди"""
    return redis_client.llen('low_priority')

def main():
    print("=" * 80)
    print("ТЕСТ ЗАЩИТЫ ОТ ПЕРЕПОЛНЕНИЯ ОЧЕРЕДИ CELERY")
    print("=" * 80)
    print()

    # 1. Проверка Redis
    print("📡 1. Проверка подключения к Redis...")
    redis_client = check_redis_connection()
    if not redis_client:
        return
    print("   ✅ Redis подключен")
    print()

    # 2. Текущий размер очереди
    print("📊 2. Текущий размер очереди:")
    current_size = get_queue_size(redis_client)
    print(f"   low_priority: {current_size:,} задач")
    print()

    # 3. Проверка MAX_QUEUE_SIZE
    print("⚙️  3. Проверка переменной MAX_QUEUE_SIZE:")
    max_queue_size = int(os.getenv('MAX_QUEUE_SIZE', '10000'))
    print(f"   MAX_QUEUE_SIZE = {max_queue_size:,}")
    print()

    # 4. Проверка количества принтеров
    print("🖨️  4. Проверка принтеров:")

    # Все принтеры
    all_printers = Printer.objects.all().count()
    print(f"   Всего принтеров: {all_printers:,}")

    # Принтеры из активных организаций
    active_printers = Printer.objects.filter(
        Q(organization__active=True) | Q(organization__isnull=True)
    ).count()
    print(f"   В активных организациях: {active_printers:,}")

    filtered_out = all_printers - active_printers
    if filtered_out > 0:
        print(f"   Отфильтровано (неактивные): {filtered_out:,}")
    print()

    # 5. Тест задачи cleanup_queue_if_needed
    print("🧹 5. Тест задачи cleanup_queue_if_needed:")
    print("   Запускаем...")

    try:
        result = cleanup_queue_if_needed()
        print(f"   Результат: {result}")

        if result.get('cleaned'):
            print(f"   ✅ ОЧИСТКА ВЫПОЛНЕНА!")
            print(f"      Удалено задач: {result['removed_tasks']:,}")
            print(f"      Размер до: {result['queue_size_before']:,}")
            print(f"      Размер после: {result['queue_size_after']:,}")
        else:
            print(f"   ✓ Очистка не требуется (очередь < {max_queue_size * 2:,})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    print()

    # 6. Проверка размера после cleanup
    size_after_cleanup = get_queue_size(redis_client)
    print("📊 6. Размер очереди после cleanup:")
    print(f"   low_priority: {size_after_cleanup:,} задач")
    print()

    # 7. Тест задачи inventory_daemon_task (без реального запуска)
    print("🔍 7. Проверка защиты в inventory_daemon_task:")

    if size_after_cleanup > max_queue_size:
        print(f"   ⚠️  Очередь переполнена ({size_after_cleanup:,} > {max_queue_size:,})")
        print(f"   Daemon НЕ должен создавать новые задачи")
        print()
        print("   Запустить daemon для проверки? (он не создаст задачи)")
        print("   ВНИМАНИЕ: Это создаст записи в БД о попытке запуска")

        response = input("   Запустить? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            print()
            print("   Запускаем inventory_daemon_task...")
            try:
                result = inventory_daemon_task()
                print(f"   Результат: {result}")

                if result.get('success') == False and 'overflow' in result.get('error', '').lower():
                    print(f"   ✅ ЗАЩИТА СРАБОТАЛА! Задачи не созданы")
                    print(f"      Размер очереди: {result.get('queue_size', 'N/A'):,}")
                elif result.get('success') == True:
                    print(f"   ⚠️  Daemon создал задачи:")
                    print(f"      Создано задач: {result.get('queued_tasks', 0)}")
                    print(f"      Очередь до: {result.get('previous_queue_size', 0):,}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("   Пропущено")
    else:
        print(f"   ✓ Очередь в норме ({size_after_cleanup:,} <= {max_queue_size:,})")
        print(f"   Daemon может создавать задачи")
    print()

    # 8. Финальный размер очереди
    final_size = get_queue_size(redis_client)
    print("=" * 80)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 80)
    print(f"Размер очереди в начале:  {current_size:,} задач")
    print(f"Размер очереди в конце:   {final_size:,} задач")

    if final_size < current_size:
        print(f"✅ Очередь уменьшилась на {current_size - final_size:,} задач")
    elif final_size > current_size:
        print(f"⚠️  Очередь увеличилась на {final_size - current_size:,} задач")
    else:
        print(f"→ Размер очереди не изменился")

    print()
    print(f"MAX_QUEUE_SIZE:           {max_queue_size:,}")
    print(f"Критический порог:        {max_queue_size * 2:,}")
    print(f"Принтеров для опроса:     {active_printers:,}")
    print()

    if final_size > max_queue_size:
        print("⚠️  РЕКОМЕНДАЦИИ:")
        print(f"   - Очередь всё ещё переполнена ({final_size:,} > {max_queue_size:,})")
        print(f"   - Daemon будет пропускать запуски пока очередь не уменьшится")
        print(f"   - Workers обрабатывают задачи - очередь уменьшится со временем")
        print(f"   - Или очистите вручную: bash clear_queues.sh")
    else:
        print("✅ ЗАЩИТА РАБОТАЕТ КОРРЕКТНО!")
        print(f"   - Очередь в норме")
        print(f"   - Daemon может создавать новые задачи")
        print(f"   - Автоочистка будет работать если очередь вырастет")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
