# monthly_report/management/commands/setup_monthly_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps

class Command(BaseCommand):
    help = "Создаёт группы и назначает права для monthly_report (view/upload/edit start/edit end/manage)."

    def handle(self, *args, **kwargs):
        app_label = "monthly_report"

        MonthlyReport = apps.get_model(app_label, "MonthlyReport")
        MonthControl  = apps.get_model(app_label, "MonthControl")

        ct_report  = ContentType.objects.get_for_model(MonthlyReport)
        ct_control = ContentType.objects.get_for_model(MonthControl)

        # Гарантируем наличие КАСТОМНЫХ прав (если не созданы миграциями).
        custom_perms = [
            (ct_report,  "access_monthly_report", "Доступ к разделу ежемесячных отчётов"),
            (ct_report,  "upload_monthly_report", "Загрузка отчётов из Excel"),
            (ct_report,  "edit_counters_start",  "Редактирование счётчиков (начало периода)"),
            (ct_report,  "edit_counters_end",    "Редактирование счётчиков (конец периода)"),
        ]
        for ct, codename, name in custom_perms:
            Permission.objects.get_or_create(
                content_type=ct, codename=codename, defaults={"name": name}
            )

        # Все коды прав, которые понадобятся группам (включая стандартные model perms).
        needed = {
            # MonthlyReport (станд.)
            "view_monthlyreport", "add_monthlyreport", "change_monthlyreport", "delete_monthlyreport",
            # MonthControl (станд.)
            "view_monthcontrol", "change_monthcontrol",
            # кастомные
            "access_monthly_report", "upload_monthly_report", "edit_counters_start", "edit_counters_end",
        }

        perms_qs = Permission.objects.filter(
            content_type__in=[ct_report, ct_control],
            codename__in=needed
        )
        perms = {p.codename: p for p in perms_qs}

        def g(name: str) -> Group:
            grp, _ = Group.objects.get_or_create(name=name)
            return grp

        viewers       = g("MonthlyReport Viewers")
        uploaders     = g("MonthlyReport Uploaders")
        editors_start = g("MonthlyReport Editors (Start)")
        editors_end   = g("MonthlyReport Editors (End)")
        managers      = g("MonthlyReport Managers")

        def add_perms(group: Group, codes: set[str]):
            group.permissions.add(*[perms[c] for c in codes if c in perms])

        # Просмотрщики
        add_perms(viewers, {
            "access_monthly_report", "view_monthlyreport", "view_monthcontrol",
        })

        # Загрузчики (могут добавлять записи)
        add_perms(uploaders, {
            "access_monthly_report", "view_monthlyreport", "view_monthcontrol",
            "upload_monthly_report", "add_monthlyreport",
        })

        # Редакторы START
        add_perms(editors_start, {
            "access_monthly_report", "view_monthlyreport",
            "change_monthlyreport", "edit_counters_start",
        })

        # Редакторы END
        add_perms(editors_end, {
            "access_monthly_report", "view_monthlyreport",
            "change_monthlyreport", "edit_counters_end",
        })

        # Менеджеры (всё + управление окном редактирования)
        add_perms(managers, {
            "access_monthly_report", "view_monthlyreport", "upload_monthly_report",
            "add_monthlyreport", "change_monthlyreport", "delete_monthlyreport",
            "edit_counters_start", "edit_counters_end",
            "view_monthcontrol", "change_monthcontrol",
        })

        self.stdout.write(self.style.SUCCESS("Группы и права настроены."))
        for grp in (viewers, uploaders, editors_start, editors_end, managers):
            self.stdout.write(f" - {grp.name}: {grp.permissions.count()} прав")
