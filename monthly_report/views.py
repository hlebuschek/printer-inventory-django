# monthly_report/views.py
from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q
from datetime import date

from .models import MonthlyReport
from .forms import ExcelUploadForm
from django.contrib.auth.decorators import login_required, permission_required


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
        from datetime import date
        from collections import defaultdict

        ctx = super().get_context_data(**kwargs)
        y, m = self._month_tuple()
        ctx['month_str'] = f"{y:04d}-{m:02d}"
        ctx['month_date'] = date(y, m, 1)

        ctx['filters'] = {
            'num': self.request.GET.get('num', ''), 'org': self.request.GET.get('org', ''),
            'branch': self.request.GET.get('branch', ''), 'city': self.request.GET.get('city', ''),
            'address': self.request.GET.get('address', ''), 'model': self.request.GET.get('model', ''),
            'serial': self.request.GET.get('serial', ''), 'inv': self.request.GET.get('inv', ''),
            'q': self.request.GET.get('q', ''),
        }

        base_qs = MonthlyReport.objects.filter(month__year=y, month__month=m)
        def opts(field):
            return (base_qs.exclude(**{f"{field}__isnull": True})
                           .exclude(**{field: ''})
                           .values_list(field, flat=True)
                           .distinct().order_by(field))

        ctx['choices'] = {
            'num': [str(n) for n in base_qs.exclude(order_number__isnull=True)
                                           .values_list('order_number', flat=True)
                                           .distinct().order_by('order_number')],
            'org': list(opts('organization')), 'branch': list(opts('branch')),
            'city': list(opts('city')), 'address': list(opts('address')),
            'model': list(opts('equipment_model')), 'serial': list(opts('serial_number')),
            'inv': list(opts('inventory_number')),
        }

        # base_qs для ссылок (сохраняем per, убираем page)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['base_qs'] = params.urlencode()

        # qs без per — для пунктов меню "на странице"
        params2 = self.request.GET.copy()
        params2.pop('page', None)
        params2.pop('per', None)
        ctx['qs_no_per'] = params2.urlencode()

        # текущее значение per
        per = self.request.GET.get('per', '').strip()
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

        # ---- подсветка дублей + ui_total (как раньше) ----
        full = self.object_list.values('id', 'serial_number', 'inventory_number')
        groups = defaultdict(list)
        for r in full:
            sn = (r['serial_number'] or '').strip()
            inv = (r['inventory_number'] or '').strip()
            if not sn and not inv:
                continue
            groups[(sn, inv)].append(r['id'])

        id_to_pos, dup_ids = {}, set()
        for ids in groups.values():
            if len(ids) >= 2:
                ids.sort()
                dup_ids.update(ids)
                for pos, rid in enumerate(ids):
                    id_to_pos[rid] = pos

        def nz(x): return int(x or 0)

        for obj in ctx['object_list']:
            obj.ui_is_dup = obj.id in dup_ids
            pos = id_to_pos.get(obj.id, None)
            a4 = max(0, nz(obj.a4_bw_end) - nz(obj.a4_bw_start)) + max(0, nz(obj.a4_color_end) - nz(obj.a4_color_start))
            a3 = max(0, nz(obj.a3_bw_end) - nz(obj.a3_bw_start)) + max(0, nz(obj.a3_color_end) - nz(obj.a3_color_start))
            obj.ui_total = a4 + a3 if pos is None else (a4 if pos == 0 else a3)

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
