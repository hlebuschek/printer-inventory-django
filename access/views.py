import json

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import AllowedUser, EntityChangeLog, UserOkdeskToken, UserThemePreference
from .services.change_log_service import ChangeLogService


@login_required
@require_http_methods(["GET", "POST"])
def theme_preference_api(request):
    """
    API для работы с настройками темы пользователя.

    GET: Получить текущую тему пользователя
    POST: Сохранить тему пользователя
    """
    if request.method == "GET":
        try:
            pref = UserThemePreference.objects.get(user=request.user)
            return JsonResponse({"ok": True, "theme": pref.theme, "updated_at": pref.updated_at.isoformat()})
        except UserThemePreference.DoesNotExist:
            return JsonResponse({"ok": True, "theme": None, "updated_at": None})  # Настройки ещё не сохранены

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            theme = data.get("theme", "light")

            # Валидация
            valid_themes = ["light", "dark", "system"]
            if theme not in valid_themes:
                return JsonResponse(
                    {"ok": False, "error": f"Invalid theme. Must be one of: {', '.join(valid_themes)}"}, status=400
                )

            # Создаём или обновляем настройки
            pref, created = UserThemePreference.objects.update_or_create(user=request.user, defaults={"theme": theme})

            return JsonResponse(
                {"ok": True, "theme": pref.theme, "created": created, "updated_at": pref.updated_at.isoformat()}
            )

        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=500)


@login_required
def permissions_overview(request):
    u = request.user

    apps = [
        {
            "name": "Опрос устройств",
            "code": "inventory",
            "access": u.has_perm("inventory.access_inventory_app"),
            "can_view": any(
                u.has_perm(f"inventory.view_{m}") for m in ["printer", "organization", "inventorytask", "pagecounter"]
            ),
            "can_edit": any(u.has_perm(f"inventory.change_{m}") for m in ["printer", "organization", "inventorytask"]),
            "can_add": any(u.has_perm(f"inventory.add_{m}") for m in ["printer", "organization", "inventorytask"]),
            "can_delete": any(
                u.has_perm(f"inventory.delete_{m}") for m in ["printer", "organization", "inventorytask"]
            ),
            "special": {
                "Запуск опроса": u.has_perm("inventory.run_inventory"),
                "Опрос всех принтеров": u.has_perm("monthly_report.can_poll_all_printers"),
                "Экспорт в excel": u.has_perm("inventory.export_printers"),
                "Отчет для АМБ": u.has_perm("inventory.export_amb_report"),
                "Управление веб-парсингом": u.has_perm("inventory.manage_web_parsing"),  # 🆕
                "Просмотр веб-парсинга": u.has_perm("inventory.view_web_parsing"),  # 🆕
            },
        },
        {
            "name": "Устройства в договоре",
            "code": "contracts",
            "access": u.has_perm("contracts.access_contracts_app"),
            "can_view": any(
                u.has_perm(f"contracts.view_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_edit": any(
                u.has_perm(f"contracts.change_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_add": any(
                u.has_perm(f"contracts.add_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_delete": any(
                u.has_perm(f"contracts.delete_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "special": {
                "Экспорт в excel": u.has_perm("contracts.export_contracts"),
                "Просмотр заявок Okdesk": u.has_perm("integrations.view_okdesk_issues"),
                "Подача заявок подрядчику": u.has_perm("contracts.create_service_request"),
                "Управление токеном Okdesk": u.has_perm("integrations.manage_okdesk_token"),
            },
        },
        {
            "name": "Дашборд",
            "code": "dashboard",
            "access": u.has_perm("dashboard.access_dashboard_app"),
            "can_view": False,
            "can_edit": False,
            "can_add": False,
            "can_delete": False,
            "special": {
                "Доступ к дашборду": u.has_perm("dashboard.access_dashboard_app"),
            },
        },
        {
            "name": "Ежемесячные отчёты",
            "code": "monthly_report",
            # колонка «Доступ»
            "access": (u.has_module_perms("monthly_report") or u.has_perm("monthly_report.access_monthly_report")),
            # базовые CRUD для строки приложения
            "can_view": any(u.has_perm(f"monthly_report.view_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_add": any(u.has_perm(f"monthly_report.add_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_edit": any(u.has_perm(f"monthly_report.change_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_delete": any(u.has_perm(f"monthly_report.delete_{m}") for m in ("monthlyreport", "monthcontrol")),
            # спец-права (правая колонка)
            "special": {
                "Доступ к модулю": u.has_perm("monthly_report.access_monthly_report"),
                "Загрузка Excel": u.has_perm("monthly_report.upload_monthly_report"),
                "Редактировать поля *_start": u.has_perm("monthly_report.edit_counters_start"),
                "Редактировать поля *_end": u.has_perm("monthly_report.edit_counters_end"),
                "Синхронизация из Inventory": u.has_perm("monthly_report.sync_from_inventory"),
                "Просмотр истории изменений": u.has_perm("monthly_report.view_change_history"),
                "Управление видимостью месяцев": u.has_perm("monthly_report.can_manage_month_visibility"),
                "Возврат на автоопрос": u.has_perm("monthly_report.can_reset_auto_polling"),
            },
        },
    ]

    context = {
        "initial_data_json": json.dumps({"apps": apps}),
    }
    return render(request, "access/permissions_overview.html", context)


@login_required
@permission_required("integrations.manage_okdesk_token")
@require_http_methods(["GET", "POST"])
def okdesk_token_api(request):
    """
    API для управления API-токеном Okdesk пользователя.

    GET: Проверить наличие токена
    POST: Сохранить токен {"token": "..."}
    """
    if request.method == "GET":
        has_token = UserOkdeskToken.objects.filter(user=request.user).exists()
        return JsonResponse({"ok": True, "has_token": has_token})

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            token = data.get("token", "").strip()

            if not token:
                return JsonResponse({"ok": False, "error": "Токен не может быть пустым"}, status=400)

            obj, _ = UserOkdeskToken.objects.get_or_create(user=request.user, defaults={"encrypted_token": ""})
            obj.set_token(token)
            obj.save()

            return JsonResponse({"ok": True, "message": "Токен сохранён"})

        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)


# ──────────────────────────────────────────────────────────────────────────────
# Управление пользователями (whitelist + группы)
# ──────────────────────────────────────────────────────────────────────────────

TRACKED_USER_FIELDS = ["username", "full_name", "email", "notes", "is_active"]


def _group_catalog():
    """Группы, разбитые на категории по названию вида 'Приложение — Роль'."""
    catalog = []
    for group in Group.objects.order_by("name"):
        category, separator, title = group.name.partition("—")
        catalog.append(
            {
                "id": group.id,
                "name": group.name,
                "category": category.strip() if separator else "Прочее",
                "title": title.strip() if separator else group.name,
            }
        )
    return catalog


def _serialize_allowed_user(allowed, django_user):
    """
    Права живут на Django-пользователе, но до первого входа его ещё нет —
    тогда показываем и правим initial_groups.
    """
    if django_user:
        group_ids = sorted(g.id for g in django_user.groups.all())
    else:
        group_ids = sorted(g.id for g in allowed.initial_groups.all())

    return {
        "id": allowed.id,
        "username": allowed.username,
        "full_name": allowed.full_name,
        "email": allowed.email,
        "notes": allowed.notes,
        "is_active": allowed.is_active,
        "added_at": allowed.added_at.isoformat() if allowed.added_at else None,
        "added_by": allowed.added_by,
        "group_ids": group_ids,
        "has_django_user": django_user is not None,
        "is_superuser": bool(django_user and django_user.is_superuser),
        "last_login": django_user.last_login.isoformat() if django_user and django_user.last_login else None,
    }


def _group_names(group_ids, catalog_by_id):
    return sorted(catalog_by_id[gid]["name"] for gid in group_ids if gid in catalog_by_id)


def _log_user_change(allowed, request, created, old_data, old_groups, new_groups):
    if created:
        entry = ChangeLogService.log_create(allowed, request.user, request)
    else:
        entry = ChangeLogService.log_update(allowed, request.user, request, old_data)

    if sorted(old_groups) == sorted(new_groups):
        return

    changes = dict(entry.changes) if entry else {}
    changes["groups"] = {
        "old": ", ".join(sorted(old_groups)) or None,
        "new": ", ".join(sorted(new_groups)) or None,
        "label": "Группы",
    }
    if entry:
        entry.changes = changes
        entry.save(update_fields=["changes"])
    else:
        EntityChangeLog.objects.create(
            content_type=ContentType.objects.get_for_model(AllowedUser),
            object_id=allowed.pk,
            action="update",
            user=request.user,
            changes=changes,
            object_repr=str(allowed)[:500],
            ip_address=ChangeLogService.get_ip_from_request(request),
            user_agent=ChangeLogService.get_user_agent(request),
        )


@login_required
@permission_required("access.manage_users", raise_exception=True)
def user_management(request):
    context = {
        "initial_data_json": json.dumps(
            {
                "groups": _group_catalog(),
                "currentUsername": request.user.username,
            }
        )
    }
    return render(request, "access/user_management.html", context)


@login_required
@permission_required("access.manage_users", raise_exception=True)
@require_http_methods(["GET"])
def users_api(request):
    allowed_users = AllowedUser.objects.prefetch_related("initial_groups").order_by("-is_active", "username")
    django_users = {u.username.lower(): u for u in User.objects.prefetch_related("groups")}

    return JsonResponse(
        {
            "ok": True,
            "users": [_serialize_allowed_user(a, django_users.get(a.username.lower())) for a in allowed_users],
        }
    )


@login_required
@permission_required("access.manage_users", raise_exception=True)
@require_http_methods(["POST"])
def user_save_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)

    username = (data.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "error": "Логин обязателен"}, status=400)

    user_id = data.get("id")
    is_active = bool(data.get("is_active", True))
    group_ids = data.get("group_ids") or []

    catalog_by_id = {g["id"]: g for g in _group_catalog()}
    unknown = [gid for gid in group_ids if gid not in catalog_by_id]
    if unknown:
        return JsonResponse({"ok": False, "error": f"Неизвестные группы: {unknown}"}, status=400)

    duplicate = AllowedUser.objects.filter(username__iexact=username).exclude(pk=user_id).exists()
    if duplicate:
        return JsonResponse({"ok": False, "error": f"Пользователь '{username}' уже есть в списке"}, status=400)

    allowed = None
    old_data = None
    old_groups = []
    if user_id:
        allowed = AllowedUser.objects.filter(pk=user_id).first()
        if not allowed:
            return JsonResponse({"ok": False, "error": "Запись не найдена"}, status=404)
        if allowed.username.lower() == request.user.username.lower() and not is_active:
            return JsonResponse({"ok": False, "error": "Нельзя отключить собственную учётную запись"}, status=400)
        old_data = ChangeLogService.get_model_data(allowed)

    django_user = User.objects.filter(username__iexact=allowed.username if allowed else username).first()
    if allowed and django_user and allowed.username.lower() != username.lower():
        return JsonResponse(
            {"ok": False, "error": "Логин нельзя менять: пользователь уже заходил в систему"}, status=400
        )

    if django_user:
        old_groups = [g.name for g in django_user.groups.all()]
    elif allowed:
        old_groups = [g.name for g in allowed.initial_groups.all()]
    new_groups = _group_names(group_ids, catalog_by_id)

    with transaction.atomic():
        created = allowed is None
        if created:
            allowed = AllowedUser(username=username, added_by=request.user.username)

        allowed.username = username
        allowed.full_name = (data.get("full_name") or "").strip()
        allowed.email = (data.get("email") or "").strip()
        allowed.notes = (data.get("notes") or "").strip()
        allowed.is_active = is_active
        allowed.save()

        allowed.initial_groups.set(group_ids)

        if django_user:
            django_user.groups.set(group_ids)
            if not django_user.is_superuser and django_user.is_active != is_active:
                django_user.is_active = is_active
                django_user.save(update_fields=["is_active"])

        _log_user_change(allowed, request, created, old_data, old_groups, new_groups)

    allowed.refresh_from_db()
    django_user = User.objects.filter(username__iexact=allowed.username).prefetch_related("groups").first()
    return JsonResponse({"ok": True, "user": _serialize_allowed_user(allowed, django_user)})


@login_required
@permission_required("access.manage_users", raise_exception=True)
@require_http_methods(["POST"])
def user_delete_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)

    allowed = AllowedUser.objects.filter(pk=data.get("id")).first()
    if not allowed:
        return JsonResponse({"ok": False, "error": "Запись не найдена"}, status=404)
    if allowed.username.lower() == request.user.username.lower():
        return JsonResponse({"ok": False, "error": "Нельзя удалить собственную учётную запись"}, status=400)

    with transaction.atomic():
        ChangeLogService.log_delete(allowed, request.user, request)
        django_user = User.objects.filter(username__iexact=allowed.username).first()
        if django_user and not django_user.is_superuser:
            django_user.is_active = False
            django_user.save(update_fields=["is_active"])
        allowed.delete()

    return JsonResponse({"ok": True})
