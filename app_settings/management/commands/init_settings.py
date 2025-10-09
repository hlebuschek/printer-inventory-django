from django.core.management.base import BaseCommand
from app_settings.models import AppSetting, SettingCategory, SettingType


class Command(BaseCommand):
    help = 'Инициализация настроек приложения из .env'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перезаписать существующие настройки'
        )

    def handle(self, *args, **options):
        force = options['force']

        # Определяем все настройки
        settings_to_create = [
            # Keycloak
            {
                'key': 'KEYCLOAK_SERVER_URL',
                'category': SettingCategory.KEYCLOAK,
                'setting_type': SettingType.URL,
                'description': 'URL сервера Keycloak',
                'default_value': 'http://localhost:8080',
                'requires_restart': True,
            },
            {
                'key': 'KEYCLOAK_REALM',
                'category': SettingCategory.KEYCLOAK,
                'setting_type': SettingType.STRING,
                'description': 'Realm Keycloak',
                'default_value': 'printer-inventory',
                'requires_restart': True,
            },
            {
                'key': 'OIDC_CLIENT_ID',
                'category': SettingCategory.KEYCLOAK,
                'setting_type': SettingType.STRING,
                'description': 'Client ID для OIDC',
                'default_value': '',
                'requires_restart': True,
            },
            {
                'key': 'OIDC_CLIENT_SECRET',
                'category': SettingCategory.KEYCLOAK,
                'setting_type': SettingType.PASSWORD,
                'description': 'Client Secret для OIDC',
                'default_value': '',
                'is_secret': True,
                'requires_restart': True,
            },

            # GLPI
            {
                'key': 'GLPI_PATH',
                'category': SettingCategory.GLPI,
                'setting_type': SettingType.STRING,
                'description': 'Путь к исполняемым файлам GLPI Agent',
                'default_value': '/usr/bin',
                'requires_restart': False,
            },
            {
                'key': 'GLPI_USE_SUDO',
                'category': SettingCategory.GLPI,
                'setting_type': SettingType.BOOLEAN,
                'description': 'Использовать sudo для запуска GLPI',
                'default_value': 'False',
                'requires_restart': False,
            },
            {
                'key': 'GLPI_USER',
                'category': SettingCategory.GLPI,
                'setting_type': SettingType.STRING,
                'description': 'Пользователь для запуска GLPI (если нужен sudo)',
                'default_value': '',
                'requires_restart': False,
            },

            # Redis
            {
                'key': 'REDIS_HOST',
                'category': SettingCategory.REDIS,
                'setting_type': SettingType.STRING,
                'description': 'Хост Redis сервера',
                'default_value': 'localhost',
                'requires_restart': True,
            },
            {
                'key': 'REDIS_PORT',
                'category': SettingCategory.REDIS,
                'setting_type': SettingType.INTEGER,
                'description': 'Порт Redis сервера',
                'default_value': '6379',
                'requires_restart': True,
            },
            {
                'key': 'REDIS_PASSWORD',
                'category': SettingCategory.REDIS,
                'setting_type': SettingType.PASSWORD,
                'description': 'Пароль Redis (если требуется)',
                'default_value': '',
                'is_secret': True,
                'requires_restart': True,
            },
            {
                'key': 'REDIS_DB',
                'category': SettingCategory.REDIS,
                'setting_type': SettingType.INTEGER,
                'description': 'Номер базы данных Redis',
                'default_value': '0',
                'requires_restart': True,
            },

            # Celery
            {
                'key': 'POLL_INTERVAL_MINUTES',
                'category': SettingCategory.CELERY,
                'setting_type': SettingType.INTEGER,
                'description': 'Интервал периодического опроса принтеров (в минутах)',
                'default_value': '60',
                'requires_restart': True,
            },

            # System
            {
                'key': 'HTTP_CHECK',
                'category': SettingCategory.SYSTEM,
                'setting_type': SettingType.BOOLEAN,
                'description': 'Выполнять HTTP проверку перед опросом принтера',
                'default_value': 'True',
                'requires_restart': False,
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for setting_data in settings_to_create:
            key = setting_data['key']

            try:
                setting = AppSetting.objects.get(key=key)
                if force:
                    for field, value in setting_data.items():
                        if field != 'key':
                            setattr(setting, field, value)
                    setting.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Обновлена настройка: {key}')
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.NOTICE(f'Пропущена (уже существует): {key}')
                    )
            except AppSetting.DoesNotExist:
                AppSetting.objects.create(**setting_data)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Создана настройка: {key}')
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS(f'Создано: {created_count}'))
        self.stdout.write(self.style.WARNING(f'Обновлено: {updated_count}'))
        self.stdout.write(self.style.NOTICE(f'Пропущено: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))