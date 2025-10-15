# access/management/commands/manage_whitelist.py
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from access.models import AllowedUser
import csv
import os


class Command(BaseCommand):
    help = "Управление whitelist разрешенных пользователей Keycloak"

    def add_arguments(self, parser):
        parser.add_argument(
            '--add',
            type=str,
            help='Добавить пользователя в whitelist'
        )
        parser.add_argument(
            '--remove',
            type=str,
            help='Удалить пользователя из whitelist'
        )
        parser.add_argument(
            '--activate',
            type=str,
            help='Активировать пользователя'
        )
        parser.add_argument(
            '--deactivate',
            type=str,
            help='Деактивировать пользователя'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Показать всех пользователей в whitelist'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email пользователя (при добавлении)'
        )
        parser.add_argument(
            '--full-name',
            type=str,
            help='ФИО пользователя (при добавлении)'
        )
        parser.add_argument(
            '--notes',
            type=str,
            help='Примечания (при добавлении)'
        )
        parser.add_argument(
            '--import-existing',
            action='store_true',
            help='Импортировать всех существующих пользователей Django'
        )
        parser.add_argument(
            '--bulk-add',
            type=str,
            help='Массово добавить пользователей из файла (CSV/TXT)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано, без изменений (для --bulk-add)'
        )
        parser.add_argument(
            '--delimiter',
            type=str,
            default=',',
            help='Разделитель для CSV (по умолчанию запятая)'
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_users()
        elif options['add']:
            self.add_user(options)
        elif options['remove']:
            self.remove_user(options['remove'])
        elif options['activate']:
            self.activate_user(options['activate'])
        elif options['deactivate']:
            self.deactivate_user(options['deactivate'])
        elif options['import_existing']:
            self.import_existing_users()
        elif options['bulk_add']:
            self.bulk_add_users(options)
        else:
            self.stdout.write(self.style.ERROR(
                'Укажите действие: --add, --remove, --activate, --deactivate, --list, --import-existing или --bulk-add'
            ))

    def list_users(self):
        """Показать всех пользователей в whitelist"""
        users = AllowedUser.objects.all().order_by('-is_active', 'username')

        if not users.exists():
            self.stdout.write(self.style.WARNING('Whitelist пуст'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nВсего в whitelist: {users.count()}\n'))

        active_count = users.filter(is_active=True).count()
        inactive_count = users.filter(is_active=False).count()

        self.stdout.write(f'Активных: {active_count}')
        self.stdout.write(f'Неактивных: {inactive_count}\n')

        self.stdout.write(self.style.SUCCESS('=' * 80))
        for user in users:
            status = '✓ АКТИВЕН' if user.is_active else '✗ ОТКЛЮЧЕН'
            style = self.style.SUCCESS if user.is_active else self.style.WARNING

            self.stdout.write(style(f'\n{status}: {user.username}'))
            if user.email:
                self.stdout.write(f'  Email: {user.email}')
            if user.full_name:
                self.stdout.write(f'  ФИО: {user.full_name}')
            if user.notes:
                self.stdout.write(f'  Примечания: {user.notes}')
            self.stdout.write(f'  Добавлен: {user.added_at.strftime("%Y-%m-%d %H:%M")}')
            if user.added_by:
                self.stdout.write(f'  Добавил: {user.added_by}')

            # Проверяем, есть ли Django пользователь
            django_user = User.objects.filter(username__iexact=user.username).first()
            if django_user:
                self.stdout.write(f'  Django пользователь: ✓ существует (ID: {django_user.id})')
            else:
                self.stdout.write('  Django пользователь: ✗ не создан')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))

    def add_user(self, options):
        """Добавить пользователя в whitelist"""
        username = options['add'].strip()

        if AllowedUser.objects.filter(username__iexact=username).exists():
            raise CommandError(f"Пользователь '{username}' уже есть в whitelist")

        allowed_user = AllowedUser.objects.create(
            username=username,
            email=options.get('email', ''),
            full_name=options.get('full_name', ''),
            notes=options.get('notes', ''),
            added_by='console',
            is_active=True
        )

        self.stdout.write(self.style.SUCCESS(
            f"✓ Пользователь '{username}' добавлен в whitelist"
        ))

        # Проверяем, есть ли уже Django пользователь
        django_user = User.objects.filter(username__iexact=username).first()
        if django_user:
            self.stdout.write(self.style.WARNING(
                f"  Django пользователь '{username}' уже существует"
            ))
            if not django_user.is_active:
                django_user.is_active = True
                django_user.save()
                self.stdout.write(self.style.SUCCESS(
                    "  Пользователь был активирован"
                ))
        else:
            self.stdout.write(
                "  Django пользователь будет создан при первом входе через Keycloak"
            )

    def remove_user(self, username):
        """Удалить пользователя из whitelist"""
        try:
            user = AllowedUser.objects.get(username__iexact=username)
            user.delete()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Пользователь '{username}' удален из whitelist"
            ))

            # Деактивируем Django пользователя
            django_user = User.objects.filter(username__iexact=username).first()
            if django_user and not django_user.is_superuser:
                django_user.is_active = False
                django_user.save()
                self.stdout.write(self.style.SUCCESS(
                    "  Django пользователь деактивирован"
                ))

        except AllowedUser.DoesNotExist:
            raise CommandError(f"Пользователь '{username}' не найден в whitelist")

    def activate_user(self, username):
        """Активировать пользователя"""
        try:
            user = AllowedUser.objects.get(username__iexact=username)
            if user.is_active:
                self.stdout.write(self.style.WARNING(
                    f"Пользователь '{username}' уже активен"
                ))
                return

            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Пользователь '{username}' активирован"
            ))

            # Активируем Django пользователя
            django_user = User.objects.filter(username__iexact=username).first()
            if django_user:
                django_user.is_active = True
                django_user.save()
                self.stdout.write(self.style.SUCCESS(
                    "  Django пользователь также активирован"
                ))

        except AllowedUser.DoesNotExist:
            raise CommandError(f"Пользователь '{username}' не найден в whitelist")

    def deactivate_user(self, username):
        """Деактивировать пользователя"""
        try:
            user = AllowedUser.objects.get(username__iexact=username)
            if not user.is_active:
                self.stdout.write(self.style.WARNING(
                    f"Пользователь '{username}' уже неактивен"
                ))
                return

            user.is_active = False
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Пользователь '{username}' деактивирован"
            ))

            # Деактивируем Django пользователя
            django_user = User.objects.filter(username__iexact=username).first()
            if django_user and not django_user.is_superuser:
                django_user.is_active = False
                django_user.save()
                self.stdout.write(self.style.SUCCESS(
                    "  Django пользователь также деактивирован"
                ))

        except AllowedUser.DoesNotExist:
            raise CommandError(f"Пользователь '{username}' не найден в whitelist")

    def import_existing_users(self):
        """Импортировать всех существующих Django пользователей"""
        django_users = User.objects.filter(is_active=True)

        added_count = 0
        skipped_count = 0

        for django_user in django_users:
            if AllowedUser.objects.filter(username__iexact=django_user.username).exists():
                skipped_count += 1
                continue

            AllowedUser.objects.create(
                username=django_user.username,
                email=django_user.email,
                full_name=django_user.get_full_name(),
                notes='Импортирован из существующих Django пользователей',
                added_by='import',
                is_active=True
            )
            added_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Импорт завершен:"
        ))
        self.stdout.write(f"  Добавлено: {added_count}")
        self.stdout.write(f"  Пропущено (уже в whitelist): {skipped_count}")

    def bulk_add_users(self, options):
        """
        Массовое добавление пользователей из файла.

        Поддерживаемые форматы:

        1. CSV с заголовками:
           username,email,full_name,notes
           ivanov,ivanov@company.com,Иванов Иван Иванович,Отдел продаж
           petrov,petrov@company.com,Петров Петр Петрович,

        2. CSV без заголовков (username,email,full_name):
           ivanov,ivanov@company.com,Иванов Иван Иванович
           petrov,petrov@company.com,Петров Петр Петрович

        3. Простой список логинов (по одному на строке):
           ivanov
           petrov
           sidorov

        4. TSV (tab-separated):
           ivanov    ivanov@company.com    Иванов Иван Иванович
           petrov    petrov@company.com    Петров Петр Петрович
        """
        file_path = options['bulk_add']
        dry_run = options['dry_run']
        delimiter = options['delimiter']

        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise CommandError(f"Файл не найден: {file_path}")

        # Определяем расширение файла
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Для .tsv или .tab используем табуляцию
        if ext in ['.tsv', '.tab']:
            delimiter = '\t'

        # Читаем файл
        users_to_add = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Пробуем определить формат
                first_line = f.readline().strip()
                f.seek(0)  # Возвращаемся в начало

                # Проверяем, есть ли разделители
                has_delimiter = delimiter in first_line or '\t' in first_line

                if has_delimiter:
                    # CSV/TSV формат
                    reader = csv.DictReader(f, delimiter=delimiter)

                    # Проверяем, есть ли заголовки
                    fieldnames = reader.fieldnames

                    if fieldnames and 'username' in [fn.lower() if fn else '' for fn in fieldnames]:
                        # CSV с заголовками
                        self.stdout.write("Обнаружен CSV формат с заголовками")

                        for row in reader:
                            # Получаем данные с учетом регистра заголовков
                            username = None
                            email = ''
                            full_name = ''
                            notes = ''

                            for key, value in row.items():
                                key_lower = key.lower() if key else ''
                                if key_lower == 'username':
                                    username = value.strip()
                                elif key_lower == 'email':
                                    email = value.strip()
                                elif key_lower in ['full_name', 'fullname', 'name', 'fio']:
                                    full_name = value.strip()
                                elif key_lower == 'notes':
                                    notes = value.strip()

                            if username:
                                users_to_add.append({
                                    'username': username,
                                    'email': email,
                                    'full_name': full_name,
                                    'notes': notes
                                })
                    else:
                        # CSV без заголовков или с непонятными заголовками
                        self.stdout.write("Обнаружен CSV формат без заголовков")
                        f.seek(0)  # Возвращаемся в начало

                        reader = csv.reader(f, delimiter=delimiter)
                        for row in reader:
                            if not row or not row[0].strip():
                                continue

                            username = row[0].strip()
                            email = row[1].strip() if len(row) > 1 else ''
                            full_name = row[2].strip() if len(row) > 2 else ''
                            notes = row[3].strip() if len(row) > 3 else ''

                            users_to_add.append({
                                'username': username,
                                'email': email,
                                'full_name': full_name,
                                'notes': notes
                            })
                else:
                    # Простой список (по одному логину на строке)
                    self.stdout.write("Обнаружен формат: список логинов")

                    for line in f:
                        username = line.strip()
                        if username and not username.startswith('#'):  # Поддержка комментариев
                            users_to_add.append({
                                'username': username,
                                'email': '',
                                'full_name': '',
                                'notes': 'Массовое добавление'
                            })

        except Exception as e:
            raise CommandError(f"Ошибка чтения файла: {e}")

        if not users_to_add:
            raise CommandError("В файле не найдено ни одного пользователя для добавления")

        # Статистика
        total_count = len(users_to_add)
        added_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 80}\n"
            f"Найдено пользователей для обработки: {total_count}\n"
            f"{'=' * 80}\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN режим: изменения НЕ будут сохранены\n"
            ))

        # Обрабатываем пользователей
        for user_data in users_to_add:
            username = user_data['username']

            try:
                # Проверяем, существует ли уже
                existing = AllowedUser.objects.filter(username__iexact=username).first()

                if existing:
                    if existing.is_active:
                        self.stdout.write(self.style.WARNING(
                            f"⊙ ПРОПУЩЕН: {username} (уже в whitelist и активен)"
                        ))
                        skipped_count += 1
                    else:
                        if not dry_run:
                            existing.is_active = True
                            existing.save()

                            # Активируем Django пользователя
                            django_user = User.objects.filter(
                                username__iexact=username
                            ).first()
                            if django_user:
                                django_user.is_active = True
                                django_user.save()

                        self.stdout.write(self.style.SUCCESS(
                            f"↻ РЕАКТИВИРОВАН: {username}"
                        ))
                        updated_count += 1
                else:
                    if not dry_run:
                        AllowedUser.objects.create(
                            username=username,
                            email=user_data.get('email', ''),
                            full_name=user_data.get('full_name', ''),
                            notes=user_data.get('notes', 'Массовое добавление'),
                            added_by='bulk_import',
                            is_active=True
                        )

                    info = f"✓ ДОБАВЛЕН: {username}"
                    if user_data.get('email'):
                        info += f" | {user_data['email']}"
                    if user_data.get('full_name'):
                        info += f" | {user_data['full_name']}"

                    self.stdout.write(self.style.SUCCESS(info))
                    added_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"✗ ОШИБКА: {username} - {str(e)}"
                ))
                error_count += 1

        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 80}\n"
            f"ИТОГО:\n"
            f"{'=' * 80}\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: Никакие изменения не были сохранены\n"
            ))

        self.stdout.write(f"Всего обработано: {total_count}")
        self.stdout.write(self.style.SUCCESS(f"✓ Добавлено новых: {added_count}"))
        self.stdout.write(self.style.SUCCESS(f"↻ Реактивировано: {updated_count}"))
        self.stdout.write(self.style.WARNING(f"⊙ Пропущено: {skipped_count}"))

        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Ошибок: {error_count}"))

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 80}\n"))

        if dry_run:
            self.stdout.write(
                "Для применения изменений запустите команду без --dry-run\n"
            )