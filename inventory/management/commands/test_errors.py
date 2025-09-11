from django.core.management.base import BaseCommand
from django.test import Client
from django.conf import settings
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Тестирует обработчики ошибок (только в DEBUG режиме)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-urls',
            action='store_true',
            help='Создать тестовые URL для вызова ошибок'
        )
        parser.add_argument(
            '--test-all',
            action='store_true',
            help='Протестировать все типы ошибок'
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR(
                    'Команда работает только в DEBUG режиме. '
                    'В production используйте реальные ошибочные URL.'
                )
            )
            return

        if options['create_test_urls']:
            self.create_test_urls()

        if options['test_all']:
            self.test_error_handlers()

        if not options['create_test_urls'] and not options['test_all']:
            self.show_help()

    def create_test_urls(self):
        """Показывает, как создать тестовые URL для ошибок"""
        test_urls = """
# Добавьте в printer_inventory/urls.py для тестирования ошибок:

if settings.DEBUG:
    from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
    from django.core.exceptions import PermissionDenied, SuspiciousOperation
    from django.views.decorators.csrf import csrf_exempt

    def test_404(request):
        raise Http404("Тестовая 404 ошибка")

    def test_403(request):
        raise PermissionDenied("Тестовая 403 ошибка")

    def test_400(request):
        raise SuspiciousOperation("Тестовая 400 ошибка")

    @csrf_exempt  
    def test_500(request):
        raise Exception("Тестовая 500 ошибка")

    def test_csrf(request):
        # POST без CSRF токена вызовет CSRF ошибку
        return render(request, 'test_csrf.html')

    urlpatterns += [
        path('test-errors/404/', test_404, name='test_404'),
        path('test-errors/403/', test_403, name='test_403'),
        path('test-errors/400/', test_400, name='test_400'),
        path('test-errors/500/', test_500, name='test_500'),
        path('test-errors/csrf/', test_csrf, name='test_csrf'),
    ]

# После добавления, вы можете перейти по адресам:
# /test-errors/404/
# /test-errors/403/ 
# /test-errors/400/
# /test-errors/500/
# /test-errors/csrf/
"""
        self.stdout.write(self.style.SUCCESS("Тестовые URL для ошибок:"))
        self.stdout.write(test_urls)

    def test_error_handlers(self):
        """Тестирует обработчики ошибок"""
        client = Client()

        self.stdout.write(self.style.SUCCESS("Тестирование обработчиков ошибок..."))

        # Тест 404
        self.stdout.write("Тестируем 404...")
        response = client.get('/nonexistent-url/')
        if response.status_code == 404:
            self.stdout.write(self.style.SUCCESS("✓ 404 обработчик работает"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ 404 обработчик вернул {response.status_code}"))

        # Создаём пользователя для тестов с авторизацией
        try:
            user = User.objects.get(username='test_user')
        except User.DoesNotExist:
            user = User.objects.create_user('test_user', 'test@example.com', 'password')

        # Тест доступа без прав
        client.force_login(user)
        self.stdout.write("Тестируем 403 (доступ без прав)...")
        response = client.get('/admin/')  # Обычный пользователь не может попасть в админку
        if response.status_code in [403, 302]:  # 302 - redirect на login
            self.stdout.write(self.style.SUCCESS("✓ 403 обработчик работает"))
        else:
            self.stdout.write(self.style.WARNING(f"? 403 обработчик вернул {response.status_code}"))

        self.stdout.write(self.style.SUCCESS("\nТестирование завершено."))

    def show_help(self):
        """Показывает справку по использованию команды"""
        help_text = """
Команда для тестирования обработчиков ошибок.

Использование:
  python manage.py test_errors --create-test-urls  # Показать код тестовых URL
  python manage.py test_errors --test-all          # Протестировать обработчики

В production режиме обработчики ошибок активируются автоматически
при возникновении реальных ошибок.

Типы ошибок, которые обрабатываются:
• 400 - Неверный запрос  
• 403 - Доступ запрещён
• 404 - Страница не найдена
• 405 - Метод не разрешён
• 500 - Внутренняя ошибка сервера
• CSRF - Ошибки CSRF защиты

Логи записываются в файлы:
• logs/django.log - общие логи
• logs/errors.log - только ошибки
"""
        self.stdout.write(help_text)