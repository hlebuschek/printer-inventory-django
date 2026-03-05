# access/management/commands/bootstrap_roles.py

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

DASH_APP_PERMS = {
    "access": "dashboard.access_dashboard_app",
}

INV_APP_PERMS = {
    "access": "inventory.access_inventory_app",
    "run": "inventory.run_inventory",
    "export": ["inventory.export_printers", "inventory.export_amb_report"],
    "web_parsing": ["inventory.manage_web_parsing", "inventory.view_web_parsing"],
}

CON_APP_PERMS = {
    "access": "contracts.access_contracts_app",
    "export": ["contracts.export_contracts"],
}

MR_APP_PERMS = {
    "access": "monthly_report.access_monthly_report",
    "upload": "monthly_report.upload_monthly_report",
    "edit_start": "monthly_report.edit_counters_start",
    "edit_end": "monthly_report.edit_counters_end",
    "sync": "monthly_report.sync_from_inventory",
    "history": "monthly_report.view_change_history",
    "metrics": "monthly_report.view_monthly_report_metrics",
    "visibility": "monthly_report.can_manage_month_visibility",
    "reset_polling": "monthly_report.can_reset_auto_polling",
    "poll_all": "monthly_report.can_poll_all_printers",
    "delete_month": "monthly_report.can_delete_month",
}

# Какие модели считаем «основными» для CRUD
INV_MODELS = ["printer", "organization", "inventorytask", "webparsingrule"]
CON_MODELS = ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
MR_MODELS = ["monthlyreport", "monthcontrol"]


def CODENAMES(act, model):
    return f"{act}_{model}"


class Command(BaseCommand):
    help = "Create default RBAC groups and assign permissions for Inventory, Contracts, and MonthlyReport apps"

    def get_or_rename_group(self, en_name: str, ru_name: str) -> Group:
        """
        Returns a group with Russian name.
        - If Russian group exists, use it
        - If English group exists, rename it to Russian (preserving members/permissions)
        - Otherwise create new group with Russian name
        """
        try:
            return Group.objects.get(name=ru_name)
        except Group.DoesNotExist:
            pass

        try:
            g_en = Group.objects.get(name=en_name)
            g_en.name = ru_name
            g_en.save(update_fields=["name"])
            self.stdout.write(self.style.WARNING(f"Группа переименована: '{en_name}' -> '{ru_name}'"))
            return g_en
        except Group.DoesNotExist:
            g_ru, _ = Group.objects.get_or_create(name=ru_name)
            return g_ru

    def add_model_perms(self, perms, app_label, models, acts):
        for model in models:
            for act in acts:
                perms.add(f"{app_label}.{CODENAMES(act, model)}")
        # Всегда включаем view_* для всех моделей приложения
        for ct in ContentType.objects.filter(app_label=app_label):
            perms.add(f"{app_label}.view_{ct.model}")
        return perms

    def get_permissions(self, perm_codes):
        objs = set()
        for code in perm_codes:
            if isinstance(code, (list, tuple, set)):
                for c in code:
                    try:
                        objs.add(
                            Permission.objects.get(codename=c.split(".")[-1], content_type__app_label=c.split(".")[0])
                        )
                    except Permission.DoesNotExist:
                        self.stderr.write(self.style.WARNING(f"Permission not found: {c}"))
            else:
                try:
                    objs.add(
                        Permission.objects.get(codename=code.split(".")[-1], content_type__app_label=code.split(".")[0])
                    )
                except Permission.DoesNotExist:
                    self.stderr.write(self.style.WARNING(f"Permission not found: {code}"))
        return objs

    def handle(self, *args, **options):
        # Dashboard — доступ к дашборду (добавляется всем группам с доступом к приложениям)
        dash_access = DASH_APP_PERMS["access"]

        # Inventory Viewer
        inv_viewer_codes = set([INV_APP_PERMS["access"], *INV_APP_PERMS["export"], dash_access])
        inv_viewer_codes.add(INV_APP_PERMS["web_parsing"][1])  # 🆕 view_web_parsing
        inv_viewer_codes = self.add_model_perms(inv_viewer_codes, "inventory", [], acts=[])

        # Inventory Editor = Viewer + CRUD основных моделей (БЕЗ веб-парсинга)
        inv_editor_codes = set(inv_viewer_codes)
        inv_editor_codes = self.add_model_perms(
            inv_editor_codes,
            "inventory",
            ["printer", "organization", "inventorytask"],  # БЕЗ webparsingrule
            acts=["add", "change", "delete"],
        )

        # Inventory Admin = Editor + run_inventory + manage_web_parsing
        inv_admin_codes = set(inv_editor_codes)
        inv_admin_codes.add(INV_APP_PERMS["run"])
        inv_admin_codes.add(INV_APP_PERMS["web_parsing"][0])  # manage_web_parsing
        inv_admin_codes = self.add_model_perms(
            inv_admin_codes,
            "inventory",
            ["webparsingrule"],  # CRUD для правил парсинга
            acts=["add", "change", "delete"],
        )

        # Contracts Viewer
        con_viewer_codes = set([CON_APP_PERMS["access"], *CON_APP_PERMS["export"], dash_access])
        con_viewer_codes = self.add_model_perms(con_viewer_codes, "contracts", [], acts=[])

        # Contracts Editor
        con_editor_codes = set(con_viewer_codes)
        con_editor_codes = self.add_model_perms(
            con_editor_codes, "contracts", CON_MODELS, acts=["add", "change", "delete"]
        )

        # Contracts Admin (пока без доп. спецправ)
        con_admin_codes = set(con_editor_codes)

        # === Monthly Report Groups ===
        # Base permission set for all groups
        mr_base = set([MR_APP_PERMS["access"], dash_access])
        mr_base = self.add_model_perms(mr_base, "monthly_report", [], acts=[])

        # MonthlyReport Viewers - просмотр
        mr_viewer_codes = set(mr_base)
        mr_viewer_codes.add("monthly_report.view_monthlyreport")
        mr_viewer_codes.add("monthly_report.view_monthcontrol")

        # MonthlyReport Uploaders - загрузка Excel
        mr_uploader_codes = set(mr_base)
        mr_uploader_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.view_monthcontrol",
                MR_APP_PERMS["upload"],
                "monthly_report.add_monthlyreport",
            ]
        )

        # MonthlyReport Editors (Start) - редактирование счётчиков начала
        mr_editor_start_codes = set(mr_base)
        mr_editor_start_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.change_monthlyreport",
                MR_APP_PERMS["edit_start"],
            ]
        )

        # MonthlyReport Editors (End) - редактирование счётчиков конца
        mr_editor_end_codes = set(mr_base)
        mr_editor_end_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.change_monthlyreport",
                MR_APP_PERMS["edit_end"],
            ]
        )

        # MonthlyReport Editors (Full) - полные редакторы
        mr_editor_full_codes = set(mr_base)
        mr_editor_full_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.change_monthlyreport",
                MR_APP_PERMS["edit_start"],
                MR_APP_PERMS["edit_end"],
            ]
        )

        # MonthlyReport Sync Users - синхронизация
        mr_sync_codes = set(mr_base)
        mr_sync_codes.update(
            [
                "monthly_report.view_monthlyreport",
                MR_APP_PERMS["sync"],
            ]
        )

        # MonthlyReport Managers - все права
        mr_manager_codes = set(mr_base)
        mr_manager_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.add_monthlyreport",
                "monthly_report.change_monthlyreport",
                "monthly_report.delete_monthlyreport",
                "monthly_report.view_monthcontrol",
                "monthly_report.change_monthcontrol",
                MR_APP_PERMS["upload"],
                MR_APP_PERMS["edit_start"],
                MR_APP_PERMS["edit_end"],
                MR_APP_PERMS["sync"],
                MR_APP_PERMS["history"],
                MR_APP_PERMS["metrics"],
                MR_APP_PERMS["visibility"],
                MR_APP_PERMS["reset_polling"],
                MR_APP_PERMS["poll_all"],
                MR_APP_PERMS["delete_month"],
            ]
        )

        # MonthlyReport History Viewers - просмотр истории
        mr_history_codes = set(mr_base)
        mr_history_codes.update(
            [
                "monthly_report.view_monthlyreport",
                MR_APP_PERMS["history"],
                MR_APP_PERMS["metrics"],
            ]
        )

        # MonthlyReport Metrics Viewers - просмотр метрик
        mr_metrics_codes = set(mr_base)
        mr_metrics_codes.update(
            [
                "monthly_report.view_monthlyreport",
                MR_APP_PERMS["metrics"],
            ]
        )

        # MonthlyReport Month Visibility Managers - управление видимостью
        mr_visibility_codes = set(mr_base)
        mr_visibility_codes.update(
            [
                "monthly_report.view_monthlyreport",
                "monthly_report.view_monthcontrol",
                MR_APP_PERMS["visibility"],
            ]
        )

        # MonthlyReport Auto Polling Resetters - сброс автоопроса
        mr_reset_polling_codes = set(mr_base)
        mr_reset_polling_codes.update(
            [
                "monthly_report.view_monthlyreport",
                MR_APP_PERMS["reset_polling"],
                MR_APP_PERMS["history"],
            ]
        )

        # MonthlyReport Poll All Users - опрос всех принтеров
        mr_poll_all_codes = set(mr_base)
        mr_poll_all_codes.update(
            [
                "monthly_report.view_monthlyreport",
                MR_APP_PERMS["poll_all"],
            ]
        )

        # Dashboard standalone group
        dash_viewer_codes = set([dash_access])

        # Group name mapping: English -> Russian (for all apps)
        name_map = {
            # Dashboard groups
            "Dashboard Viewer": "Дашборд — Просмотр",
            # Inventory groups
            "Inventory Viewer": "Инвентаризация — Просмотр",
            "Inventory Editor": "Инвентаризация — Редактор",
            "Inventory Admin": "Инвентаризация — Администратор",
            # Contracts groups
            "Contracts Viewer": "Договоры — Просмотр",
            "Contracts Editor": "Договоры — Редактор",
            "Contracts Admin": "Договоры — Администратор",
            # MonthlyReport groups
            "MonthlyReport Viewers": "Ежемесячные отчёты — Просмотр",
            "MonthlyReport Uploaders": "Ежемесячные отчёты — Загрузка",
            "MonthlyReport Editors (Start)": "Ежемесячные отчёты — Редакторы (начало)",
            "MonthlyReport Editors (End)": "Ежемесячные отчёты — Редакторы (конец)",
            "MonthlyReport Editors (Full)": "Ежемесячные отчёты — Редакторы (полные)",
            "MonthlyReport Sync Users": "Ежемесячные отчёты — Синхронизация",
            "MonthlyReport Managers": "Ежемесячные отчёты — Менеджеры",
            "MonthlyReport History Viewers": "Ежемесячные отчёты — История (просмотр)",
            "MonthlyReport Metrics Viewers": "Ежемесячные отчёты — Метрики (просмотр)",
            "MonthlyReport Month Visibility Managers": "Ежемесячные отчёты — Управление видимостью",
            "MonthlyReport Auto Polling Resetters": "Ежемесячные отчёты — Сброс автоопроса",
            "MonthlyReport Poll All Users": "Ежемесячные отчёты — Опрос всех принтеров",
        }

        # All groups with Russian names (rename from English if exists)
        all_groups = {
            # Dashboard
            "Dashboard Viewer": dash_viewer_codes,
            # Inventory
            "Inventory Viewer": inv_viewer_codes,
            "Inventory Editor": inv_editor_codes,
            "Inventory Admin": inv_admin_codes,
            # Contracts
            "Contracts Viewer": con_viewer_codes,
            "Contracts Editor": con_editor_codes,
            "Contracts Admin": con_admin_codes,
            # MonthlyReport
            "MonthlyReport Viewers": mr_viewer_codes,
            "MonthlyReport Uploaders": mr_uploader_codes,
            "MonthlyReport Editors (Start)": mr_editor_start_codes,
            "MonthlyReport Editors (End)": mr_editor_end_codes,
            "MonthlyReport Editors (Full)": mr_editor_full_codes,
            "MonthlyReport Sync Users": mr_sync_codes,
            "MonthlyReport Managers": mr_manager_codes,
            "MonthlyReport History Viewers": mr_history_codes,
            "MonthlyReport Metrics Viewers": mr_metrics_codes,
            "MonthlyReport Month Visibility Managers": mr_visibility_codes,
            "MonthlyReport Auto Polling Resetters": mr_reset_polling_codes,
            "MonthlyReport Poll All Users": mr_poll_all_codes,
        }

        for en_name, codes in all_groups.items():
            ru_name = name_map[en_name]
            group = self.get_or_rename_group(en_name, ru_name)
            perms = self.get_permissions(codes)
            group.permissions.set(list(perms))
            group.save()
            self.stdout.write(self.style.SUCCESS(f"Группа настроена: {ru_name} ({len(perms)} прав)"))

        self.stdout.write(self.style.SUCCESS("\nВсе группы RBAC инициализированы."))
