import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from celery import current_app
from celery.events.state import State
from celery.events import EventReceiver


class Command(BaseCommand):
    help = "Мониторинг и управление Celery задачами"

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            choices=['status', 'active', 'stats', 'queues', 'workers', 'inspect', 'purge'],
            required=True,
            help='Действие для выполнения'
        )
        parser.add_argument(
            '--queue',
            help='Имя очереди для операций'
        )
        parser.add_argument(
            '--worker',
            help='Имя воркера для операций'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Лимит для вывода задач'
        )

    def handle(self, *args, **options):
        action = options['action']

        try:
            if action == 'status':
                self.show_status()
            elif action == 'active':
                self.show_active_tasks(options['limit'])
            elif action == 'stats':
                self.show_stats()
            elif action == 'queues':
                self.show_queues()
            elif action == 'workers':
                self.show_workers()
            elif action == 'inspect':
                self.inspect_workers(options['worker'])
            elif action == 'purge':
                self.purge_queue(options['queue'])
        except Exception as e:
            raise CommandError(f"Ошибка выполнения команды: {e}")

    def get_celery_app(self):
        """Получить экземпляр Celery приложения"""
        return current_app

    def show_status(self):
        """Показать общий статус Celery"""
        self.stdout.write(self.style.SUCCESS("=== Статус Celery ==="))

        try:
            app = self.get_celery_app()

            # Проверяем подключение к брокеру
            try:
                inspect = app.control.inspect()
                stats = inspect.stats()
                if stats:
                    self.stdout.write("Подключение к брокеру: OK")
                    self.stdout.write(f"Активных воркеров: {len(stats)}")
                else:
                    self.stdout.write(self.style.WARNING("Воркеры не найдены"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка подключения к брокеру: {e}"))
                return

            # Информация о конфигурации
            self.stdout.write(f"Брокер: {app.conf.broker_url}")
            self.stdout.write(f"Backend результатов: {app.conf.result_backend}")
            self.stdout.write(f"Часовой пояс: {app.conf.timezone}")

            # Информация об очередях
            try:
                active_queues = inspect.active_queues()
                if active_queues:
                    total_queues = sum(len(queues) for queues in active_queues.values())
                    self.stdout.write(f"Активных очередей: {total_queues}")
            except Exception as e:
                self.stdout.write(f"Не удалось получить информацию об очередях: {e}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения статуса: {e}"))

    def show_active_tasks(self, limit):
        """Показать активные задачи"""
        self.stdout.write(self.style.SUCCESS(f"=== Активные задачи (лимит: {limit}) ==="))

        try:
            app = self.get_celery_app()
            inspect = app.control.inspect()

            active_tasks = inspect.active()
            if not active_tasks:
                self.stdout.write("Активных задач не найдено")
                return

            task_count = 0
            for worker, tasks in active_tasks.items():
                self.stdout.write(f"\nВоркер: {worker}")
                self.stdout.write(f"Задач: {len(tasks)}")

                for task in tasks[:limit]:
                    task_count += 1
                    task_id = task.get('id', 'N/A')
                    task_name = task.get('name', 'N/A')
                    task_args = task.get('args', [])
                    task_kwargs = task.get('kwargs', {})
                    time_start = task.get('time_start')

                    self.stdout.write(f"  {task_count}. {task_name}")
                    self.stdout.write(f"     ID: {task_id}")
                    self.stdout.write(f"     Args: {task_args}")
                    if task_kwargs:
                        self.stdout.write(f"     Kwargs: {task_kwargs}")
                    if time_start:
                        self.stdout.write(f"     Запущена: {time_start}")

                    if task_count >= limit:
                        break

                if task_count >= limit:
                    break

            self.stdout.write(
                f"\nОбщее количество активных задач: {sum(len(tasks) for tasks in active_tasks.values())}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения активных задач: {e}"))

    def show_stats(self):
        """Показать статистику Celery"""
        self.stdout.write(self.style.SUCCESS("=== Статистика Celery ==="))

        try:
            app = self.get_celery_app()
            inspect = app.control.inspect()

            # Статистика воркеров
            stats = inspect.stats()
            if not stats:
                self.stdout.write("Статистика недоступна")
                return

            total_completed = 0
            total_failed = 0

            for worker, worker_stats in stats.items():
                self.stdout.write(f"\nВоркер: {worker}")

                # Основная статистика
                if 'total' in worker_stats:
                    total_tasks = worker_stats['total']
                    total_completed += total_tasks.get('completed', 0)
                    total_failed += total_tasks.get('failed', 0)

                    self.stdout.write(f"  Выполнено задач: {total_tasks.get('completed', 0)}")
                    self.stdout.write(f"  Провалено задач: {total_tasks.get('failed', 0)}")

                # Пул воркеров
                if 'pool' in worker_stats:
                    pool = worker_stats['pool']
                    self.stdout.write(f"  Процессов в пуле: {pool.get('max-concurrency', 'N/A')}")
                    self.stdout.write(f"  Процессов активно: {pool.get('processes', 'N/A')}")

                # Время работы
                if 'clock' in worker_stats:
                    self.stdout.write(f"  Время работы: {worker_stats['clock']} секунд")

            # Общая статистика
            self.stdout.write(f"\nОбщая статистика:")
            self.stdout.write(f"  Всего выполнено: {total_completed}")
            self.stdout.write(f"  Всего провалено: {total_failed}")
            if total_completed + total_failed > 0:
                success_rate = (total_completed / (total_completed + total_failed)) * 100
                self.stdout.write(f"  Успешность: {success_rate:.2f}%")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения статистики: {e}"))

    def show_queues(self):
        """Показать информацию об очередях"""
        self.stdout.write(self.style.SUCCESS("=== Очереди Celery ==="))

        try:
            app = self.get_celery_app()
            inspect = app.control.inspect()

            # Активные очереди
            active_queues = inspect.active_queues()
            if not active_queues:
                self.stdout.write("Активных очередей не найдено")
                return

            for worker, queues in active_queues.items():
                self.stdout.write(f"\nВоркер: {worker}")

                for queue in queues:
                    queue_name = queue.get('name', 'N/A')
                    exchange = queue.get('exchange', {})
                    routing_key = queue.get('routing_key', 'N/A')

                    self.stdout.write(f"  Очередь: {queue_name}")
                    self.stdout.write(f"    Routing key: {routing_key}")
                    if exchange:
                        self.stdout.write(f"    Exchange: {exchange.get('name', 'N/A')}")

            # Зарезервированные задачи
            try:
                reserved = inspect.reserved()
                if reserved:
                    self.stdout.write(f"\nЗарезервированные задачи:")
                    for worker, tasks in reserved.items():
                        if tasks:
                            self.stdout.write(f"  {worker}: {len(tasks)} задач")
            except Exception as e:
                self.stdout.write(f"Не удалось получить зарезервированные задачи: {e}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения очередей: {e}"))

    def show_workers(self):
        """Показать информацию о воркерах"""
        self.stdout.write(self.style.SUCCESS("=== Воркеры Celery ==="))

        try:
            app = self.get_celery_app()
            inspect = app.control.inspect()

            # Активные воркеры
            active_workers = inspect.active()
            stats = inspect.stats()

            if not active_workers and not stats:
                self.stdout.write("Воркеры не найдены")
                return

            # Объединяем информацию
            all_workers = set()
            if active_workers:
                all_workers.update(active_workers.keys())
            if stats:
                all_workers.update(stats.keys())

            for worker in sorted(all_workers):
                self.stdout.write(f"\nВоркер: {worker}")

                # Статус
                is_active = worker in active_workers if active_workers else False
                has_stats = worker in stats if stats else False

                self.stdout.write(f"  Статус: {'Активен' if is_active else 'Неактивен'}")

                # Активные задачи
                if is_active:
                    tasks = active_workers[worker]
                    self.stdout.write(f"  Активных задач: {len(tasks)}")

                # Статистика
                if has_stats:
                    worker_stats = stats[worker]

                    if 'total' in worker_stats:
                        total = worker_stats['total']
                        completed = total.get('completed', 0)
                        failed = total.get('failed', 0)
                        self.stdout.write(f"  Выполнено: {completed}")
                        self.stdout.write(f"  Провалено: {failed}")

                    if 'pool' in worker_stats:
                        pool = worker_stats['pool']
                        self.stdout.write(f"  Параллельность: {pool.get('max-concurrency', 'N/A')}")

                    if 'rusage' in worker_stats:
                        rusage = worker_stats['rusage']
                        self.stdout.write(f"  CPU время: {rusage.get('utime', 0):.2f}s")
                        self.stdout.write(f"  Память: {rusage.get('maxrss', 0)} KB")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка получения воркеров: {e}"))

    def inspect_workers(self, worker_name=None):
        """Детальная инспекция воркеров"""
        self.stdout.write(self.style.SUCCESS("=== Инспекция воркеров ==="))

        try:
            app = self.get_celery_app()
            inspect = app.control.inspect()

            if worker_name:
                destination = [worker_name]
            else:
                destination = None

            # Получаем различную информацию
            ping_result = inspect.ping(destination=destination)
            registered_tasks = inspect.registered(destination=destination)
            scheduled_tasks = inspect.scheduled(destination=destination)
            conf = inspect.conf(destination=destination)

            # Показываем результаты
            if ping_result:
                self.stdout.write("\nОтвет на ping:")
                for worker, response in ping_result.items():
                    self.stdout.write(f"  {worker}: {response}")

            if registered_tasks:
                self.stdout.write(f"\nЗарегистрированные задачи:")
                for worker, tasks in registered_tasks.items():
                    self.stdout.write(f"  {worker}: {len(tasks)} задач")
                    for task in sorted(tasks)[:10]:  # показываем первые 10
                        self.stdout.write(f"    - {task}")
                    if len(tasks) > 10:
                        self.stdout.write(f"    ... и ещё {len(tasks) - 10}")

            if scheduled_tasks:
                self.stdout.write(f"\nЗапланированные задачи:")
                for worker, tasks in scheduled_tasks.items():
                    self.stdout.write(f"  {worker}: {len(tasks)} задач")
                    for task in tasks:
                        eta = task.get('eta')
                        task_name = task.get('request', {}).get('name', 'N/A')
                        self.stdout.write(f"    - {task_name} (ETA: {eta})")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка инспекции воркеров: {e}"))

    def purge_queue(self, queue_name):
        """Очистить очередь"""
        if not queue_name:
            raise CommandError("Необходимо указать имя очереди с помощью --queue")

        self.stdout.write(f"Очистка очереди '{queue_name}'...")

        try:
            app = self.get_celery_app()

            # Подтверждение
            confirm = input(f"Вы уверены, что хотите очистить очередь '{queue_name}'? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("Операция отменена")
                return

            # Очищаем очередь
            purged = app.control.purge()
            self.stdout.write(self.style.SUCCESS(f"Очередь '{queue_name}' очищена. Удалено задач: {purged}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка очистки очереди: {e}"))