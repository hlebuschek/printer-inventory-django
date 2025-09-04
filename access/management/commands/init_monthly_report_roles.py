from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.apps import apps

class Command(BaseCommand):
    help = "Создаёт группы и назначает права для monthly_report"

    def handle(self, *args, **kwargs):
        app_label = 'monthly_report'
        perms_needed = [
            ('access_monthly_report',),
            ('upload_monthly_report',),
            ('view_monthlyreport',),  # базовое право на просмотр записей модели
        ]

        ct_model = apps.get_model(app_label, 'MonthlyReport')
        codenames = [p[0] for p in perms_needed]
        perms = Permission.objects.filter(codename__in=codenames, content_type__app_label=app_label)

        viewers, _ = Group.objects.get_or_create(name='MonthlyReport Viewers')
        uploaders, _ = Group.objects.get_or_create(name='MonthlyReport Uploaders')

        for p in perms:
            if p.codename in ('access_monthly_report', 'view_monthlyreport'):
                viewers.permissions.add(p)
            if p.codename in ('access_monthly_report', 'view_monthlyreport', 'upload_monthly_report'):
                uploaders.permissions.add(p)

        self.stdout.write(self.style.SUCCESS("Группы и права настроены."))
