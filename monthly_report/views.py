from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q
from datetime import date
from django.utils import timezone
from .forms import ExcelUploadForm
from django.contrib.auth.decorators import login_required, permission_required
from .models import MonthlyReport, MonthControl
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
import json


class MonthListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'monthly_report/month_list.html'
    context_object_name = 'months'
    permission_required = 'monthly_report.access_monthly_report'
    raise_exception = True

    def get_queryset(self):
        from django.db.models.functions import TruncMonth
        from django.db.models import Count
        return (
            MonthlyReport.objects
            .annotate(month_trunc=TruncMonth('month'))
            .values('month_trunc')
            .annotate(count=Count('id'))
            .order_by('-month_trunc')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        months = list(ctx['months'])  # это список dict из values()

        # ключ месяца = date(YYYY,MM,1)
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
    paginate_by = 100  # fallback

    # варианты "на странице"
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
        'num':    None,  # обрабатываем отдельно
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
            return None  # показать все
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
        from django.db.models import Q
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
                if a > b: a, b = b, a
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

        # варианты для подсказок (distinct по месяцу)
        base_qs = MonthlyReport.objects.filter(month__year=y, month__month=m)

        def opts(field):
            return (base_qs
                    .exclude(**{f"{field}__isnull": True})
                    .exclude(**{field: ''})
                    .values_list(field, flat=True)
                    .distinct()
                    .order_by(field))

        ctx['choices'] = {
            'num': [str(n) for n in base_qs.exclude(order_number__isnull=True)
            .values_list('order_number', flat=True)
            .distinct().order_by('order_number')],
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

        # ---- подсветка дублей и расчет ui_total по "верх/низ" ----
        full_qs = self.get_queryset().values('id', 'serial_number', 'inventory_number')
        groups = defaultdict(list)
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

        # --- флаги редактирования месяца и права пользователя ---
        mc = MonthControl.objects.filter(month=month_dt).first()

        # если у модели есть @property is_editable — можешь использовать его:
        # now_open = bool(mc and mc.is_editable)
        # а универсально — так:
        now_open = bool(mc and mc.edit_until and timezone.now() < mc.edit_until)

        ctx['report_is_editable'] = now_open
        ctx['report_edit_until'] = mc.edit_until if mc else None

        u = self.request.user
        ctx['can_edit_end'] = u.has_perm('monthly_report.edit_counters_end')
        ctx['can_edit_start'] = u.has_perm('monthly_report.edit_counters_start')

        return ctx


@login_required
@permission_required('monthly_report.upload_monthly_report', raise_exception=True)
def upload_excel(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            count = form.process_data()
            return render(request, 'monthly_report/upload_success.html', {'count': count})
    else:
        form = ExcelUploadForm()
    return render(request, 'monthly_report/upload.html', {'form': form})

@login_required
@require_POST
def api_update_counters(request, pk: int):
    """
    Обновляет набор счётчиков у одной записи. Разрешает:
      - *_end поля, если у пользователя есть право edit_counters_end
      - *_start поля, если есть право edit_counters_start
    Дополнительно блокирует всё, если месяц закрыт (MonthControl.is_editable == False).
    После сохранения переcчитывает total_prints по «особой» логике через recompute_month.
    """
    from .models import MonthlyReport, MonthControl
    from .services import recompute_month

    try:
        obj = MonthlyReport.objects.get(pk=pk)
    except MonthlyReport.DoesNotExist:
        return HttpResponseBadRequest("not found")

    # проверка окна редактирования
    mc = MonthControl.objects.filter(month=obj.month).first()
    now_open = bool(mc and mc.edit_until and timezone.now() < mc.edit_until)
    if not now_open:
        return HttpResponseForbidden(_("Отчёт закрыт для редактирования"))

    # права по полям
    user = request.user
    can_start = user.has_perm('monthly_report.edit_counters_start')
    can_end   = user.has_perm('monthly_report.edit_counters_end')

    allowed_fields = set()
    if can_start:
        allowed_fields |= {
            'a4_bw_start','a4_color_start','a3_bw_start','a3_color_start'
        }
    if can_end:
        allowed_fields |= {
            'a4_bw_end','a4_color_end','a3_bw_end','a3_color_end'
        }
    if not allowed_fields:
        return HttpResponseForbidden(_("Нет прав для изменения счётчиков"))

    # данные
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        fields = payload.get('fields', {})
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid json")

    def to_int(x):
        try:
            if x in [None, ""]: return 0
            return int(float(str(x).replace(",", ".")))
        except Exception:
            return 0

    changed = {}
    for name, val in fields.items():
        if name in allowed_fields:
            setattr(obj, name, to_int(val))
            changed[name] = to_int(val)

    if not changed:
        return JsonResponse({"ok": False, "error": _("Нет разрешённых к изменению полей")}, status=400)

    # сохраняем запись
    obj.save()

    # пересчёт «итого» по всему месяцу (A4 у первой дублирующейся, A3 у нижних)
    recompute_month(obj.month)

    # перечитаем свежие данные
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
        }
    })