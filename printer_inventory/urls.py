# printer_inventory/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # auth
    path('accounts/login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # apps
    path('printers/',  include(('inventory.urls', 'inventory'), namespace='inventory')),
    path('contracts/', include(('contracts.urls', 'contracts'), namespace='contracts')),
    path('', RedirectView.as_view(pattern_name='inventory:printer_list', permanent=False), name='index'),
    path("", include("access.urls", namespace="access")),
    path('monthly-report/', include('monthly_report.urls')),
    ]
