from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.db.models import Count, Q, OuterRef, Subquery
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_http_methods
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
    """Безопасное преобразование в int с валидацией"""
    try:
        if x in (None, ""):
            return 0
        # Удаляем пробелы и проверяем на валидность
        s = str(x).strip().replace(" ", "")

        # Проверяем что строка содержит только цифры
        if not s.isdigit():
            raise ValueError(f"Недопустимые символы в значении: {x}")

        num = int(s)

        # Ограничиваем максимальное значение (100 миллионов)
        MAX_VALUE = 100_000_000
        if num > MAX_VALUE:
            raise ValueError(f"Слишком большое значение: {num} (максимум {MAX_VALUE})")

        return num
    except ValueError as e:
        # Пробрасываем ошибку валидации выше
        raise
    except Exception:
        return 0


def _get_duplicate_groups(month_dt):
    """
    Возвращает группы дублирующихся серийников с позициями строк.
    Результат: {(serial, inventory): [(report_id, position), ...]}
    """
    from collections import defaultdict

    reports = MonthlyReport.objects.filter(month=month_dt).values(
        'id', 'serial_number', 'inventory_number', 'order_number'
    ).order_by('order_number', 'id')

    groups = defaultdict(list)
    for r in reports:
        sn = (r['serial_number'] or '').strip()
        inv = (r['inventory_number'] or '').strip()
        if not sn and not inv:
            continue
        groups[(sn, inv)].append(r)

    # Оставляем только группы с дублями и определяем позиции
    result = {}
    for key, reports_list in groups.items():
        if len(reports_list) >= 2:
            # Сортируем по order_number и id для стабильного порядка
            sorted_reports = sorted(reports_list, key=lambda x: (x['order_number'], x['id']))
            result[key] = [(r['id'], pos) for pos, r in enumerate(sorted_reports)]

    return result


class MonthListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Список месяцев с отчетами (Vue.js компонент).
    Данные загружаются через API endpoint api_months_list.
    """
    template_name = 'monthly_report/month_list_vue.html'
    context_object_name = 'months'
    permission_required = 'monthly_report.access_monthly_report'
    raise_exception = True

    def get_queryset(self):
        # Возвращаем пустой queryset, так как данные загружаются через API
        return MonthlyReport.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Vue компонент загружает данные самостоятельно через API
        return ctx


class MonthDetailView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Детальная страница месяца с отчетами (Vue.js компонент).
    Данные загружаются через API endpoint api_month_detail.
    """
    template_name = 'monthly_report/month_detail_vue.html'
    context_object_name = 'reports'
    permission_required = 'monthly_report.access_monthly_report'
    raise_exception = True
    paginate_by = 100

    PER_CHOICES = [100, 200, 500, 1000, 2000, 5000]
    DEFAULT_PER = 100

    def dispatch(self, request, *args, **kwargs):
        """Проверяем, опубликован ли месяц для обычных пользователей"""
        from datetime import date
        from django.http import HttpResponseForbidden

        # Получаем дату месяца
        y, m = self._month_tuple()
        month_date = date(y, m, 1)

        # Проверяем права на управление видимостью месяцев
        can_manage_months = request.user.has_perm('monthly_report.can_manage_month_visibility')

        # Если нет прав на управление видимостью, проверяем публикацию
        if not can_manage_months:
            month_control = MonthControl.objects.filter(month=month_date).first()
            is_published = month_control.is_published if month_control else False

            if not is_published:
                return HttpResponseForbidden(
                    "Этот месяц еще не опубликован. Обратитесь к администратору."
                )

        return super().dispatch(request, *args, **kwargs)

    FILTER_MAP = {
        'org': 'organization__icontains',
        'branch': 'branch__icontains',
        'city': 'city__icontains',
        'address': 'address__icontains',
        'model': 'equipment_model__icontains',
        'serial': 'serial_number__icontains',
        'inv': 'inventory_number__icontains',
        'num': None,
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
        # Поддержка как нового формата (year, month отдельно), так и старого (month='2025-11')
        if 'year' in self.kwargs and 'month' in self.kwargs:
            return int(self.kwargs['year']), int(self.kwargs['month'])
        else:
            # Старый формат для совместимости
            y, m = self.kwargs['month'].split('-')
            return int(y), int(m)

    def get_queryset(self):
        # Возвращаем пустой queryset, так как данные загружаются через API
        return MonthlyReport.objects.none()

    def get_context_data(self, **kwargs):
        # НЕ вызываем super() чтобы избежать проблем с пустым queryset
        y, m = self._month_tuple()

        context = {
            'year': y,
            'month': m,
            'month_str': f"{y:04d}-{m:02d}",
        }

        return context

    # Сохраняем старую реализацию для совместимости (если понадобится)
    def get_queryset_old(self):
        import re
        y, m = self._month_tuple()
        qs = MonthlyReport.objects.filter(month__year=y, month__month=m)

        # Общий поиск
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(organization__icontains=q) | Q(branch__icontains=q) | Q(city__icontains=q) |
                Q(address__icontains=q) | Q(equipment_model__icontains=q) |
                Q(serial_number__icontains=q) | Q(inventory_number__icontains=q)
            )

        # Фильтры по полям с поддержкой множественного выбора
        filter_fields = {
            'org': 'organization',
            'branch': 'branch',
            'city': 'city',
            'address': 'address',
            'model': 'equipment_model',
            'serial': 'serial_number',
            'inv': 'inventory_number',
        }

        for param_key, field_name in filter_fields.items():
            multi_value = self.request.GET.get(f'{param_key}__in', '').strip()
            single_value = self.request.GET.get(param_key, '').strip()

            if multi_value:
                # Используем || как разделитель для множественного выбора
                values = [v.strip() for v in multi_value.split('||') if v.strip()]

                if values:
                    q_objects = []
                    for value in values:
                        # Нормализуем пробелы
                        normalized = ' '.join(value.split())
                        q_objects.append(Q(**{f'{field_name}__iexact': normalized}))

                    if q_objects:
                        combined_q = q_objects[0]
                        for q_obj in q_objects[1:]:
                            combined_q |= q_obj
                        qs = qs.filter(combined_q)
            elif single_value:
                # Одиночное значение - частичное совпадение
                qs = qs.filter(**{f'{field_name}__icontains': single_value})

        # Специальная обработка для поля "num" (номер по порядку)
        num_value = self.request.GET.get('num__in') or self.request.GET.get('num', '')
        num_value = num_value.strip()

        if num_value:
            if ',' in num_value:
                # Множественный выбор номеров
                try:
                    nums = [int(v.strip()) for v in num_value.split(',') if v.strip().isdigit()]
                    if nums:
                        qs = qs.filter(order_number__in=nums)
                except (ValueError, TypeError):
                    pass
            else:
                # Одиночное значение или диапазон
                if re.fullmatch(r'\d+', num_value):
                    qs = qs.filter(order_number=int(num_value))
                elif re.fullmatch(r'\d+\s*-\s*\d+', num_value):
                    a, b = [int(x) for x in re.split(r'\s*-\s*', num_value)]
                    if a > b:
                        a, b = b, a
                    qs = qs.filter(order_number__gte=a, order_number__lte=b)
                else:
                    nums = [int(n) for n in re.findall(r'\d+', num_value)]
                    if nums:
                        qs = qs.filter(order_number__in=nums)

        # Сортировка
        sort = self.request.GET.get('sort', '').strip()
        if sort:
            desc = sort.startswith('-')
            key = sort[1:] if desc else sort
            field = self.SORT_MAP.get(key)
            if field:
                qs = qs.order_by(('-' if desc else '') + field)
        else:
            qs = qs.order_by('order_number', 'organization', 'city', 'equipment_model', 'serial_number')

        if self.request.GET.get('anomalies') == '1':
            # Получаем текущий месяц для расчета аномалий
            from datetime import date
            month_dt = date(y, m, 1)

            # Аннотируем средними значениями за предыдущие месяцы
            from django.db.models import Avg, Count, F, Case, When, FloatField

            # Подзапрос для получения среднего количества отпечатков
            avg_subquery = MonthlyReport.objects.filter(
                serial_number=OuterRef('serial_number'),
                month__lt=month_dt
            ).values('serial_number').annotate(
                avg=Avg('total_prints')
            ).values('avg')

            # Аннотируем queryset средними значениями
            qs = qs.annotate(
                historical_avg=Subquery(avg_subquery)
            )

            # Фильтруем только аномалии (превышение > 2000)
            THRESHOLD = 2000
            qs = qs.filter(
                historical_avg__isnull=False,
                total_prints__gt=F('historical_avg') + THRESHOLD
            )

        return qs


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

                # Получаем месяц для формирования URL
                month_str = form.cleaned_data['month'].strftime('%Y-%m')
                month_url = f'/monthly-report/{month_str}/'

                # Возвращаем JSON для Vue.js компонента
                return JsonResponse({
                    'success': True,
                    'count': count,
                    'bulk_log_id': bulk_log.id,
                    'month_url': month_url,
                    'message': f'Успешно загружено {count} записей'
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
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)
        else:
            # Форма невалидна
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    errors.append(f'{field}: {error}')
            return JsonResponse({
                'success': False,
                'error': ', '.join(errors)
            }, status=400)
    else:
        form = ExcelUploadForm()
    # Используем Vue.js шаблон
    return render(request, 'monthly_report/upload_vue.html', {'form': form})


@login_required
@require_POST
def api_update_counters(request, pk: int):
    """
    Обновляет счётчики одной записи при открытом месяце + записывает аудит
    + помечает отредактированные *_end поля как ручные (отключает автосинхронизацию)
    + НОВАЯ ЛОГИКА: проверка ограничений для дублирующихся серийников
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

    # НОВАЯ ЛОГИКА: ограничения по дублям
    duplicate_groups = _get_duplicate_groups(obj.month)

    # Находим информацию о дубле для данной записи
    dup_info = None
    for (sn, inv), report_positions in duplicate_groups.items():
        for report_id, position in report_positions:
            if report_id == obj.id:
                dup_info = {'position': position, 'group_size': len(report_positions)}
                break
        if dup_info:
            break

    # Определяем ограничения по дублям
    if dup_info:
        if dup_info['position'] == 0:
            # Первая строка в группе дублей - только A4
            allowed_by_dup = {"a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end"}
        else:
            # Остальные строки в группе дублей - только A3
            allowed_by_dup = {"a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end"}
    else:
        # Обычная строка - без ограничений по дублям
        allowed_by_dup = COUNTER_FIELDS

    # ограничения по справочнику модели
    spec = get_spec_for_model_name(obj.equipment_model)
    allowed_by_spec = allowed_counter_fields(spec)

    # итоговый whitelist
    allowed_fields = allowed_by_perm & allowed_by_dup
    if allowed_by_spec:
        allowed_fields &= allowed_by_spec

    if not allowed_fields:
        error_msg = _("Для этой записи редактирование счётчиков запрещено правилами.")
        if dup_info:
            if dup_info['position'] == 0:
                error_msg = _("Первая строка группы дублей — редактирование только полей A4.")
            else:
                error_msg = _(f"Строка #{dup_info['position'] + 1} группы дублей — редактирование только полей A3.")
        return HttpResponseForbidden(error_msg)

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
    manually_edited_fields = []
    manual_flag_fields = []
    validation_errors = []  # НОВОЕ

    for name, val in fields.items():
        if name not in COUNTER_FIELDS:
            continue
        if name not in allowed_fields:
            ignored.append(name)
            continue

        old_value = getattr(obj, name)

        # НОВОЕ: валидация с обработкой ошибок
        try:
            new_value = _to_int(val)
        except ValueError as e:
            validation_errors.append(f"{name}: {str(e)}")
            continue  # Пропускаем это поле и идем дальше

        # Записываем изменение
        setattr(obj, name, new_value)
        updated.append(name)

        # Сохраняем для аудита только если значение изменилось
        if old_value != new_value:
            changes_for_audit[name] = (old_value, new_value)

        # НОВАЯ ЛОГИКА: помечаем *_end поля как отредактированные вручную
        if name.endswith('_end') and old_value != new_value:
            obj.mark_field_as_manually_edited(name)
            manually_edited_fields.append(name)

            manual_flag_field = f"{name}_manual"
            if hasattr(obj, manual_flag_field):
                manual_flag_fields.append(manual_flag_field)

    # НОВОЕ: проверяем ошибки валидации ПОСЛЕ цикла
    if validation_errors:
        return JsonResponse({
            "ok": False,
            "error": "Ошибка валидации данных",
            "validation_errors": validation_errors
        }, status=400)

    if not updated:
        return JsonResponse(
            {"ok": False, "error": _("Нет разрешённых к изменению полей"), "ignored_fields": ignored},
            status=400
        )

    # ИСПРАВЛЕНИЕ: сохраняем объект включая флаги ручного редактирования
    all_fields_to_update = updated + manual_flag_fields
    obj.save(update_fields=all_fields_to_update)

    # АУДИТ: Записываем историю изменений
    if changes_for_audit:
        try:
            AuditService.log_multiple_changes(
                monthly_report=obj,
                user=user,
                changes=changes_for_audit,
                request=request,
                change_source='manual',
                comment='Ручное редактирование через веб-интерфейс'
            )
        except Exception as e:
            # Не прерываем выполнение если аудит не сработал
            logger.error(f"Ошибка записи аудита: {e}")

    # пересчитываем только свою группу
    recompute_group(obj.month, obj.serial_number, obj.inventory_number)

    # GRANULAR UPDATE: Получаем все записи группы для отправки обновлений total_prints
    # Формируем запрос для группы (аналогично recompute_group)
    sn = (obj.serial_number or "").strip()
    inv = (obj.inventory_number or "").strip()

    group_reports = []
    if sn or inv:
        qs = MonthlyReport.objects.filter(month=obj.month)
        if sn:
            qs = qs.filter(serial_number__iexact=sn)
        else:
            qs = qs.filter(inventory_number__iexact=inv)
        group_reports = list(qs.values('id', 'total_prints'))

    obj.refresh_from_db()

    # Вычисляем информацию об аномалии для обновлённого объекта
    anomaly_data = _annotate_anomalies_api([obj], obj.month, threshold=2000)
    anomaly_info = anomaly_data.get(obj.id, {'is_anomaly': False, 'has_history': False})

    # REAL-TIME UPDATE: Отправляем WebSocket уведомление об изменениях другим пользователям
    if changes_for_audit:
        try:
            channel_layer = get_channel_layer()
            # Формируем имя группы по году-месяцу
            year = obj.month.year
            month = obj.month.month
            room_group_name = f'monthly_report_{year}_{month:02d}'

            # Отправляем уведомление для каждого измененного поля
            for field_name, (old_val, new_val) in changes_for_audit.items():
                # Определяем, является ли это поле ручным редактированием
                manual_field_name = None
                is_manual = False
                if field_name.endswith('_end'):
                    # Для end полей проверяем соответствующий флаг manual
                    manual_field_name = f"{field_name}_manual"
                    is_manual = getattr(obj, manual_field_name, False)

                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'counter_update',
                        'report_id': obj.id,
                        'field': field_name,
                        'old_value': old_val,
                        'new_value': new_val,
                        'is_manual': is_manual,
                        'manual_field': manual_field_name,
                        'user_username': user.username,
                        'user_full_name': user.get_full_name() or user.username,
                        'timestamp': timezone.now().isoformat(),
                    }
                )
            logger.info(f"WebSocket broadcast sent for {len(changes_for_audit)} field changes in report {obj.id}")

            # GRANULAR UPDATE: Если были изменены end поля, отправляем обновления total_prints для всей группы
            # Это позволяет избежать полной перезагрузки таблицы на фронте
            end_fields_changed = any(field.endswith('_end') for field in changes_for_audit.keys())
            if end_fields_changed and group_reports:
                logger.info(f"Sending total_prints updates for {len(group_reports)} records in group")

                # Оптимизация: получаем все объекты группы за один запрос
                group_ids = [r['id'] for r in group_reports]
                group_objects = list(MonthlyReport.objects.filter(id__in=group_ids))

                # Вычисляем аномалии для всех записей группы за один раз
                group_anomaly_data = _annotate_anomalies_api(group_objects, obj.month, threshold=2000)

                # Отправляем обновления
                for report_data in group_reports:
                    report_anomaly_info = group_anomaly_data.get(
                        report_data['id'],
                        {'is_anomaly': False, 'has_history': False}
                    )

                    async_to_sync(channel_layer.group_send)(
                        room_group_name,
                        {
                            'type': 'total_prints_update',
                            'report_id': report_data['id'],
                            'total_prints': report_data['total_prints'],
                            'is_anomaly': report_anomaly_info.get('is_anomaly', False),
                            'anomaly_info': report_anomaly_info,
                        }
                    )

        except Exception as e:
            # Не прерываем выполнение если WebSocket не сработал
            logger.error(f"Ошибка отправки WebSocket уведомления: {e}")

    # НОВОЕ: добавляем информацию об ограничениях в ответ
    response_data = {
        "ok": True,
        "report": {
            "id": obj.id,
            "a4_bw_start": obj.a4_bw_start, "a4_bw_end": obj.a4_bw_end,
            "a4_color_start": obj.a4_color_start, "a4_color_end": obj.a4_color_end,
            "a3_bw_start": obj.a3_bw_start, "a3_bw_end": obj.a3_bw_end,
            "a3_color_start": obj.a3_color_start, "a3_color_end": obj.a3_color_end,
            "total_prints": obj.total_prints,
            "is_anomaly": anomaly_info.get('is_anomaly', False),
            "anomaly_info": anomaly_info,
        },
        "updated_fields": updated,
        "ignored_fields": ignored,
        "changes_logged": len(changes_for_audit),
        "manually_edited_fields": manually_edited_fields,  # НОВОЕ: информируем фронтенд
        "message": f"Поля {', '.join(manually_edited_fields)} помечены как отредактированные вручную и больше не будут обновляться автоматически" if manually_edited_fields else None
    }

    # Добавляем информацию об ограничениях для UI
    if dup_info:
        response_data["duplicate_info"] = {
            "is_duplicate": True,
            "position": dup_info['position'],
            "group_size": dup_info['group_size'],
            "restriction": "Только A4" if dup_info['position'] == 0 else "Только A3"
        }

    return JsonResponse(response_data)


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


# Добавьте в views.py.back:

@login_required
@require_POST
def revert_change(request, change_id: int):
    """
    Откат конкретного изменения счетчика
    """
    if not request.user.has_perm('monthly_report.edit_counters_end') and \
            not request.user.has_perm('monthly_report.edit_counters_start'):
        return HttpResponseForbidden(_("Нет прав для отката изменений"))

    try:
        change_log = get_object_or_404(CounterChangeLog, id=change_id)
        monthly_report = change_log.monthly_report

        # Проверяем, что месяц открыт для редактирования
        mc = MonthControl.objects.filter(month=monthly_report.month).first()
        if not (mc and mc.edit_until and timezone.now() < mc.edit_until):
            return JsonResponse({"ok": False, "error": "Месяц закрыт для редактирования"})

        # Откатываем значение
        old_value = getattr(monthly_report, change_log.field_name)
        setattr(monthly_report, change_log.field_name, change_log.old_value)
        monthly_report.save(update_fields=[change_log.field_name])

        # Логируем откат
        AuditService.log_single_change(
            monthly_report=monthly_report,
            user=request.user,
            field_name=change_log.field_name,
            old_value=old_value,
            new_value=change_log.old_value,
            request=request,
            change_source='revert',
            comment=f'Откат изменения #{change_id}'
        )

        # Пересчитываем группу
        recompute_group(monthly_report.month, monthly_report.serial_number, monthly_report.inventory_number)

        return JsonResponse({
            "ok": True,
            "message": f"Изменение отменено: {change_log.field_name} = {change_log.old_value}"
        })

    except Exception as e:
        logger.error(f"Ошибка отката изменения {change_id}: {e}")
        return JsonResponse({"ok": False, "error": str(e)})


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
        'permissions': json.dumps({
            'can_reset_auto_polling': request.user.has_perm('monthly_report.can_reset_auto_polling'),
        })
    }
    # Используем Vue.js шаблон
    return render(request, 'monthly_report/change_history_vue.html', context)


@login_required
def api_change_history(request, pk: int):
    """
    API endpoint для получения истории изменений в JSON формате
    """
    monthly_report = get_object_or_404(MonthlyReport, pk=pk)

    # Получаем историю изменений
    history_qs = AuditService.get_change_history(monthly_report, limit=100)

    # Сериализуем историю
    history_data = []
    for change in history_qs:
        history_data.append({
            'id': change.id,
            'timestamp': change.timestamp.isoformat(),
            'user_username': change.user.username if change.user else '',
            'user_full_name': change.user.get_full_name() if change.user else '',
            'field': change.field_name,  # Исправлено: field_name вместо field
            'field_display': change.get_field_display_name(),
            'old_value': change.old_value,
            'new_value': change.new_value,
            'change_delta': change.change_delta,
            'change_source': change.change_source,
            'ip_address': change.ip_address or '',
            'comment': change.comment or '',
        })

    # Сериализуем monthly_report
    report_data = {
        'id': monthly_report.id,
        'month': monthly_report.month.isoformat(),
        'organization': monthly_report.organization or '',
        'branch': monthly_report.branch or '',
        'city': monthly_report.city or '',
        'address': monthly_report.address or '',
        'equipment_model': monthly_report.equipment_model or '',
        'serial_number': monthly_report.serial_number or '',
        'inventory_number': monthly_report.inventory_number or '',
        'a4_bw_start': monthly_report.a4_bw_start,
        'a4_bw_end': monthly_report.a4_bw_end,
        'a4_bw_end_auto': monthly_report.a4_bw_end_auto,
        'a4_bw_end_manual': monthly_report.a4_bw_end_manual,
        'a4_color_start': monthly_report.a4_color_start,
        'a4_color_end': monthly_report.a4_color_end,
        'a4_color_end_auto': monthly_report.a4_color_end_auto,
        'a4_color_end_manual': monthly_report.a4_color_end_manual,
        'a3_bw_start': monthly_report.a3_bw_start,
        'a3_bw_end': monthly_report.a3_bw_end,
        'a3_bw_end_auto': monthly_report.a3_bw_end_auto,
        'a3_bw_end_manual': monthly_report.a3_bw_end_manual,
        'a3_color_start': monthly_report.a3_color_start,
        'a3_color_end': monthly_report.a3_color_end,
        'a3_color_end_auto': monthly_report.a3_color_end_auto,
        'a3_color_end_manual': monthly_report.a3_color_end_manual,
        'total_prints': monthly_report.total_prints or 0,
    }

    return JsonResponse({
        'ok': True,
        'report': report_data,
        'history': history_data
    })


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


@login_required
@permission_required('monthly_report.can_reset_auto_polling', raise_exception=True)
@require_POST
def api_reset_manual_flag(request, pk: int):
    """
    Сброс флага ручного редактирования - поле вернется к автосинхронизации
    Требуется право can_reset_auto_polling
    """
    obj = get_object_or_404(MonthlyReport, pk=pk)

    # Проверки прав и окна редактирования...

    try:
        payload = json.loads(request.body.decode("utf-8"))
        field_name = payload.get("field")

        if field_name and field_name.endswith('_end'):
            # Сбрасываем флаг ручного редактирования
            setattr(obj, f"{field_name}_manual", False)

            # Синхронизируем с auto значением
            auto_field = f"{field_name}_auto"
            auto_value = getattr(obj, auto_field, 0)
            setattr(obj, field_name, auto_value)

            obj.save(update_fields=[field_name, f"{field_name}_manual"])

            return JsonResponse({
                "ok": True,
                "message": f"Поле {field_name} возвращено к автоматическому режиму",
                "new_value": auto_value
            })

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


@login_required
@permission_required('monthly_report.access_monthly_report', raise_exception=True)
def export_month_excel(request, year: int, month: int):
    """
    Экспорт месяца в Excel
    """
    from datetime import date
    from .services.excel_export import export_month_to_excel

    month_date = date(int(year), int(month), 1)

    try:
        return export_month_to_excel(month_date)
    except Exception as e:
        logger.exception(f"Ошибка экспорта Excel: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def _calculate_month_metrics(month_dt, allowed_by_perm):
    """
    Вычисляет метрики месяца (процент заполненности и количество пользователей).
    Результат кэшируется в Redis.

    Args:
        month_dt: Дата месяца (date object)
        allowed_by_perm: Set разрешенных полей по правам пользователя

    Returns:
        dict: {
            'completion_percentage': float,  # Процент заполненных полей
            'unique_users_count': int,       # Количество пользователей редактировавших отчет
            'auto_fill_potential_percentage': float,  # Процент записей которые могут быть заполнены автоматически
            'auto_fill_actual_percentage': float,     # Процент записей которые были заполнены автоматически и не изменены
        }
    """
    # Генерируем уникальный ключ кэша на основе месяца и прав пользователя
    # Права нужны потому что процент заполненности зависит от того какие поля может редактировать пользователь
    perm_key = '_'.join(sorted(allowed_by_perm))
    cache_key = f'month_metrics:{month_dt.year}-{month_dt.month:02d}:{perm_key}'

    # Пытаемся получить из кэша
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT for month metrics: {month_dt}")
        return cached

    logger.debug(f"Cache MISS for month metrics: {month_dt}, calculating...")

    # Расчет процента заполненности
    completion_percentage = None
    auto_fill_potential_percentage = None
    auto_fill_actual_percentage = None

    month_reports = MonthlyReport.objects.filter(month=month_dt)
    records_count = month_reports.count()

    if records_count > 0:
        duplicate_groups = _get_duplicate_groups(month_dt)

        total_records = 0
        filled_records = 0

        # Метрики автозаполнения
        records_with_ip = 0  # Записи у которых есть device_ip (могут быть заполнены автоматически)
        records_auto_filled = 0  # Записи которые были заполнены автоматически и не изменены вручную

        for report in month_reports:
            # Определяем позицию в группе дублей
            is_dup = False
            dup_position = 0
            for (serial, inv), positions in duplicate_groups.items():
                for report_id, position in positions:
                    if report_id == report.id:
                        is_dup = True
                        dup_position = position
                        break
                if is_dup:
                    break

            # Вычисляем разрешенные поля для этого отчета
            # 1. Ограничения по дублям
            if is_dup:
                if dup_position == 0:
                    allowed_by_dup = {"a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end"}
                else:
                    allowed_by_dup = {"a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end"}
            else:
                allowed_by_dup = COUNTER_FIELDS

            # 2. Ограничения по модели устройства
            spec = get_spec_for_model_name(report.equipment_model)
            allowed_by_spec = allowed_counter_fields(spec)

            # 3. Итоговые разрешения = пересечение всех ограничений
            allowed_final = allowed_by_perm & allowed_by_dup & allowed_by_spec

            # Получаем разрешенные end поля
            allowed_end_fields = {f for f in allowed_final if f.endswith('_end')}

            # Проверяем есть ли незаполненные среди разрешенных
            has_unfilled = False
            for field in allowed_end_fields:
                if getattr(report, field, 0) == 0:
                    has_unfilled = True
                    break

            total_records += 1
            if not has_unfilled:
                filled_records += 1

            # Метрики автозаполнения
            # 1. Потенциальное автозаполнение - есть ли device_ip
            has_device_ip = bool(report.device_ip)
            if has_device_ip:
                records_with_ip += 1

            # 2. Фактическое автозаполнение - заполнено автоматически и не изменено вручную
            # ВАЖНО: проверяем только среди записей с device_ip (потенциал)
            if has_device_ip and allowed_end_fields:
                all_auto = True
                for field in allowed_end_fields:
                    manual_field = f"{field}_manual"
                    if getattr(report, manual_field, False):
                        all_auto = False
                        break

                # Также проверяем что поля заполнены (не нулевые)
                if all_auto:
                    has_values = False
                    for field in allowed_end_fields:
                        if getattr(report, field, 0) > 0:
                            has_values = True
                            break

                    if has_values:
                        records_auto_filled += 1

        # Рассчитываем процент заполненности
        if total_records > 0:
            completion_percentage = round((filled_records / total_records) * 100, 1)
            auto_fill_potential_percentage = round((records_with_ip / total_records) * 100, 1)
            auto_fill_actual_percentage = round((records_auto_filled / total_records) * 100, 1)

    # Расчет количества уникальных пользователей
    unique_users_count = CounterChangeLog.objects.filter(
        monthly_report__month=month_dt
    ).values('user').distinct().count()

    result = {
        'completion_percentage': completion_percentage,
        'unique_users_count': unique_users_count,
        'auto_fill_potential_percentage': auto_fill_potential_percentage,
        'auto_fill_actual_percentage': auto_fill_actual_percentage,
    }

    # Кэшируем результат на 1 час (3600 секунд)
    cache.set(cache_key, result, 3600)

    return result


def invalidate_month_metrics_cache(month_dt):
    """
    Инвалидирует кэш метрик для указанного месяца.
    Вызывается при изменении данных MonthlyReport.

    Args:
        month_dt: Дата месяца (date object)
    """
    # Очищаем кэш для всех возможных комбинаций прав
    # Так как мы не знаем какие комбинации прав были закэшированы, удаляем по паттерну
    pattern = f'month_metrics:{month_dt.year}-{month_dt.month:02d}:*'

    # Redis не поддерживает удаление по паттерну напрямую через django cache
    # Но мы можем использовать version для инвалидации
    # Для простоты просто установим короткий TTL=1 для ключей которые мы знаем

    # Возможные комбинации прав (самые распространенные)
    common_perms = [
        set(),  # Нет прав
        {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"},  # Только start
        {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"},  # Только end
        {"a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end", "a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end"},  # Все права
    ]

    for perms in common_perms:
        perm_key = '_'.join(sorted(perms))
        cache_key = f'month_metrics:{month_dt.year}-{month_dt.month:02d}:{perm_key}'
        cache.delete(cache_key)

    logger.debug(f"Invalidated month metrics cache for {month_dt}")


@login_required
@permission_required('monthly_report.access_monthly_report', raise_exception=True)
def api_months_list(request):
    """
    API endpoint для получения списка месяцев (для Vue.js компонента)
    """
    import calendar
    from django.utils.formats import date_format

    months_data = (
        MonthlyReport.objects
        .annotate(month_trunc=TruncMonth('month'))
        .values('month_trunc')
        .annotate(count=Count('id'))
        .order_by('-month_trunc')
    )

    def month_key(dt):
        return dt.date() if hasattr(dt, 'date') else dt

    keys = [month_key(rec['month_trunc']) for rec in months_data]
    controls = {mc.month: mc for mc in MonthControl.objects.filter(month__in=keys)}
    now = timezone.now()

    # Проверяем права на управление видимостью месяцев
    can_manage_months = request.user.has_perm('monthly_report.can_manage_month_visibility')

    # Проверяем права редактирования для расчета процента заполненности
    can_start = request.user.has_perm('monthly_report.edit_counters_start')
    can_end = request.user.has_perm('monthly_report.edit_counters_end')

    # Формируем set разрешенных полей по правам
    allowed_by_perm = set()
    if can_start:
        allowed_by_perm |= {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"}
    if can_end:
        allowed_by_perm |= {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}

    result = []
    for rec in months_data:
        month_dt = month_key(rec['month_trunc'])
        mc = controls.get(month_dt)

        # Фильтруем неопубликованные месяцы для обычных пользователей
        is_published = mc.is_published if mc else False  # По умолчанию скрыт
        if not is_published and not can_manage_months:
            continue  # Скрываем неопубликованный месяц от обычных пользователей

        # Форматируем название месяца на русском
        month_name = calendar.month_name[month_dt.month] if month_dt.month <= 12 else 'Unknown'
        # Переводим на русский
        month_names_ru = {
            'January': 'Январь', 'February': 'Февраль', 'March': 'Март',
            'April': 'Апрель', 'May': 'Май', 'June': 'Июнь',
            'July': 'Июль', 'August': 'Август', 'September': 'Сентябрь',
            'October': 'Октябрь', 'November': 'Ноябрь', 'December': 'Декабрь'
        }
        month_name = month_names_ru.get(month_name, month_name)

        # Получаем метрики из кэша или вычисляем
        metrics = _calculate_month_metrics(month_dt, allowed_by_perm)
        completion_percentage = metrics['completion_percentage']
        unique_users_count = metrics['unique_users_count']
        auto_fill_potential_percentage = metrics.get('auto_fill_potential_percentage')
        auto_fill_actual_percentage = metrics.get('auto_fill_actual_percentage')

        month_data = {
            'month_str': f"{month_dt.year}-{month_dt.month:02d}",
            'year': month_dt.year,
            'month_number': month_dt.month,
            'month_name': month_name,
            'count': rec['count'],
            'is_editable': bool(mc and mc.edit_until and now < mc.edit_until),
            'is_published': is_published,
            'edit_until': mc.edit_until.strftime('%d.%m %H:%M') if (mc and mc.edit_until) else None,
            'completion_percentage': completion_percentage,
            'unique_users_count': unique_users_count,
        }

        # Добавляем метрики автозаполнения только если есть право на их просмотр
        if request.user.has_perm('monthly_report.view_monthly_report_metrics'):
            month_data['auto_fill_potential_percentage'] = auto_fill_potential_percentage
            month_data['auto_fill_actual_percentage'] = auto_fill_actual_percentage

        result.append(month_data)

    return JsonResponse({
        'ok': True,
        'months': result,
        'permissions': {
            'upload_monthly_report': request.user.has_perm('monthly_report.upload_monthly_report'),
            'manage_months': can_manage_months,
            'view_monthly_report_metrics': request.user.has_perm('monthly_report.view_monthly_report_metrics'),
        }
    })


def _annotate_anomalies_api(reports, current_month, threshold=2000):
    """
    Аннотирует записи информацией об аномалиях печати
    Возвращает словарь {report_id: anomaly_info}

    Args:
        reports: Список объектов MonthlyReport
        current_month: Дата текущего месяца (date object)
        threshold: Порог превышения среднего для определения аномалии (по умолчанию 2000)

    Returns:
        dict: Словарь вида {report_id: anomaly_info_dict}
    """
    from django.db.models import Avg, Count

    if not reports:
        return {}

    serial_numbers = [r.serial_number for r in reports if r.serial_number]

    if not serial_numbers:
        return {r.id: {'is_anomaly': False, 'has_history': False} for r in reports}

    # Получаем средние значения для всех серийных номеров одним запросом
    averages = MonthlyReport.objects.filter(
        serial_number__in=serial_numbers,
        month__lt=current_month
    ).values('serial_number').annotate(
        avg_prints=Avg('total_prints'),
        month_count=Count('id')
    )

    # Создаем словарь для быстрого поиска
    avg_dict = {}
    for item in averages:
        if item['month_count'] > 0:
            avg_dict[item['serial_number']] = {
                'avg': item['avg_prints'],
                'count': item['month_count']
            }

    # Вычисляем аномалию для каждого отчета
    result = {}
    for r in reports:
        # Проверка на отрицательное значение (сброс счётчика)
        is_negative = r.total_prints < 0

        if r.serial_number in avg_dict:
            avg_data = avg_dict[r.serial_number]
            avg = avg_data['avg']
            difference = r.total_prints - avg

            # Аномалия = превышение среднего ИЛИ отрицательное значение
            is_excess = difference > threshold
            is_anomaly = is_excess or is_negative

            # Определяем тип аномалии
            if is_excess and is_negative:
                anomaly_type = 'both'  # И превышение, и сброс (крайне редко)
            elif is_negative:
                anomaly_type = 'negative'  # Сброс счётчика
            elif is_excess:
                anomaly_type = 'excess'  # Превышение среднего
            else:
                anomaly_type = None

            result[r.id] = {
                'is_anomaly': is_anomaly,
                'anomaly_type': anomaly_type,
                'has_history': True,
                'average': round(avg, 0),
                'months_count': avg_data['count'],
                'difference': round(difference, 0),
                'percentage': round((difference / avg * 100), 1) if avg > 0 else 0,
                'threshold': threshold
            }
        else:
            # Нет истории - проверяем только отрицательное значение
            result[r.id] = {
                'is_anomaly': is_negative,
                'anomaly_type': 'negative' if is_negative else None,
                'has_history': False
            }

    return result


@login_required
@permission_required('monthly_report.access_monthly_report', raise_exception=True)
def api_month_detail(request, year, month):
    """
    API endpoint для получения данных месяца (для Vue.js компонента)
    """
    import re
    from datetime import date
    from django.core.paginator import Paginator

    try:
        month_date = date(int(year), int(month), 1)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid date'}, status=400)

    # Проверяем права на управление видимостью месяцев
    can_manage_months = request.user.has_perm('monthly_report.can_manage_month_visibility')

    # Если нет прав на управление видимостью, проверяем публикацию
    if not can_manage_months:
        month_control = MonthControl.objects.filter(month=month_date).first()
        is_published = month_control.is_published if month_control else False

        if not is_published:
            return JsonResponse({
                'ok': False,
                'error': 'Этот месяц еще не опубликован. Обратитесь к администратору.'
            }, status=403)

    # Базовый queryset
    qs = MonthlyReport.objects.filter(month__year=year, month__month=month)

    # Общий поиск
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(organization__icontains=q) | Q(branch__icontains=q) | Q(city__icontains=q) |
            Q(address__icontains=q) | Q(equipment_model__icontains=q) |
            Q(serial_number__icontains=q) | Q(inventory_number__icontains=q)
        )

    # Фильтры по столбцам (текстовые поля)
    filter_fields = {
        'org': 'organization',
        'branch': 'branch',
        'city': 'city',
        'address': 'address',
        'model': 'equipment_model',
        'serial': 'serial_number',
        'inv': 'inventory_number',
        # total обрабатывается отдельно ниже как числовое поле
    }

    for param_key, field_name in filter_fields.items():
        multi_value = request.GET.get(f'{param_key}__in', '').strip()
        single_value = request.GET.get(param_key, '').strip()

        if multi_value:
            values = [v.strip() for v in multi_value.split('||') if v.strip()]
            if values:
                q_objects = []
                for value in values:
                    normalized = ' '.join(value.split())
                    q_objects.append(Q(**{f'{field_name}__iexact': normalized}))
                if q_objects:
                    combined_q = q_objects[0]
                    for q_obj in q_objects[1:]:
                        combined_q |= q_obj
                    qs = qs.filter(combined_q)
        elif single_value:
            qs = qs.filter(**{f'{field_name}__icontains': single_value})

    # Фильтр по номеру
    num_value = request.GET.get('num__in') or request.GET.get('num', '')
    num_value = num_value.strip()
    if num_value:
        # Поддержка множественного выбора через '||' (как в ColumnFilter)
        if '||' in num_value:
            try:
                nums = [int(v.strip()) for v in num_value.split('||') if v.strip().lstrip('-').isdigit()]
                if nums:
                    qs = qs.filter(order_number__in=nums)
            except (ValueError, TypeError):
                pass
        # Поддержка старого формата через запятую (обратная совместимость)
        elif ',' in num_value:
            try:
                nums = [int(v.strip()) for v in num_value.split(',') if v.strip().isdigit()]
                if nums:
                    qs = qs.filter(order_number__in=nums)
            except (ValueError, TypeError):
                pass
        else:
            if re.fullmatch(r'\d+', num_value):
                qs = qs.filter(order_number=int(num_value))
            elif re.fullmatch(r'\d+\s*-\s*\d+', num_value):
                a, b = [int(x) for x in re.split(r'\s*-\s*', num_value)]
                if a > b:
                    a, b = b, a
                qs = qs.filter(order_number__gte=a, order_number__lte=b)

    # Фильтр по итого (total_prints) - числовое поле с поддержкой отрицательных значений
    total_value = request.GET.get('total__in') or request.GET.get('total', '')
    total_value = total_value.strip()
    if total_value:
        # Поддержка множественного выбора через '||' (как в ColumnFilter)
        if '||' in total_value:
            try:
                # Поддержка отрицательных значений
                totals = []
                for v in total_value.split('||'):
                    v = v.strip()
                    if v.lstrip('-').isdigit():  # Разрешаем отрицательные числа
                        totals.append(int(v))
                if totals:
                    qs = qs.filter(total_prints__in=totals)
            except (ValueError, TypeError):
                pass
        # Поддержка старого формата через запятую (обратная совместимость)
        elif ',' in total_value:
            try:
                # Поддержка отрицательных значений
                totals = []
                for v in total_value.split(','):
                    v = v.strip()
                    if v.lstrip('-').isdigit():  # Разрешаем отрицательные числа
                        totals.append(int(v))
                if totals:
                    qs = qs.filter(total_prints__in=totals)
            except (ValueError, TypeError):
                pass
        else:
            # Поддержка диапазонов с отрицательными значениями
            if re.fullmatch(r'-?\d+', total_value):
                qs = qs.filter(total_prints=int(total_value))
            elif re.fullmatch(r'-?\d+\s*-\s*-?\d+', total_value):
                parts = re.split(r'\s*-\s*', total_value)
                # Обрабатываем случаи с отрицательными числами
                if len(parts) >= 2:
                    try:
                        a = int(parts[0]) if parts[0] else 0
                        b = int(parts[-1]) if parts[-1] else 0
                        if a > b:
                            a, b = b, a
                        qs = qs.filter(total_prints__gte=a, total_prints__lte=b)
                    except (ValueError, IndexError):
                        pass

    # Сортировка
    sort_map = {
        'org': 'organization', 'branch': 'branch', 'city': 'city', 'address': 'address',
        'model': 'equipment_model', 'serial': 'serial_number', 'inv': 'inventory_number',
        'total': 'total_prints', 'k1': 'k1', 'k2': 'k2',
        'num': 'order_number',
    }

    sort_param = request.GET.get('sort', 'num')
    if sort_param.startswith('-'):
        sort_field = sort_param[1:]
        descending = True
    else:
        sort_field = sort_param
        descending = False

    if sort_field in sort_map:
        order_by = f"-{sort_map[sort_field]}" if descending else sort_map[sort_field]
        qs = qs.order_by(order_by)
    else:
        qs = qs.order_by('order_number')

    # Фильтр по аномалиям (если запрошен)
    show_anomalies = request.GET.get('show_anomalies') == 'true'
    if show_anomalies:
        # Получаем все серийные номера для расчета среднего
        all_reports = list(qs)
        anomaly_flags = _annotate_anomalies_api(all_reports, month_date, threshold=2000)
        # Фильтруем только аномальные
        anomaly_ids = [report_id for report_id, info in anomaly_flags.items() if info.get('is_anomaly', False)]
        qs = qs.filter(id__in=anomaly_ids)

    # Сохраняем флаг фильтра незаполненных (будет применен после вычисления allowed полей)
    show_unfilled = request.GET.get('show_unfilled') == 'true'

    # Получаем дубли до пагинации
    duplicate_groups = _get_duplicate_groups(month_date)

    # Если нужен фильтр незаполненных, получаем ВСЕ записи для фильтрации в Python
    if show_unfilled:
        # Получаем все записи без пагинации
        all_reports_list = list(qs)
    else:
        # Обычная пагинация
        per_page = request.GET.get('per_page', '100')
        page_num = request.GET.get('page', '1')

        try:
            per_page = int(per_page) if per_page != 'all' else 10000
        except ValueError:
            per_page = 100

        try:
            page_num = int(page_num)
        except ValueError:
            page_num = 1

        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_num)
        all_reports_list = list(page_obj)

    # Вычисляем аномалии для отчетов
    anomaly_flags = _annotate_anomalies_api(all_reports_list, month_date, threshold=2000)

    # Проверяем права редактирования
    can_start = request.user.has_perm('monthly_report.edit_counters_start')
    can_end = request.user.has_perm('monthly_report.edit_counters_end')

    # Формируем set разрешенных полей по правам
    allowed_by_perm = set()
    if can_start:
        allowed_by_perm |= {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"}
    if can_end:
        allowed_by_perm |= {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}

    # Сериализуем записи и применяем фильтр незаполненных если нужно
    reports = []
    for report in all_reports_list:
        # Определяем позицию в группе дублей
        dup_info = None
        is_dup = False
        dup_position = 0
        for (serial, inv), positions in duplicate_groups.items():
            for report_id, position in positions:
                if report_id == report.id:
                    is_dup = True
                    dup_position = position
                    dup_info = {
                        'group_key': f"{serial}_{inv}",
                        'position': position,
                        'total_in_group': len(positions),
                        'is_first': position == 0
                    }
                    break
            if dup_info:
                break

        # Вычисляем разрешенные поля для этого отчета
        # 1. Ограничения по дублям
        if is_dup:
            if dup_position == 0:
                # Первая строка в группе дублей - только A4
                allowed_by_dup = {"a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end"}
            else:
                # Остальные строки в группе дублей - только A3
                allowed_by_dup = {"a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end"}
        else:
            # Обычная строка - без ограничений по дублям
            allowed_by_dup = COUNTER_FIELDS

        # 2. Ограничения по модели устройства
        spec = get_spec_for_model_name(report.equipment_model)
        allowed_by_spec = allowed_counter_fields(spec)

        # 3. Итоговые разрешения = пересечение всех ограничений
        allowed_final = allowed_by_perm & allowed_by_dup & allowed_by_spec

        # Фильтр незаполненных: проверяем только разрешенные end поля
        if show_unfilled:
            # Получаем разрешенные end поля
            allowed_end_fields = {f for f in allowed_final if f.endswith('_end')}
            # Проверяем есть ли незаполненные среди разрешенных
            has_unfilled = False
            for field in allowed_end_fields:
                if getattr(report, field, 0) == 0:
                    has_unfilled = True
                    break
            # Если все разрешенные end поля заполнены - пропускаем запись
            if not has_unfilled:
                continue

        # Формируем словарь ui_allow_* флагов
        ui_allow = {}
        for field in COUNTER_FIELDS:
            ui_allow[f'ui_allow_{field}'] = field in allowed_final

        reports.append({
            'id': report.id,
            'order_number': report.order_number,
            'organization': report.organization,
            'branch': report.branch,
            'city': report.city,
            'address': report.address,
            'equipment_model': report.equipment_model,
            'serial_number': report.serial_number,
            'inventory_number': report.inventory_number,

            # Счётчики
            'a4_bw_start': report.a4_bw_start,
            'a4_bw_end': report.a4_bw_end,
            'a4_color_start': report.a4_color_start,
            'a4_color_end': report.a4_color_end,
            'a3_bw_start': report.a3_bw_start,
            'a3_bw_end': report.a3_bw_end,
            'a3_color_start': report.a3_color_start,
            'a3_color_end': report.a3_color_end,

            # Флаги ручного редактирования
            'a4_bw_end_manual': report.a4_bw_end_manual,
            'a4_color_end_manual': report.a4_color_end_manual,
            'a3_bw_end_manual': report.a3_bw_end_manual,
            'a3_color_end_manual': report.a3_color_end_manual,

            # Авто значения
            'a4_bw_end_auto': report.a4_bw_end_auto,
            'a4_color_end_auto': report.a4_color_end_auto,
            'a3_bw_end_auto': report.a3_bw_end_auto,
            'a3_color_end_auto': report.a3_color_end_auto,

            'total_prints': report.total_prints,
            'k1': report.k1,
            'k2': report.k2,

            # Информация о дублях
            'duplicate_info': dup_info,

            # Информация для бейджей IP·AUTO
            'device_ip': report.device_ip,
            'inventory_last_ok': report.inventory_last_ok.isoformat() if report.inventory_last_ok else None,

            # Аномалия (на основе исторического среднего)
            'is_anomaly': anomaly_flags.get(report.id, {}).get('is_anomaly', False),
            'anomaly_info': anomaly_flags.get(report.id),

            # ui_allow_* флаги
            **ui_allow,
        })

    # Применяем пагинацию к отфильтрованному списку (если был show_unfilled)
    if show_unfilled:
        per_page = request.GET.get('per_page', '100')
        page_num = request.GET.get('page', '1')

        try:
            per_page = int(per_page) if per_page != 'all' else 10000
        except ValueError:
            per_page = 100

        try:
            page_num = int(page_num)
        except ValueError:
            page_num = 1

        # Создаем пагинатор для отфильтрованного списка
        paginator = Paginator(reports, per_page)
        page_obj = paginator.get_page(page_num)
        # Получаем записи для текущей страницы
        reports = list(page_obj)

    # Choices для фильтров
    all_reports = MonthlyReport.objects.filter(month__year=year, month__month=month)
    choices = {
        'org': sorted(set(all_reports.values_list('organization', flat=True).distinct())),
        'branch': sorted(set(all_reports.values_list('branch', flat=True).distinct())),
        'city': sorted(set(all_reports.values_list('city', flat=True).distinct())),
        'address': sorted(set(all_reports.values_list('address', flat=True).distinct())),
        'model': sorted(set(all_reports.values_list('equipment_model', flat=True).distinct())),
        'serial': sorted(set(all_reports.values_list('serial_number', flat=True).distinct())),
        'inv': sorted(set(all_reports.values_list('inventory_number', flat=True).distinct())),
        'total': sorted(set(all_reports.values_list('total_prints', flat=True).distinct())),
    }

    # Проверка прав редактирования
    now = timezone.now()
    mc = MonthControl.objects.filter(month=month_date).first()
    is_editable = bool(mc and mc.edit_until and now < mc.edit_until)

    return JsonResponse({
        'ok': True,
        'reports': reports,
        'pagination': {
            'total': paginator.count,
            'per_page': per_page,
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        },
        'choices': choices,
        'is_editable': is_editable,
        'edit_until': mc.edit_until.strftime('%d.%m %H:%M') if (mc and mc.edit_until) else None,
        'permissions': {
            'edit_counters_start': request.user.has_perm('monthly_report.edit_counters_start'),
            'edit_counters_end': request.user.has_perm('monthly_report.edit_counters_end'),
            'sync_from_inventory': request.user.has_perm('monthly_report.sync_from_inventory'),
        }
    })

@login_required
@permission_required('monthly_report.access_monthly_report', raise_exception=True)
@permission_required('monthly_report.can_reset_auto_polling', raise_exception=True)
@require_http_methods(['POST'])
def reset_manual_flags(request):
    """
    Сбросить флаги ручного редактирования для записи отчета.
    Возвращает принтер на автоматический опрос.
    Требуется право can_reset_auto_polling
    """
    data = json.loads(request.body)
    report_id = data.get('report_id')

    if not report_id:
        return JsonResponse({'success': False, 'error': 'report_id обязателен'}, status=400)

    try:
        report = MonthlyReport.objects.get(pk=report_id)
    except MonthlyReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Отчет не найден'}, status=404)

    # Список полей для сброса
    counter_fields = [
        ('a4_bw_end', 'A4 ч/б конец'),
        ('a4_color_end', 'A4 цвет конец'),
        ('a3_bw_end', 'A3 ч/б конец'),
        ('a3_color_end', 'A3 цвет конец'),
    ]

    # Сбрасываем флаги и логируем изменения
    reset_count = 0
    for field_name, field_label in counter_fields:
        manual_flag = f"{field_name}_manual"

        # Проверяем, был ли флаг установлен
        if getattr(report, manual_flag, False):
            # Получаем старое и новое значения
            old_value = getattr(report, field_name, 0)
            auto_value = getattr(report, f"{field_name}_auto", 0)

            # Сбрасываем флаг
            setattr(report, manual_flag, False)

            # Обновляем счетчик на автоматическое значение
            setattr(report, field_name, auto_value)

            # Логируем изменение
            AuditService.log_counter_change(
                monthly_report=report,
                user=request.user,
                field_name=field_name,
                old_value=old_value,
                new_value=auto_value,
                request=request,
                change_source='manual',
                comment=f'Сброс флага ручного редактирования - возврат на автоопрос'
            )

            reset_count += 1

    report.save()

    return JsonResponse({
        'success': True,
        'message': f'Сброшено флагов: {reset_count}. Принтер возвращен на автоматический опрос.',
        'reset_count': reset_count
    })


@login_required
@permission_required('monthly_report.can_manage_month_visibility', raise_exception=True)
@require_http_methods(['POST'])
def api_toggle_month_published(request):
    """
    Переключение статуса публикации месяца.
    Только пользователи с правом can_manage_month_visibility могут управлять публикацией.
    """
    try:
        data = json.loads(request.body)
        year = data.get('year')
        month = data.get('month')
        is_published = data.get('is_published')

        if not year or not month:
            return JsonResponse({'success': False, 'error': 'Требуются параметры year и month'}, status=400)

        if is_published is None:
            return JsonResponse({'success': False, 'error': 'Требуется параметр is_published'}, status=400)

        # Создаём дату месяца (первое число)
        month_date = date(int(year), int(month), 1)

        # Получаем или создаём MonthControl
        month_control, created = MonthControl.objects.get_or_create(month=month_date)

        # Обновляем статус публикации
        month_control.is_published = is_published
        month_control.save()

        action = 'опубликован' if is_published else 'скрыт'
        logger.info(f"Месяц {month_date} {action} пользователем {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': f'Месяц успешно {action}',
            'is_published': is_published
        })

    except Exception as e:
        logger.exception(f"Ошибка при изменении статуса публикации месяца: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@permission_required('monthly_report.view_monthly_report_metrics', raise_exception=True)
def api_month_users_stats(request, year: int, month: int):
    """
    API endpoint для получения статистики по пользователям за месяц.
    Возвращает список пользователей и количество их изменений.
    Требуется право view_monthly_report_metrics.
    """
    try:
        month_date = date(int(year), int(month), 1)

        # Получаем статистику по пользователям
        users_stats = (
            CounterChangeLog.objects
            .filter(monthly_report__month=month_date)
            .values('user__username', 'user__first_name', 'user__last_name')
            .annotate(changes_count=Count('id'))
            .order_by('-changes_count')
        )

        # Получаем ФИО из таблицы AllowedUser
        from access.models import AllowedUser
        usernames = [stat['user__username'] for stat in users_stats if stat['user__username']]
        allowed_users = {
            au.username: au.full_name
            for au in AllowedUser.objects.filter(username__in=usernames)
            if au.full_name
        }

        # Формируем результат
        users_data = []
        for stat in users_stats:
            username = stat['user__username'] or 'Неизвестно'

            # Приоритет: full_name из AllowedUser -> first_name + last_name -> username
            full_name = allowed_users.get(username)

            if not full_name:
                first_name = stat['user__first_name'] or ''
                last_name = stat['user__last_name'] or ''
                full_name = f"{first_name} {last_name}".strip()

            if not full_name:
                full_name = username

            users_data.append({
                'username': username,
                'full_name': full_name,
                'changes_count': stat['changes_count']
            })

        return JsonResponse({
            'ok': True,
            'users': users_data,
            'total_users': len(users_data),
            'total_changes': sum(u['changes_count'] for u in users_data)
        })

    except Exception as e:
        logger.exception(f"Ошибка при получении статистики пользователей: {e}")
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)
