import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Переключает DEBUG режим для тестирования обработчиков ошибок"

    def add_arguments(self, parser):
        parser.add_argument(
            '--on',
            action='store_true',
            help='Включить DEBUG режим'
        )
        parser.add_argument(
            '--off',
            action='store_true',
            help='Выключить DEBUG режим'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Показать текущий статус DEBUG'
        )

    def handle(self, *args, **options):
        env_file = Path(settings.BASE_DIR) / '.env'

        if options['status']:
            self.show_status()
            return

        if options['on'] and options['off']:
            self.stdout.write(
                self.style.ERROR('Нельзя одновременно включить и выключить DEBUG режим')
            )
            return

        if not options['on'] and not options['off']:
            self.show_help()
            return

        if options['on']:
            self.set_debug(True, env_file)
        elif options['off']:
            self.set_debug(False, env_file)

    def show_status(self):
        """Показывает текущий статус DEBUG и связанных настроек"""
        current_debug = getattr(settings, 'DEBUG', False)

        self.stdout.write(
            f"Текущий DEBUG режим: {self.style.SUCCESS('ON') if current_debug else self.style.ERROR('OFF')}")

        if current_debug:
            self.stdout.write("\n" + self.style.SUCCESS("В DEBUG режиме доступно:"))
            self.stdout.write("• Детальные страницы ошибок Django")
            self.stdout.write("• Тестовые URL для ошибок: /debug/errors/")
            self.stdout.write("• Подробные трейсбеки исключений")
            self.stdout.write("• Автоперезагрузка при изменении кода")
        else:
            self.stdout.write("\n" + self.style.WARNING("В PRODUCTION режиме:"))
            self.stdout.write("• Активны кастомные обработчики ошибок")
            self.stdout.write("• Красивые страницы ошибок")
            self.stdout.write("• Логирование ошибок в файлы")
            self.stdout.write("• Заголовки безопасности")

        # Статус логирования
        logs_dir = Path(settings.BASE_DIR) / 'logs'
        if logs_dir.exists():
            self.stdout.write(f"\nЛоги: {logs_dir}")
            for log_file in ['django.log', 'errors.log']:
                log_path = logs_dir / log_file
                if log_path.exists():
                    size = log_path.stat().st_size
                    self.stdout.write(f"• {log_file}: {size} байт")
                else:
                    self.stdout.write(f"• {log_file}: не создан")
        else:
            self.stdout.write(f"\nДиректория логов не найдена: {logs_dir}")

    def set_debug(self, debug_value, env_file):
        """Устанавливает значение DEBUG в .env файле"""
        debug_str = "True" if debug_value else "False"

        if not env_file.exists():
            # Создаём .env файл
            content = f"DEBUG={debug_str}\n"
            self.stdout.write(f"Создаём {env_file}")
        else:
            # Читаем существующий .env файл
            content = env_file.read_text(encoding='utf-8')

            # Обновляем или добавляем DEBUG
            lines = content.splitlines()
            debug_found = False

            for i, line in enumerate(lines):
                if line.startswith('DEBUG='):
                    lines[i] = f'DEBUG={debug_str}'
                    debug_found = True
                    break

            if not debug_found:
                lines.append(f'DEBUG={debug_str}')

            content = '\n'.join(lines) + '\n'

        # Записываем файл
        env_file.write_text(content, encoding='utf-8')

        self.stdout.write(
            self.style.SUCCESS(
                f'DEBUG режим {"включён" if debug_value else "выключен"}. '
                f'Перезапустите сервер для применения изменений.'
            )
        )

        if debug_value:
            self.stdout.write("\nТеперь доступны тестовые URL:")
            self.stdout.write("• /debug/errors/ - меню тестирования")
            self.stdout.write("• /debug/errors/404/ - тест 404 ошибки")
            self.stdout.write("• /debug/errors/500/ - тест 500 ошибки")
        else:
            self.stdout.write("\nКастомные обработчики ошибок активированы.")
            self.stdout.write("Для проверки используйте несуществующие URL.")

    def show_help(self):
        """Показывает справку по использованию команды"""
        help_text = """
Команда для управления DEBUG режимом.

Использование:
  python manage.py toggle_debug --status    # Показать текущий статус
  python manage.py toggle_debug --on       # Включить DEBUG режим  
  python manage.py toggle_debug --off      # Выключить DEBUG режим

После изменения режима необходимо перезапустить сервер разработки.

DEBUG=True (разработка):
• Детальные страницы ошибок с трейсбеками
• Доступны тестовые URL /debug/errors/
• Автоперезагрузка при изменении кода
• Подробное логирование

DEBUG=False (production):
• Кастомные красивые страницы ошибок  
• Логирование в файлы logs/
• Заголовки безопасности
• Скрытие чувствительной информации

Для тестирования обработчиков ошибок:
1. Включите DEBUG=False
2. Перезапустите сервер  
3. Перейдите на несуществующую страницу
4. Проверьте логи в директории logs/
"""
        self.stdout.write(help_text)