from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from inventory.views import printer_list

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", printer_list, name="index"),
    # Авторизация
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Основное приложение
    path('', include('inventory.urls')),
    path("contracts/", include(("contracts.urls", "contracts"), namespace="contracts")),
]