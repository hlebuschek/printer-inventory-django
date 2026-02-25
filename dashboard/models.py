from django.db import models


class DashboardAccess(models.Model):
    """Proxy-модель только для управления правами доступа к дашборду."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('access_dashboard_app', 'Доступ к дашборду'),
        ]
        app_label = 'dashboard'
        verbose_name = 'Дашборд'
        verbose_name_plural = 'Дашборд'
