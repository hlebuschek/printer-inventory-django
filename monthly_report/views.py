from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from django.apps import apps
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, OuterRef, Subquery
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .forms import ExcelUploadForm
from .models import MonthlyReport, MonthControl, CounterChangeLog
from .services import recompute_group
from .services.audit_service import AuditService
from .specs import get_spec_for_model_name, allowed_counter_fields

logger = logging.getLogger(__name__)

COUNTER_FIELDS = {
    "a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end",
    "a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end",
}


def _to_int(x):
    try:
        if x in (None, ""):
            return 0
        s = str(x).replace(" ", "").replace(",", ".")
        return int(float(s))
    except Exception:
        return 0


class MonthListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'monthly_report/month_list.html'
    context_object_name = 'months'
    permission_required = 'monthly_report.access_monthly_report'
    raise_exception = True

    def get_queryset(self):
        return (
            MonthlyReport.objects
            .annotate(month_trunc=TruncMonth('month'))
            .values('month_trunc')
            .annotate(count=Count('id'))
            .order_by('-month_trunc')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        months = list(ctx['months'])

        def month_key(dt):
            return dt.date() if hasattr(dt, 'date') else dt

        keys = []
        for rec in months:
            rec['_key'] = month_key(rec['month_trunc'])
            keys.append(rec['_key'])

        controls = {mc.month: mc for mc in MonthControl.objects.filter(month__in=keys)}
        now = timezone.now()
        for rec in months:
            mc = controls.get(rec['_key'])
            rec['is_editable'] = bool(mc and mc.edit_until and now < mc.edit_until)
            rec['edit_until'] = mc.edit_until if mc else None

        ctx['months'] = months
        return ctx


class MonthDetailView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'monthly_report/month_detail.html'
    context_object_name = 'reports'
    permission_required = 'monthly_report.access_monthly_report'
    raise_exception = True
    paginate_by = 100

    PER_CHOICES = [100, 200, 500, 1000, 2000, 5000]
    DEFAULT_PER = 100

    FILTER_MAP = {
        'org':    'organization__icontains',
        'branch': 'branch__icontains',
        'city':   'city__icontains',
        'address':'address__icontains',
        'model':  'equipment_model__icontains',
        'serial': 'serial_number__icontains',
        'inv':    'inventory_number__icontains',
        'num':    None,
    }

    SORT_MAP = {
        'org': 'organization', 'branch': 'branch', 'city': 'city', 'address': 'address',
        'model': 'equipment_model', 'serial': 'serial_number', 'inv': 'inventory_number',
        'total': 'total_prints', 'k1': 'k1', 'k2': 'k2', 'A': 'normative_availability',
        'D': 'actual_downtime', 'L': 'non_overdue_requests', 'W': 'total_requests',
        'num': 'order_number',
    }

    def get_paginate_by(self, queryset):
        per = self.request.GET.get('per', '').strip()
        if per == 'all':
            return None
        try:
            per_i = int(per)
            if per_i in self.PER_CHOICES:
                return per_i
        except (TypeError, ValueError):
            pass
        return self.DEFAULT_PER

    def _month_tuple(self):
        y, m = self.kwargs['month'].split('-')
        return int(y), int(m)

    def get_queryset(self):
        import re
        y, m = self._month_tuple()
        qs = MonthlyReport.objects.filter(month__year=y, month__month=m)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(organization__icontains=q) | Q(branch__icontains=q) | Q(city__icontains=q) |
                Q(address__icontains=q) | Q(equipment_model__icontains=q) |
                Q(serial_number__icontains=q) | Q(inventory_number__icontains=q)
            )

        # ИЗМЕНЕННАЯ ЧАСТЬ: используем icontains вместо точного совпадения
        for key, lookup in self.FILTER_MAP.items():
            if not lookup:
                continue
            val = self.request.GET.get(key, '').strip()
            if val:
                qs = qs.filter(**{lookup: val})

        num_val = self.request.GET.get('num', '').strip()
        if num_val:
            if re.fullmatch(r'\d+', num_val):
                qs = qs.filter(order_number=int(num_val))
            elif re.fullmatch(r'\d+\s*-\s*\d+', num_val):
                a, b = [int(x) for x in re.split(r'\s*-\s*', num_val)]
                if a > b:
                    a, b = b, a
                qs = qs.filter(order_number__gte=a, order_number__lte=b)
            else:
                nums = [int(n) for n in re.findall(r'\d+', num_val)]
                if nums:
                    qs = qs.filter(order_number__in=nums)

        sort = self.request.GET.get('sort', '').strip()
        if sort:
            desc = sort.startswith('-')
            key = sort[1:] if desc else sort
            field = self.SORT_MAP.get(key)
            if field:
                qs = qs.order_by(('-' if desc else '') + field)
        else:
            qs = qs.order_by('order_number', 'organization', 'city', 'equipment_model', 'serial_number')

        return qs

    def get_context_data(self, **kwargs):
        from collections import defaultdict

        ctx = super().get_context_data(**kwargs)
        y, m = self._month_tuple()
        month_dt = date(y, m, 1)

        # базовая информация о месяце
        ctx['month_str'] = f"{y:04d}-{m:02d}"
        ctx['month_date'] = month_dt

        # текущие значения фильтров
        ctx['filters'] = {
            'num': self.request.GET.get('num', ''),
            'org': self.request.GET.get('org', ''),
            'branch': self.request.GET.get('branch', ''),
            'city': self.request.GET.get('city', ''),
            'address': self.request.GET.get('address', ''),
            'model': self.request.GET.get('model', ''),
            'serial': self.request.GET.get('serial', ''),
            'inv': self.request.GET.get('inv', ''),
            'q': self.request.GET.get('q', ''),
        }

        # варианты для подсказок (distinct по месяцу) - БЕЗ ОГРАНИЧЕНИЙ
        base_qs = MonthlyReport.objects.filter(month__year=y, month__month=m)

        def opts(field):
            return (
                base_qs
                .exclude(**{f"{field}__isnull": True})
                .exclude(**{field: ''})
                .values_list(field, flat=True)
                .distinct()
                .order_by(field)
            )

        ctx['choices'] = {
            'num': [
                str(n) for n in base_qs
                .exclude(order_number__isnull=True)
                .values_list('order_number', flat=True)
                .distinct().order_by('order_number')
            ],
            'org': list(opts('organization')),
            'branch': list(opts('branch')),
            'city': list(opts('city')),
            'address': list(opts('address')),
            'model': list(opts('equipment_model')),
            'serial': list(opts('serial_number')),
            'inv': list(opts('inventory_number')),
        }

        # base_qs для ссылок (сохраняем per, убираем page)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['base_qs'] = params.urlencode()

        # qs без per — для меню "на странице"
        params2 = self.request.GET.copy()
        params2.pop('page', None)
        params2.pop('per', None)
        ctx['qs_no_per'] = params2.urlencode()

        # текущее значение per
        per = (self.request.GET.get('per') or '').strip()
        if per == 'all':
            per_current = 'all'
        else:
            try:
                per_i = int(per)
                per_current = per_i if per_i in self.PER_CHOICES else self.DEFAULT_PER
            except (TypeError, ValueError):
                per_current = self.DEFAULT_PER

        ctx['per_choices'] = self.PER_CHOICES
        ctx['per_default'] = self.DEFAULT_PER
        ctx['per_current'] = per_current

        # ---- подсветка дублей и расчёт ui_total по "верх/низ" ----
        full_qs = self.get_queryset().values('id', 'serial_number', 'inventory_number')
        from collections import defaultdict as _dd
        groups = _dd(list)
        for r in full_qs:
            sn = (r['serial_number'] or '').strip()
            inv = (r['inventory_number'] or '').strip()
            if not sn and not inv:
                continue
            groups[(sn, inv)].append(r['id'])

        id_to_pos, dup_ids = {}, set()
        for ids in groups.values():
            if len(ids) >= 2:
                ids = sorted(ids)
                dup_ids.update(ids)
                for pos, rid in enumerate(ids):
                    id_to_pos[rid] = pos  # 0 — верхняя, 1.. — нижние

        def nz(x):
            return int(x or 0)

        for obj in ctx['object_list']:
            obj.ui_is_dup = obj.id in dup_ids
            pos = id_to_pos.get(obj.id, None)
            a4 = max(0, nz(obj.a4_bw_end) - nz(obj.a4_bw_start)) + max(0, nz(obj.a4_color_end) - nz(obj.a4_color_start))
            a3 = max(0, nz(obj.a3_bw_end) - nz(obj.a3_bw_start)) + max(0, nz(obj.a3_color_end) - nz(obj.a3_color_start))
            obj.ui_total = a4 + a3 if pos is None else (a4 if pos == 0 else a3)

        # --- окно редактирования и права ---
        mc = MonthControl.objects.filter(month=month_dt).first()
        now_open = bool(mc and mc.edit_until and timezone.now() < mc.edit_until)
        ctx['report_is_editable'] = now_open
        ctx['report_edit_until'] = mc.edit_until if mc else None

        u = self.request.user
        ctx['can_edit_end'] = u.has_perm('monthly_report.edit_counters_end')
        ctx['can_edit_start'] = u.has_perm('monthly_report.edit_counters_start')

        # --- разрешённые поля для каждой строки ---
        can_start = ctx['can_edit_start']
        can_end = ctx['can_edit_end']
        report_is_editable = ctx['report_is_editable']

        allowed_by_perm = set()
        if can_start:
            allowed_by_perm |= {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"}
        if can_end:
            allowed_by_perm |= {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}

        rows = ctx[self.context_object_name]
        if not report_is_editable or not allowed_by_perm:
            for r in rows:
                for f in COUNTER_FIELDS:
                    setattr(r, f"ui_allow_{f}", False)
        else:
            for r in rows:
                spec = get_spec_for_model_name(r.equipment_model)
                allowed_by_spec = allowed_counter_fields(spec)
                allowed_final = (allowed_by_perm & allowed_by_spec) if allowed_by_spec else allowed_by_perm
                for f in COUNTER_FIELDS:
                    setattr(r, f"ui_allow_{f}", f in allowed_final)
        from .models_modelspec import PaperFormat

        for r in rows:
            spec = get_spec_for_model_name(r.equipment_model)
            allowed_by_spec = allowed_counter_fields(spec)

            # Сохраняем информацию о правилах для отображения в UI
            r.ui_model_spec = spec
            r.ui_spec_enforced = bool(spec and spec.enforce)
            r.ui_spec_info = None

            if spec and spec.enforce:
                # Формируем понятное описание ограничений
                formats = []
                if spec.paper_format == PaperFormat.A4_ONLY:
                    formats.append("A4")
                elif spec.paper_format == PaperFormat.A3_ONLY:
                    formats.append("A3")
                else:  # A4_A3
                    formats.append("A4+A3")

                color_info = "цветной" if spec.is_color else "ч/б"
                r.ui_spec_info = f"{', '.join(formats)}, {color_info}"

            # Для каждого поля добавляем причину блокировки
            for f in COUNTER_FIELDS:
                allowed = getattr(r, f"ui_allow_{f}", False)
                reason = None

                if not report_is_editable:
                    reason = "Месяц закрыт для редактирования"
                elif not allowed_by_perm:
                    reason = "Нет прав на редактирование"
                elif f not in allowed_by_perm:
                    if f.endswith('_start') and not can_start:
                        reason = "Нет права на изменение полей 'начало'"
                    elif f.endswith('_end') and not can_end:
                        reason = "Нет права на изменение полей 'конец'"
                elif allowed_by_spec and f not in allowed_by_spec:
                    # Определяем конкретную причину блокировки по модели
                    if spec and spec.enforce:
                        if f.startswith('a4_') and spec.paper_format == PaperFormat.A3_ONLY:
                            reason = "Модель поддерживает только A3"
                        elif f.startswith('a3_') and spec.paper_format == PaperFormat.A4_ONLY:
                            reason = "Модель поддерживает только A4"
                        elif 'color' in f and not spec.is_color:
                            reason = "Монохромная модель (все отпечатки ч/б)"
                        elif 'bw' in f and spec.is_color:
                            reason = "Цветная модель (все отпечатки цветные)"
                        else:
                            reason = f"Ограничено правилами модели ({r.ui_spec_info})"
                    else:
                        reason = "Ограничено правилами модели"

                setattr(r, f"ui_block_reason_{f}", reason)

        # Проверка устаревших данных
        now = timezone.now()
        STALE_DAYS = 7
        for r in ctx['object_list']:
            r.ui_poll_stale = bool(r.inventory_last_ok and (now - r.inventory_last_ok) > timedelta(days=STALE_DAYS))

        return ctx


@login_required
@permission_required('monthly_report.upload_monthly_report', raise_exception=True)
def upload_excel(request):
    """
    Загрузка Excel с аудитом массовой операции
    """
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Начинаем логирование массовой операции
            bulk_log = AuditService.start_bulk_operation(
                user=request.user,
                operation_type='excel_upload',
                operation_params={
                    'filename': request.FILES['excel_file'].name,
                    'month': form.cleaned_data['month'].isoformat(),
                    'replace_month': form.cleaned_data.get('replace_month', False),
                    'allow_edit': form.cleaned_data.get('allow_edit', False),
                },
                request=request,
                month=form.cleaned_data['month']
            )

            try:
                count = form.process_data()

                # Завершаем логирование успешно
                AuditService.finish_bulk_operation(
                    bulk_log=bulk_log,
                    records_affected=count,
                    fields_changed=['multiple_counters'],
                    success=True
                )

                return render(request, 'monthly_report/upload_success.html', {
                    'count': count,
                    'bulk_log_id': bulk_log.id
                })
            except Exception as e:
                # Завершаем логирование с ошибкой
                AuditService.finish_bulk_operation(
                    bulk_log=bulk_log,
                    records_affected=0,
                    fields_changed=[],
                    success=False,
                    error_message=str(e)
                )
                raise
    else:
        form = ExcelUploadForm()
    return render(request, 'monthly_report/upload.html', {'form': form})


@login_required
@require_POST
def api_update_counters(request, pk: int):
    """
    Обновляет счётчики одной записи при открытом месяце + записывает аудит
    """
    obj = get_object_or_404(MonthlyReport, pk=pk)

    # окно редактирования
    mc = MonthControl.objects.filter(month=obj.month).first()
    if not (mc and getattr(mc, "is_editable", False)):
        return HttpResponseForbidden(_("Отчёт закрыт для редактирования"))

    # права пользователя
    user = request.user
    can_start = user.has_perm("monthly_report.edit_counters_start")
    can_end = user.has_perm("monthly_report.edit_counters_end")

    allowed_by_perm = set()
    if can_start:
        allowed_by_perm |= {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"}
    if can_end:
        allowed_by_perm |= {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}
    if not allowed_by_perm:
        return HttpResponseForbidden(_("Нет прав для изменения счётчиков"))

    # ограничения по справочнику модели
    spec = get_spec_for_model_name(obj.equipment_model)
    allowed_by_spec = allowed_counter_fields(spec)

    # итоговый whitelist
    allowed_fields = (allowed_by_perm & allowed_by_spec) if allowed_by_spec else allowed_by_perm
    if not allowed_fields:
        return HttpResponseForbidden(_("Для этой модели редактирование счётчиков запрещено правилами."))

    # парсим payload
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid json")

    fields = payload.get("fields", payload if isinstance(payload, dict) else {})
    if not isinstance(fields, dict):
        return HttpResponseBadRequest("invalid fields")

    # Собираем изменения для аудита
    changes_for_audit = {}
    updated, ignored = [], []

    for name, val in fields.items():
        if name not in COUNTER_FIELDS:
            continue
        if name not in allowed_fields:
            ignored.append(name)
            continue

        # Запоминаем старое значение для аудита
        old_value = getattr(obj, name)
        new_value = _to_int(val)

        # Записываем изменение
        setattr(obj, name, new_value)
        updated.append(name)

        # Сохраняем для аудита только если значение изменилось
        if old_value != new_value:
            changes_for_audit[name] = (old_value, new_value)

        # любое ручное изменение *_end отключает авто-сопровождение
        if name.endswith('_end'):
            auto_flag = f"{name}_auto"
            if hasattr(obj, auto_flag) and getattr(obj, auto_flag):
                old_auto_value = getattr(obj, auto_flag)
                setattr(obj, auto_flag, 0)  # сбрасываем в 0
                updated.append(auto_flag)

                # Логируем отключение автосинхронизации
                if old_auto_value != 0:
                    changes_for_audit[auto_flag] = (old_auto_value, 0)

    if not updated:
        return JsonResponse(
            {"ok": False, "error": _("Нет разрешённых к изменению полей"), "ignored_fields": ignored},
            status=400
        )

    # Сохраняем объект
    obj.save(update_fields=updated)

    # АУДИТ: Записываем историю изменений
    if changes_for_audit:
        try:
            AuditService.log_multiple_changes(
                monthly_report=obj,
                user=user,
                changes=changes_for_audit,
                request=request,
                change_source='manual',
                comment='Обновление через веб-интерфейс'
            )
        except Exception as e:
            # Не прерываем выполнение если аудит не сработал
            logger.error(f"Ошибка записи аудита: {e}")

    # пересчитываем только свою группу
    recompute_group(obj.month, obj.serial_number, obj.inventory_number)

    obj.refresh_from_db()

    return JsonResponse({
        "ok": True,
        "report": {
            "id": obj.id,
            "a4_bw_start": obj.a4_bw_start, "a4_bw_end": obj.a4_bw_end,
            "a4_color_start": obj.a4_color_start, "a4_color_end": obj.a4_color_end,
            "a3_bw_start": obj.a3_bw_start, "a3_bw_end": obj.a3_bw_end,
            "a3_color_start": obj.a3_color_start, "a3_color_end": obj.a3_color_end,
            "total_prints": obj.total_prints,
        },
        "updated_fields": updated,
        "ignored_fields": ignored,
        "changes_logged": len(changes_for_audit),  # Сколько изменений записано в аудит
    })


@login_required
@require_POST
def api_sync_from_inventory(request, year: int, month: int):
    """
    API для синхронизации данных с inventory.
    """
    if not request.user.has_perm('monthly_report.sync_from_inventory'):
        return JsonResponse({"ok": False, "error": "Нет права: monthly_report.sync_from_inventory"}, status=403)

    month_date = date(int(year), int(month), 1)
    mc = MonthControl.objects.filter(month=month_date).first()
    if not (mc and mc.edit_until and timezone.now() < mc.edit_until):
        return JsonResponse({"ok": False, "error": "Отчёт закрыт"}, status=403)

    try:
        from .services_inventory_sync import sync_month_from_inventory
        result = sync_month_from_inventory(month_date, only_empty=True) or {}
        result.setdefault("ok", True)
        return JsonResponse(result)
    except Exception as e:
        logger.exception(f"Ошибка синхронизации: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@login_required
@permission_required('monthly_report.view_change_history', raise_exception=True)
def change_history_view(request, pk: int):
    """
    Просмотр истории изменений для записи.
    Требует право monthly_report.view_change_history (отдельная группа History Viewers).
    """
    monthly_report = get_object_or_404(MonthlyReport, pk=pk)

    # Получаем историю изменений (через ваш AuditService)
    history = AuditService.get_change_history(monthly_report, limit=100)

    context = {
        'monthly_report': monthly_report,
        'history': history,
    }
    return render(request, 'monthly_report/change_history.html', context)


@login_required
@require_POST
def revert_change(request, change_id: int):
    """
    Откат изменения
    """
    change_log = get_object_or_404(CounterChangeLog, pk=change_id)

    # Проверяем права (оставляем как было — право на завершение периода/конец)
    if not request.user.has_perm('monthly_report.edit_counters_end'):
        return JsonResponse({"ok": False, "error": "Нет прав на откат изменений"}, status=403)

    # Проверяем что месяц открыт для редактирования
    mc = MonthControl.objects.filter(month=change_log.monthly_report.month).first()
    if not (mc and mc.is_editable):
        return JsonResponse({"ok": False, "error": "Месяц закрыт для редактирования"}, status=403)

    try:
        AuditService.revert_change(change_log, request.user, request)
        return JsonResponse({
            'ok': True,
            'message': 'Изменение успешно отменено'
        })
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=400)
