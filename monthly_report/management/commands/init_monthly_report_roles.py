# monthly_report/management/commands/init_monthly_report_roles.py
#
# DEPRECATED: This command is deprecated in favor of:
#   python manage.py bootstrap_roles
#
# All MonthlyReport groups and permissions are now managed in:
#   access/management/commands/bootstrap_roles.py
#
# This script is kept for backward compatibility but will be removed in a future release.
#
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps


class Command(BaseCommand):
    help = """
    [DEPRECATED] Use 'python manage.py bootstrap_roles' instead.

    Создаёт/обновляет группы и права для monthly_report.
    Эта команда устарела и будет удалена в будущих версиях.
    Используйте access/management/commands/bootstrap_roles.py
    """

    def handle(self, *args, **kwargs):
        VERSION = "init_monthly_report_roles v3-ru 2025-09-09 [DEPRECATED]"
        self.stdout.write(self.style.WARNING(
            "\n" + "="*80 + "\n"
            "ВНИМАНИЕ: Эта команда устарела!\n"
            "Используйте вместо неё: python manage.py bootstrap_roles\n"
            "Все группы monthly_report теперь управляются в access/management/commands/bootstrap_roles.py\n"
            "="*80 + "\n"
        ))
        self.stdout.write(f"{VERSION} | file: {__file__}")

        app_label = "monthly_report"

        MonthlyReport = apps.get_model(app_label, "MonthlyReport")
        MonthControl  = apps.get_model(app_label, "MonthControl")

        ct_report  = ContentType.objects.get_for_model(MonthlyReport)
        ct_control = ContentType.objects.get_for_model(MonthControl)

        # ---- КАСТОМНЫЕ ПРАВА (гарантируем наличие) ----
        custom_perms = [
            (ct_report, "access_monthly_report", "Доступ к разделу ежемесячных отчётов"),
            (ct_report, "upload_monthly_report", "Загрузка отчётов из Excel"),
            (ct_report, "edit_counters_start",  "Редактирование счётчиков (начало периода)"),
            (ct_report, "edit_counters_end",    "Редактирование счётчиков (конец периода)"),
            (ct_report, "sync_from_inventory",  "Синхронизация данных из Inventory"),
            (ct_report, "view_change_history",  "Просмотр истории изменений"),
            (ct_report, "view_monthly_report_metrics", "Просмотр метрик автозаполнения и пользователей"),
            (ct_report, "can_manage_month_visibility", "Управление видимостью месяцев (публикация/скрытие)"),
            (ct_report, "can_reset_auto_polling", "Возврат принтера на автоопрос"),
            (ct_report, "can_poll_all_printers", "Опрос всех принтеров одновременно"),
        ]
        for ct, codename, name in custom_perms:
            Permission.objects.get_or_create(
                content_type=ct, codename=codename, defaults={"name": name}
            )

        # ---- НУЖНЫЕ ПРАВА (включая стандартные) ----
        needed = {
            # стандартные model-perms
            "view_monthlyreport", "add_monthlyreport", "change_monthlyreport", "delete_monthlyreport",
            "view_monthcontrol", "change_monthcontrol",
            # кастомные
            "access_monthly_report", "upload_monthly_report",
            "edit_counters_start", "edit_counters_end",
            "sync_from_inventory",
            "view_change_history",
            "view_monthly_report_metrics",
            "can_manage_month_visibility",
            "can_reset_auto_polling",
            "can_poll_all_printers",
        }

        perms_qs = Permission.objects.filter(
            content_type__in=[ct_report, ct_control],
            codename__in=needed
        )
        perms = {p.codename: p for p in perms_qs}

        # ---- Карта переименования: EN -> RU ----
        name_map = {
            "MonthlyReport Viewers":            "Ежемесячные отчёты — Просмотр",
            "MonthlyReport Uploaders":          "Ежемесячные отчёты — Загрузка",
            "MonthlyReport Editors (Start)":    "Ежемесячные отчёты — Редакторы (начало)",
            "MonthlyReport Editors (End)":      "Ежемесячные отчёты — Редакторы (конец)",
            "MonthlyReport Editors (Full)":     "Ежемесячные отчёты — Редакторы (полные)",
            "MonthlyReport Sync Users":         "Ежемесячные отчёты — Синхронизация",
            "MonthlyReport Managers":           "Ежемесячные отчёты — Менеджеры",
            "MonthlyReport History Viewers":    "Ежемесячные отчёты — История (просмотр)",
            "MonthlyReport Metrics Viewers":    "Ежемесячные отчёты — Метрики (просмотр)",
            "MonthlyReport Month Visibility Managers": "Ежемесячные отчёты — Управление видимостью",
            "MonthlyReport Auto Polling Resetters": "Ежемесячные отчёты — Сброс автоопроса",
            "MonthlyReport Poll All Users":     "Ежемесячные отчёты — Опрос всех принтеров",
        }

        # Набор русских имён (для удобства)
        RU = set(name_map.values())

        def get_or_rename_group(en_name: str, ru_name: str) -> Group:
            """
            Возвращает группу с русским именем.
            - если русская уже есть — берём её;
            - иначе, если есть старая английская — ПЕРЕИМЕНОВЫВАЕМ её в русскую (сохраняя участников/права);
            - иначе создаём новую с русским именем.
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

        def add_perms(group: Group, codes: set[str]):
            group.permissions.add(*[perms[c] for c in codes if c in perms])

        # ---- Создаём/переименовываем группы и назначаем права ----
        viewers = get_or_rename_group("MonthlyReport Viewers", name_map["MonthlyReport Viewers"])
        uploaders = get_or_rename_group("MonthlyReport Uploaders", name_map["MonthlyReport Uploaders"])
        editors_start = get_or_rename_group("MonthlyReport Editors (Start)", name_map["MonthlyReport Editors (Start)"])
        editors_end   = get_or_rename_group("MonthlyReport Editors (End)",   name_map["MonthlyReport Editors (End)"])
        editors_full  = get_or_rename_group("MonthlyReport Editors (Full)",  name_map["MonthlyReport Editors (Full)"])
        sync_users    = get_or_rename_group("MonthlyReport Sync Users",      name_map["MonthlyReport Sync Users"])
        managers      = get_or_rename_group("MonthlyReport Managers",        name_map["MonthlyReport Managers"])
        history_viewers = get_or_rename_group("MonthlyReport History Viewers", name_map["MonthlyReport History Viewers"])
        metrics_viewers = get_or_rename_group("MonthlyReport Metrics Viewers", name_map["MonthlyReport Metrics Viewers"])
        month_visibility_managers = get_or_rename_group("MonthlyReport Month Visibility Managers", name_map["MonthlyReport Month Visibility Managers"])
        auto_polling_resetters = get_or_rename_group("MonthlyReport Auto Polling Resetters", name_map["MonthlyReport Auto Polling Resetters"])
        poll_all_users = get_or_rename_group("MonthlyReport Poll All Users", name_map["MonthlyReport Poll All Users"])

        # Просмотр
        add_perms(viewers, {
            "access_monthly_report", "view_monthlyreport", "view_monthcontrol",
        })

        # Загрузка Excel
        add_perms(uploaders, {
            "access_monthly_report", "view_monthlyreport", "view_monthcontrol",
            "upload_monthly_report", "add_monthlyreport",
        })

        # Редакторы начала
        add_perms(editors_start, {
            "access_monthly_report", "view_monthlyreport",
            "change_monthlyreport", "edit_counters_start",
        })

        # Редакторы конца
        add_perms(editors_end, {
            "access_monthly_report", "view_monthlyreport",
            "change_monthlyreport", "edit_counters_end",
        })

        # Полные редакторы
        add_perms(editors_full, {
            "access_monthly_report", "view_monthlyreport",
            "change_monthlyreport", "edit_counters_start", "edit_counters_end",
        })

        # Синхронизация
        add_perms(sync_users, {
            "access_monthly_report", "view_monthlyreport",
            "sync_from_inventory",
        })

        # Менеджеры (всё + история + новые права)
        add_perms(managers, {
            "access_monthly_report", "view_monthlyreport", "upload_monthly_report",
            "add_monthlyreport", "change_monthlyreport", "delete_monthlyreport",
            "edit_counters_start", "edit_counters_end",
            "view_monthcontrol", "change_monthcontrol",
            "sync_from_inventory",
            "view_change_history",
            "view_monthly_report_metrics",
            "can_manage_month_visibility",
            "can_reset_auto_polling",
            "can_poll_all_printers",
        })

        # История (просмотр истории + метрики нужны для просмотра изменений)
        add_perms(history_viewers, {
            "access_monthly_report", "view_monthlyreport",
            "view_change_history",
            "view_monthly_report_metrics",
        })

        # Метрики (просмотр метрик автозаполнения и статистики)
        add_perms(metrics_viewers, {
            "access_monthly_report", "view_monthlyreport",
            "view_monthly_report_metrics",
        })

        # Управление видимостью месяцев
        add_perms(month_visibility_managers, {
            "access_monthly_report", "view_monthlyreport", "view_monthcontrol",
            "can_manage_month_visibility",
        })

        # Сброс автоопроса
        add_perms(auto_polling_resetters, {
            "access_monthly_report", "view_monthlyreport",
            "can_reset_auto_polling",
            "view_change_history",
        })

        # Опрос всех принтеров
        add_perms(poll_all_users, {
            "access_monthly_report", "view_monthlyreport",
            "can_poll_all_printers",
        })

        # ---- Вывод итогов ----
        groups = [
            viewers, uploaders, editors_start, editors_end,
            editors_full, sync_users, managers, history_viewers,
            metrics_viewers, month_visibility_managers, auto_polling_resetters, poll_all_users
        ]
        self.stdout.write(self.style.SUCCESS("Группы и права настроены."))
        for grp in groups:
            self.stdout.write(f" - {grp.name}: {grp.permissions.count()} прав")
