import json
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache, caches
from django.conf import settings
from django.utils import timezone
import redis


class Command(BaseCommand):
    help = "Управление Redis: мониторинг, очистка кэша, статистика"

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            choices=['status', 'clear', 'stats', 'keys', 'test', 'info'],
            required=True,
            help='Действие для выполнения'
        )
        parser.add_argument(
            '--cache',
            default='default',
            help='Имя кэша (default, sessions, inventory)'
        )
        parser.add_argument(
            '--pattern',
            default='*',
            help='Паттерн для поиска ключей'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Лимит для вывода ключей'
        )

    def handle(self, *args, **options):
        action = options['action']
        cache_name = options['cache']

        try:
            if action == 'status':
                self.show_status(cache_name)
            elif action == 'clear':
                self.clear_cache(cache_name)
            elif action == 'stats':
                self.show_stats(cache_name)
            elif action == 'keys':
                self.show_keys(cache_name, options['pattern'], options['limit'])
            elif action == 'test':
                self.test_redis(cache_name)
            elif action == 'info':
                self.show_redis_info(cache_name)
        except Exception as e:
            raise CommandError(f"Ошибка выполнения команды: {e}")

    def get_redis_client(self, cache_name):
        """Получить Redis клиент для указанного кэша"""
        try:
            cache_instance = caches[cache_name]
            return cache_instance._cache.get_client(None)
        except Exception as e:
            raise CommandError(f"Не удалось подключиться к Redis кэшу '{cache_name}': {e}")

    def show_status(self, cache_name):
        """Показать статус подключения к Redis"""
        self.stdout.write(self.style.SUCCESS(f"=== Статус Redis кэша '{cache_name}' ==="))

        try:
            redis_client = self.get_redis_client(cache_name)

            # Проверяем подключение
            pong = redis_client.ping()
            self.stdout.write(f"Подключение: {'OK' if pong else 'FAILED'}")

            # Информация о сервере
            info = redis_client.info()
            self.stdout.write(f"Redis версия: {info.get('redis_version')}")
            self.stdout.write(f"Режим: {info.get('redis_mode', 'standalone')}")
            self.stdout.write(f"Время работы: {info.get('uptime_in_seconds', 0)} секунд")
            self.stdout.write(f"Подключённые клиенты: {info.get('connected_clients', 0)}")

            # Память
            used_memory = info.get('used_memory_human', 'N/A')
            max_memory = info.get('maxmemory_human', 'N/A')
            self.stdout.write(f"Используемая память: {used_memory}")
            if max_memory != '0B':
                self.stdout.write(f"Максимальная память: {max_memory}")

            # Количество ключей
            db_info = redis_client.info('keyspace')
            total_keys = 0
            for db_name, db_data in db_info.items():
                if db_name.startswith('db'):
                    keys_count = db_data.get('keys', 0)
                    total_keys += keys_count
                    self.stdout.write(f"База {db_name}: {keys_count} ключей")

            self.stdout.write(f"Общее количество ключей: {total_keys}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения статуса: {e}"))

    def clear_cache(self, cache_name):
        """Очистить кэш"""
        self.stdout.write(f"Очистка кэша '{cache_name}'...")

        try:
            cache_instance = caches[cache_name]
            cache_instance.clear()
            self.stdout.write(self.style.SUCCESS(f"Кэш '{cache_name}' очищен"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка очистки кэша: {e}"))

    def show_stats(self, cache_name):
        """Показать статистику кэша"""
        self.stdout.write(self.style.SUCCESS(f"=== Статистика Redis кэша '{cache_name}' ==="))

        try:
            redis_client = self.get_redis_client(cache_name)

            # Общая статистика
            info = redis_client.info()
            stats = redis_client.info('stats')

            self.stdout.write(f"Общие команды: {stats.get('total_commands_processed', 0)}")
            self.stdout.write(f"Операций в секунду: {stats.get('instantaneous_ops_per_sec', 0)}")
            self.stdout.write(f"Попаданий в кэш: {stats.get('keyspace_hits', 0)}")
            self.stdout.write(f"Промахов кэша: {stats.get('keyspace_misses', 0)}")

            # Вычисляем hit rate
            hits = stats.get('keyspace_hits', 0)
            misses = stats.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            self.stdout.write(f"Hit Rate: {hit_rate:.2f}%")

            # Память
            self.stdout.write(f"Используемая память: {info.get('used_memory_human')}")
            self.stdout.write(f"Пиковая память: {info.get('used_memory_peak_human')}")

            # Клиенты
            self.stdout.write(f"Подключённые клиенты: {info.get('connected_clients')}")
            self.stdout.write(f"Заблокированные клиенты: {info.get('blocked_clients')}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения статистики: {e}"))

    def show_keys(self, cache_name, pattern, limit):
        """Показать ключи в кэше"""
        self.stdout.write(f"Ключи в кэше '{cache_name}' (паттерн: {pattern}, лимит: {limit}):")

        try:
            redis_client = self.get_redis_client(cache_name)

            # Получаем ключи
            keys = redis_client.keys(pattern)
            total_keys = len(keys)

            self.stdout.write(f"Найдено ключей: {total_keys}")

            # Показываем ограниченное количество
            for i, key in enumerate(keys[:limit]):
                key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)

                # Получаем информацию о ключе
                key_type = redis_client.type(key).decode('utf-8')
                ttl = redis_client.ttl(key)
                ttl_str = f"{ttl}s" if ttl > 0 else "постоянный" if ttl == -1 else "истёк"

                # Размер ключа
                try:
                    memory_usage = redis_client.memory_usage(key)
                    size_str = f"{memory_usage} bytes"
                except:
                    size_str = "N/A"

                self.stdout.write(f"  {i + 1:3d}. {key_str} [{key_type}] TTL: {ttl_str}, Size: {size_str}")

            if total_keys > limit:
                self.stdout.write(f"... и ещё {total_keys - limit} ключей")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения ключей: {e}"))

    def test_redis(self, cache_name):
        """Тестировать работу Redis"""
        self.stdout.write(f"Тестирование кэша '{cache_name}'...")

        try:
            cache_instance = caches[cache_name]

            # Тест записи/чтения
            test_key = f'test_key_{timezone.now().timestamp()}'
            test_value = {
                'message': 'Redis test',
                'timestamp': timezone.now().isoformat(),
                'number': 42
            }

            self.stdout.write("1. Тест записи...")
            cache_instance.set(test_key, test_value, timeout=60)

            self.stdout.write("2. Тест чтения...")
            retrieved_value = cache_instance.get(test_key)

            if retrieved_value == test_value:
                self.stdout.write(self.style.SUCCESS("✓ Тест чтения/записи успешен"))
            else:
                self.stdout.write(self.style.ERROR("✗ Ошибка в тесте чтения/записи"))
                return

            # Тест TTL
            self.stdout.write("3. Тест TTL...")
            cache_instance.set(test_key, test_value, timeout=1)
            import time
            time.sleep(2)
            expired_value = cache_instance.get(test_key)

            if expired_value is None:
                self.stdout.write(self.style.SUCCESS("✓ Тест TTL успешен"))
            else:
                self.stdout.write(self.style.WARNING("? TTL может не работать корректно"))

            # Тест удаления
            self.stdout.write("4. Тест удаления...")
            cache_instance.set(test_key, test_value, timeout=60)
            cache_instance.delete(test_key)
            deleted_value = cache_instance.get(test_key)

            if deleted_value is None:
                self.stdout.write(self.style.SUCCESS("✓ Тест удаления успешен"))
            else:
                self.stdout.write(self.style.ERROR("✗ Ошибка в тесте удаления"))

            self.stdout.write(self.style.SUCCESS("Все тесты завершены"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка тестирования: {e}"))

    def show_redis_info(self, cache_name):
        """Показать подробную информацию о Redis"""
        self.stdout.write(self.style.SUCCESS(f"=== Подробная информация Redis '{cache_name}' ==="))

        try:
            redis_client = self.get_redis_client(cache_name)

            # Получаем все секции info
            sections = ['server', 'clients', 'memory', 'persistence', 'stats', 'replication', 'cpu']

            for section in sections:
                self.stdout.write(f"\n--- {section.upper()} ---")
                info = redis_client.info(section)

                for key, value in info.items():
                    if isinstance(value, (int, float)):
                        if key.endswith('_human'):
                            continue  # пропускаем human-readable дубликаты
                        if key.endswith('_time') and isinstance(value, int):
                            # Преобразуем timestamp в читаемый формат
                            try:
                                from datetime import datetime
                                dt = datetime.fromtimestamp(value)
                                value = f"{value} ({dt.strftime('%Y-%m-%d %H:%M:%S')})"
                            except:
                                pass

                    self.stdout.write(f"  {key}: {value}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения информации: {e}"))