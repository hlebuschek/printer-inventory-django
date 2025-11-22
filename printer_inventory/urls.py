from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from .auth_views import login_choice, django_login, keycloak_access_denied, custom_logout, CustomOIDCCallbackView
from django.views.generic import TemplateView
from mozilla_django_oidc import views as oidc_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # OIDC auth - используем кастомный callback
    path('oidc/callback/', CustomOIDCCallbackView.as_view(), name='oidc_authentication_callback'),
    path('oidc/authenticate/', oidc_views.OIDCAuthenticationRequestView.as_view(), name='oidc_authentication_init'),
    path('oidc/logout/', oidc_views.OIDCLogoutView.as_view(), name='oidc_logout'),

    # Наши кастомные auth views
    path('accounts/login/', login_choice, name='login_choice'),
    path('accounts/django-login/', django_login, name='django_login'),
    path('accounts/access-denied/', keycloak_access_denied, name='keycloak_access_denied'),
    path('accounts/logout/', custom_logout, name='logout'),

    # Для совместимости (старые ссылки)
    path('login/', auth_views.LoginView.as_view(template_name='registration/django_login.html'), name='login'),

    # apps
    path('inventory/', include(('inventory.urls', 'inventory'), namespace='inventory')),
    path('contracts/', include(('contracts.urls', 'contracts'), namespace='contracts')),
    path('', RedirectView.as_view(pattern_name='inventory:printer_list', permanent=False), name='index'),
    path("", include("access.urls", namespace="access")),
    path('monthly-report/', include('monthly_report.urls')),
    path('test-alpine/', TemplateView.as_view(template_name='alpine_test.html'), name='test_alpine'),
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

# Обработчики ошибок
if not settings.DEBUG:
    from printer_inventory import errors

    handler400 = errors.custom_400
    handler403 = errors.custom_403
    handler404 = errors.custom_404
    handler500 = errors.custom_500

# Обслуживание статики в dev режиме
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')