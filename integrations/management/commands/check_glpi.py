"""
Management команда для запуска проверки устройств в GLPI.

Примеры использования:
  python manage.py check_glpi                    # Запустить задачу асинхронно
  python manage.py check_glpi --sync             # Запустить синхронно (с выводом)
  python manage.py check_glpi --status TASK_ID   # Проверить статус задачи
"""

import sys
import time

from celery.result import AsyncResult
from django.core.management.base import BaseCommand

from integrations.tasks import check_all_devices_in_glpi


class Command(BaseCommand):
    help = "Запуск проверки всех устройств в GLPI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync", action="store_true", help="Запустить синхронно (ждать завершения и показывать прогресс)"
        )
        parser.add_argument("--status", type=str, help="Проверить статус задачи по ID")
        parser.add_argument(
            "--update-contract-field",
            action="store_true",
            help='Обновить поле "Заявлен в договоре" в GLPI для найденных устройств',
        )
        parser.add_argument(
            "--update-only",
            action="store_true",
            help="Только обновить поле договора (без повторной проверки, использует кэш)",
        )

    def handle(self, *args, **options):
        # Проверка статуса задачи
        if options["status"]:
            self.check_task_status(options["status"])
            return

        # Запуск задачи
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🚀 ЗАПУСК ПРОВЕРКИ УСТРОЙСТВ В GLPI"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # Запускаем задачу
        update_contract = options.get("update_contract_field", False)
        update_only = options.get("update_only", False)

        # Если указан --update-only, автоматически включаем --update-contract-field
        if update_only:
            update_contract = True

        result = check_all_devices_in_glpi.delay(update_contract_field=update_contract, skip_check=update_only)
        task_id = result.id

        self.stdout.write(f"✓ Задача запущена")
        self.stdout.write(f"  Task ID: {task_id}")
        self.stdout.write(f"  Очередь: high_priority")
        if update_only:
            self.stdout.write(f"  Режим: Только обновление договора (без проверки)")
        elif update_contract:
            self.stdout.write(f"  Режим: Проверка + обновление поля договора")
        else:
            self.stdout.write(f"  Режим: Только проверка наличия")
        self.stdout.write("")

        if options["sync"]:
            # Синхронный режим - ждем завершения и показываем прогресс
            self.stdout.write("⏳ Ожидание выполнения...")
            self.stdout.write("   (нажмите Ctrl+C для выхода, задача продолжит выполнение)")
            self.stdout.write("")

            try:
                last_percent = -1
                while not result.ready():
                    # Получаем текущее состояние
                    info = result.info

                    if isinstance(info, dict):
                        current = info.get("current", 0)
                        total = info.get("total", 0)
                        percent = info.get("percent", 0)
                        status = info.get("status", "")

                        # Выводим прогресс только если изменился
                        if percent != last_percent:
                            progress_bar = self._create_progress_bar(percent)
                            self.stdout.write(f"\r📈 {progress_bar} {percent}% | {status}", ending="")
                            self.stdout.flush()
                            last_percent = percent

                    time.sleep(1)

                # Задача завершена
                self.stdout.write("")  # Новая строка после прогресса
                self.stdout.write("")

                # Получаем результат
                final_result = result.get(timeout=5)

                # Выводим итоги
                self.stdout.write("=" * 70)
                self.stdout.write(self.style.SUCCESS("✅ ПРОВЕРКА ЗАВЕРШЕНА"))
                self.stdout.write("=" * 70)
                self.stdout.write(
                    f"📊 Проверено устройств: {final_result.get('checked', 0)}/{final_result.get('total', 0)}"
                )
                self.stdout.write(self.style.SUCCESS(f"✓  Найдено (1 карточка): {final_result.get('found_single', 0)}"))
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Конфликты (>1 карточки): {final_result.get('found_multiple', 0)}")
                )
                self.stdout.write(self.style.WARNING(f"❌ Не найдено в GLPI: {final_result.get('not_found', 0)}"))
                self.stdout.write(self.style.ERROR(f"❗ Ошибок при проверке: {final_result.get('errors', 0)}"))

                # Статистика обновления договоров
                if update_contract and "contract_updated" in final_result:
                    self.stdout.write("")
                    self.stdout.write("📝 Обновление поля договора:")
                    self.stdout.write(
                        self.style.SUCCESS(f"✓  Обновлено успешно: {final_result.get('contract_updated', 0)}")
                    )
                    if final_result.get("contract_errors", 0) > 0:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Ошибок обновления: {final_result.get('contract_errors', 0)}")
                        )

                        # Показываем примеры ошибок
                        error_details = final_result.get("contract_error_details", [])
                        if error_details:
                            self.stdout.write("")
                            self.stdout.write(self.style.ERROR(f"Примеры ошибок (первые {len(error_details)}):"))
                            for detail in error_details:
                                self.stdout.write(
                                    f"  • Serial: {detail['serial']} | GLPI ID: {detail['glpi_id']}\n"
                                    f"    Ошибка: {detail['error']}"
                                )

                self.stdout.write("=" * 70)

                # Детали конфликтов
                if final_result.get("conflicts"):
                    self.stdout.write("")
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  ОБНАРУЖЕНО {len(final_result['conflicts'])} КОНФЛИКТОВ:")
                    )
                    for conflict in final_result["conflicts"][:10]:  # Показываем первые 10
                        self.stdout.write(
                            f"  • Device #{conflict['device_id']} ({conflict['serial']}): "
                            f"{conflict['count']} карточек - IDs: {conflict['glpi_ids']}"
                        )
                    if len(final_result["conflicts"]) > 10:
                        self.stdout.write(f"  ... и еще {len(final_result['conflicts']) - 10}")

            except KeyboardInterrupt:
                self.stdout.write("")
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("⚠️  Прервано пользователем"))
                self.stdout.write(f"   Задача продолжает выполнение в фоне: {task_id}")
                self.stdout.write(f"   Проверить статус: python manage.py check_glpi --status {task_id}")

        else:
            # Асинхронный режим - просто выходим
            self.stdout.write("💡 Советы:")
            self.stdout.write(f"   • Следить за прогрессом: python manage.py check_glpi --status {task_id}")
            self.stdout.write(f"   • Или запустить с --sync для отслеживания")
            self.stdout.write(f"   • Логи задачи: tail -f logs/celery.log | grep -i glpi")
            self.stdout.write("")

    def check_task_status(self, task_id):
        """Проверяет статус задачи по ID"""
        self.stdout.write(f"🔍 Проверка статуса задачи: {task_id}")
        self.stdout.write("")

        result = AsyncResult(task_id)

        self.stdout.write(f"Статус: {result.state}")

        if result.state == "PENDING":
            self.stdout.write("   Задача ожидает выполнения или не существует")

        elif result.state == "PROGRESS":
            info = result.info
            if isinstance(info, dict):
                current = info.get("current", 0)
                total = info.get("total", 0)
                percent = info.get("percent", 0)
                status = info.get("status", "")

                progress_bar = self._create_progress_bar(percent)
                self.stdout.write(f"📈 {progress_bar} {percent}%")
                self.stdout.write(f"   {status}")
                self.stdout.write(f"   Прогресс: {current}/{total}")

        elif result.state == "SUCCESS":
            self.stdout.write(self.style.SUCCESS("✓ Задача успешно завершена"))
            final_result = result.result
            if isinstance(final_result, dict):
                self.stdout.write("")
                self.stdout.write(f"📊 Проверено: {final_result.get('checked', 0)}/{final_result.get('total', 0)}")
                self.stdout.write(f"✓  Найдено: {final_result.get('found_single', 0)}")
                self.stdout.write(f"⚠️  Конфликты: {final_result.get('found_multiple', 0)}")
                self.stdout.write(f"❌ Не найдено: {final_result.get('not_found', 0)}")
                self.stdout.write(f"❗ Ошибки: {final_result.get('errors', 0)}")

        elif result.state == "FAILURE":
            self.stdout.write(self.style.ERROR("✗ Задача завершилась с ошибкой"))
            self.stdout.write(f"   {result.info}")

        else:
            self.stdout.write(f"   {result.info}")

    def _create_progress_bar(self, percent, width=30):
        """Создает ASCII прогресс-бар"""
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
