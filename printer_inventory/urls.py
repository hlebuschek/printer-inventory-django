# printer_inventory/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.conf import settings
urlpatterns = [
    path('admin/', admin.site.urls),

    # auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # apps
    path('printers/', include(('inventory.urls', 'inventory'), namespace='inventory')),
    path('contracts/', include(('contracts.urls', 'contracts'), namespace='contracts')),
    path('', RedirectView.as_view(pattern_name='inventory:printer_list', permanent=False), name='index'),
    path("", include("access.urls", namespace="access")),
    path('monthly-report/', include('monthly_report.urls')),
]

# Debug URLs для тестирования ошибок
if settings.DEBUG:
    from printer_inventory import debug_views

    urlpatterns += [
        # Меню тестирования ошибок
        path('debug/errors/', debug_views.error_test_menu, name='error_test_menu'),

        # Тестовые ошибки
        path('debug/errors/400/', debug_views.test_400, name='test_400'),
        path('debug/errors/403/', debug_views.test_403, name='test_403'),
        path('debug/errors/404/', debug_views.test_404, name='test_404'),
        path('debug/errors/405/', debug_views.test_405, name='test_405'),
        path('debug/errors/500/', debug_views.test_500, name='test_500'),

        # CSRF тестирование
        path('debug/errors/csrf/', debug_views.test_csrf_form, name='test_csrf_form'),
        path('debug/errors/csrf/submit/', debug_views.test_csrf_submit, name='test_csrf_submit'),
    ]

# Обработчики ошибок (настраиваются автоматически из settings.py)
# В DEBUG=True режиме Django покажет встроенные страницы отладки
if not settings.DEBUG:
    from printer_inventory import errors

    # Эти переменные автоматически используются Django
    handler400 = errors.custom_400
    handler403 = errors.custom_403
    handler404 = errors.custom_404
    handler500 = errors.custom_500