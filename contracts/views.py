import json
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from .models import ContractDevice, ContractStatus, City, Manufacturer, DeviceModel
from inventory.models import Organization
from .forms import ContractDeviceForm

from io import BytesIO
from django.utils.timezone import now
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from django.http import FileResponse
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import os
from .utils import generate_email_for_device


@method_decorator(
    [
        login_required,
        ensure_csrf_cookie,
        permission_required("contracts.access_contracts_app", raise_exception=True),
        permission_required("contracts.view_contractdevice", raise_exception=True),
    ],
    name="dispatch",
)
class ContractDeviceListView(ListView):
    model = ContractDevice
    template_name = "contracts/contractdevice_list.html"
    paginate_by = 50

    PER_CHOICES = [25, 50, 100, 200, 500, 1000]
    DEFAULT_PER = 50

    def get_paginate_by(self, queryset):
        """Динамическое определение количества записей на странице"""
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

    def get_queryset(self):
        qs = (
            ContractDevice.objects
            .select_related("organization", "city", "model__manufacturer", "printer", "status")
        )

        g = self.request.GET

        # Фильтры с поддержкой множественного выбора
        filter_fields = {
            "org": "organization__name",
            "city": "city__name",
            "address": "address",
            "room": "room_number",
            "mfr": "model__manufacturer__name",
            "model": "model__name",
            "serial": "serial_number",
            "status": "status__name",
            "comment": "comment",
        }

        for param_key, field_name in filter_fields.items():
            # Проверяем множественный параметр (с суффиксом __in)
            multi_value = g.get(f'{param_key}__in', '').strip()
            single_value = g.get(param_key, '').strip()

            if multi_value:
                # ИСПРАВЛЕНИЕ: используем || как разделитель и точное совпадение
                values = [v.strip() for v in multi_value.split('||') if v.strip()]
                if values:
                    # Используем __in для точного совпадения с любым из значений
                    qs = qs.filter(**{f'{field_name}__in': values})
            elif single_value:
                # Одиночное значение - используем частичное совпадение
                qs = qs.filter(**{f'{field_name}__icontains': single_value})

        # Специальная обработка для service_month
        service_multi = g.get('service_month__in', '').strip()
        service_single = g.get('service_month', '').strip()

        if service_multi:
            # Множественный выбор месяцев
            values = [v.strip() for v in service_multi.split('||') if v.strip()]
            if values:
                q_objects = []
                for filter_val in values:
                    if '.' in filter_val:
                        try:
                            month, year = filter_val.split('.')
                            month, year = int(month), int(year)
                            q_objects.append(
                                Q(service_start_month__year=year, service_start_month__month=month)
                            )
                        except (ValueError, TypeError):
                            pass
                    elif '-' in filter_val and len(filter_val) == 7:  # YYYY-MM
                        try:
                            year, month = filter_val.split('-')
                            month, year = int(month), int(year)
                            q_objects.append(
                                Q(service_start_month__year=year, service_start_month__month=month)
                            )
                        except (ValueError, TypeError):
                            pass

                if q_objects:
                    combined_q = q_objects[0]
                    for q_obj in q_objects[1:]:
                        combined_q |= q_obj
                    qs = qs.filter(combined_q)
        elif service_single:
            # Одиночное значение для service_month
            filter_val = service_single
            if '.' in filter_val:
                try:
                    month, year = filter_val.split('.')
                    month, year = int(month), int(year)
                    qs = qs.filter(
                        service_start_month__year=year,
                        service_start_month__month=month
                    )
                except (ValueError, TypeError):
                    qs = qs.extra(
                        where=["to_char(service_start_month, 'MM.YYYY') ILIKE %s"],
                        params=[f'%{filter_val}%']
                    )
            elif '-' in filter_val and len(filter_val) == 7:  # YYYY-MM
                try:
                    year, month = filter_val.split('-')
                    month, year = int(month), int(year)
                    qs = qs.filter(
                        service_start_month__year=year,
                        service_start_month__month=month
                    )
                except (ValueError, TypeError):
                    qs = qs.extra(
                        where=["to_char(service_start_month, 'MM.YYYY') ILIKE %s"],
                        params=[f'%{filter_val}%']
                    )
            else:
                qs = qs.extra(
                    where=["to_char(service_start_month, 'MM.YYYY') ILIKE %s"],
                    params=[f'%{filter_val}%']
                )

        # Общий поиск по ключевому слову
        q = g.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q) |
                Q(address__icontains=q) |
                Q(room_number__icontains=q) |
                Q(comment__icontains=q) |
                Q(model__name__icontains=q) |
                Q(model__manufacturer__name__icontains=q) |
                Q(organization__name__icontains=q) |
                Q(city__name__icontains=q) |
                Q(status__name__icontains=q)
            )

        # Сортировка
        allowed_sorts = {
            "org": "organization__name",
            "city": "city__name",
            "address": "address",
            "room": "room_number",
            "mfr": "model__manufacturer__name",
            "model": "model__name",
            "serial": "serial_number",
            "status": "status__name",
            "service_month": "service_start_month",
            "comment": "comment",
        }

        sort = g.get("sort", "").strip()
        if sort:
            desc = sort.startswith("-")
            key = sort[1:] if desc else sort
            if key in allowed_sorts:
                field = allowed_sorts[key]
                qs = qs.order_by(("-" if desc else "") + field)
        else:
            # Сортировка по умолчанию
            qs = qs.order_by("organization__name", "city__name", "address", "room_number")

        # Сохраняем для использования в context
        self._filters_dict = {}
        filter_keys = ["org", "city", "address", "room", "mfr", "model", "serial", "status", "service_month", "comment"]

        for key in filter_keys:
            # Проверяем множественное значение
            multi_value = g.get(f'{key}__in', '').strip()
            single_value = g.get(key, '').strip()

            if multi_value:
                # Форматируем для отображения
                self._filters_dict[key] = multi_value.replace('||', ', ')
            else:
                self._filters_dict[key] = single_value

        self._sort = sort
        self._qs_for_choices = qs

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # базовый QS без page (для ссылок пагинации/сортировки)
        qs_params = self.request.GET.copy()
        qs_params.pop("page", None)
        ctx["base_qs"] = qs_params.urlencode()

        # qs без per — для меню "количество на странице"
        qs_no_per = self.request.GET.copy()
        qs_no_per.pop('page', None)
        qs_no_per.pop('per', None)
        ctx['qs_no_per'] = qs_no_per.urlencode()

        # текущие значения фильтров и сортировки
        ctx["filters"] = self._filters_dict
        ctx["current_sort"] = self._sort

        # уникальные значения для выпадающих подсказок в фильтрах
        def get_unique_values(field, limit=500):
            """Получить уникальные значения для автодополнения"""
            filter_kwargs = {f"{field}__isnull": False}
            exclude_kwargs = {field: ""}

            return list(
                self._qs_for_choices
                .filter(**filter_kwargs)
                .exclude(**exclude_kwargs)
                .values_list(field, flat=True)
                .distinct()
                .order_by(field)[:limit]
            )

        def get_service_month_choices(limit=500):
            """Получить уникальные месяцы обслуживания в формате MM.YYYY"""
            months = (
                self._qs_for_choices
                .filter(service_start_month__isnull=False)
                .values_list('service_start_month', flat=True)
                .distinct()
                .order_by('-service_start_month')[:limit]
            )
            return [month.strftime('%m.%Y') for month in months if month]

        ctx["choices"] = {
            "org": get_unique_values("organization__name"),
            "city": get_unique_values("city__name"),
            "address": get_unique_values("address"),
            "room": get_unique_values("room_number"),
            "mfr": get_unique_values("model__manufacturer__name"),
            "model": get_unique_values("model__name"),
            "serial": get_unique_values("serial_number"),
            "status": get_unique_values("status__name"),
            "service_month": get_service_month_choices(),
            "comment": get_unique_values("comment"),
        }

        # текущее значение количества записей на странице
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

        # данные для инлайн-редактора (справочники в JSON)
        statuses = ContractStatus.objects.all().order_by("name")
        orgs = Organization.objects.order_by("name").values("id", "name")
        cities = City.objects.order_by("name").values("id", "name")
        mfrs = Manufacturer.objects.order_by("name").values("id", "name")
        models = (DeviceModel.objects
                  .select_related("manufacturer")
                  .order_by("manufacturer__name", "name")
                  .values("id", "name", "manufacturer_id"))

        ctx["statuses_json"] = json.dumps(
            [{"id": s.id, "name": s.name, "color": s.color, "is_active": s.is_active}
             for s in statuses],
            ensure_ascii=False
        )
        ctx["orgs_json"] = json.dumps(list(orgs), ensure_ascii=False)
        ctx["cities_json"] = json.dumps(list(cities), ensure_ascii=False)
        ctx["mfrs_json"] = json.dumps(list(mfrs), ensure_ascii=False)
        ctx["models_json"] = json.dumps(list(models), ensure_ascii=False)
        ctx['column_filter_styles_loaded'] = False
        ctx['column_filter_scripts_loaded'] = False

        return ctx


@method_decorator(
    [
        login_required,
        permission_required("contracts.access_contracts_app", raise_exception=True),
        permission_required("contracts.add_contractdevice", raise_exception=True),
    ],
    name="dispatch",
)
class ContractDeviceCreateView(CreateView):
    model = ContractDevice
    form_class = ContractDeviceForm
    template_name = "contracts/contractdevice_form.html"
    success_url = reverse_lazy("contracts:list")


@method_decorator(
    [
        login_required,
        permission_required("contracts.access_contracts_app", raise_exception=True),
        permission_required("contracts.change_contractdevice", raise_exception=True),
    ],
    name="dispatch",
)
class ContractDeviceUpdateView(UpdateView):
    model = ContractDevice
    form_class = ContractDeviceForm
    template_name = "contracts/contractdevice_form.html"
    success_url = reverse_lazy("contracts:list")


# ── API: частичное обновление (инлайн-редактор) ──────────────────────────────
@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.change_contractdevice", raise_exception=True)
@require_POST
def contractdevice_update_api(request, pk: int):
    try:
        obj = (
            ContractDevice.objects
            .select_related("organization", "city", "model__manufacturer", "status")
            .get(pk=pk)
        )
    except ContractDevice.DoesNotExist:
        raise Http404("Device not found")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректный JSON"}, status=400)

    # разрешённые поля (включая FK)
    allowed = (
        "address", "room_number", "serial_number", "comment", "status_id",
        "organization_id", "city_id", "model_id", "service_start_month"
    )
    data = {k: v for k, v in payload.items() if k in allowed}

    # нормализация текстовых полей
    for key in ("address", "room_number", "serial_number", "comment"):
        if key in data and data[key] is not None:
            data[key] = str(data[key]).strip()

    # обработка даты принятия на обслуживание
    if "service_start_month" in data and data["service_start_month"]:
        try:
            # Ожидаем формат YYYY-MM от HTML input type="month"
            date_str = str(data["service_start_month"]).strip()
            if date_str:
                # Парсим YYYY-MM и устанавливаем первое число месяца
                year, month = date_str.split('-')
                obj.service_start_month = datetime(int(year), int(month), 1).date()
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"ok": False, "error": "Некорректный формат месяца обслуживания"}, status=400)
    elif "service_start_month" in data:
        obj.service_start_month = None

    # FK: организация/город/модель
    if "organization_id" in data and data["organization_id"]:
        try:
            obj.organization_id = int(data["organization_id"])
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "Некорректная организация"}, status=400)

    if "city_id" in data and data["city_id"]:
        try:
            obj.city_id = int(data["city_id"])
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "Некорректный город"}, status=400)

    if "model_id" in data and data["model_id"]:
        try:
            obj.model_id = int(data["model_id"])
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "Некорректная модель"}, status=400)

    # статус
    if "status_id" in data:
        try:
            st = ContractStatus.objects.get(pk=int(data["status_id"]))
            obj.status = st
        except (TypeError, ValueError, ContractStatus.DoesNotExist):
            return JsonResponse({"ok": False, "error": "Статус не найден"}, status=400)

    # простые поля
    for k in ("address", "room_number", "serial_number", "comment"):
        if k in data:
            setattr(obj, k, data[k])

    # сохранение с контролем уникальности серийника в рамках организации
    try:
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        return JsonResponse(
            {"ok": False, "error": "Нарушение уникальности (серийный номер уже используется в этой организации)."},
            status=400
        )

    # свежие related-объекты в ответ
    obj.refresh_from_db()
    st = obj.status
    return JsonResponse({
        "ok": True,
        "device": {
            "id": obj.id,
            "address": obj.address,
            "room_number": obj.room_number,
            "serial_number": obj.serial_number,
            "comment": obj.comment,
            "service_start_month": obj.service_start_month.strftime('%Y-%m') if obj.service_start_month else "",
            "service_start_month_display": obj.service_start_month_display,
            "status": {
                "id": st.id if st else None,
                "name": st.name if st else "",
                "color": st.color if st else "#6c757d",
                "is_active": st.is_active if st else True,
            },
            "organization": {"id": obj.organization_id, "name": str(obj.organization)},
            "city": {"id": obj.city_id, "name": str(obj.city)},
            "manufacturer": {"id": obj.model.manufacturer_id, "name": str(obj.model.manufacturer)},
            "model": {"id": obj.model_id, "name": obj.model.name},
        }
    })


# ── API: удаление ─────────────────────────────────────────────────────────────
@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.delete_contractdevice", raise_exception=True)
@require_POST
def contractdevice_delete_api(request, pk: int):
    try:
        obj = ContractDevice.objects.get(pk=pk)
    except ContractDevice.DoesNotExist:
        raise Http404("Device not found")
    obj.delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.add_contractdevice", raise_exception=True)
@require_POST
def contractdevice_create_api(request):
    """
    Создать устройство договора.
    Ожидает JSON:
    {
      organization_id, city_id, model_id, status_id,
      address, room_number, serial_number, comment, service_start_month
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректный JSON"}, status=400)

    required = ("organization_id", "city_id", "model_id", "status_id")
    for k in required:
        if not payload.get(k):
            return JsonResponse({"ok": False, "error": f"Не заполнено поле: {k}"}, status=400)

    # нормализуем строки
    for key in ("address", "room_number", "serial_number", "comment"):
        if key in payload and payload[key] is not None:
            payload[key] = str(payload[key]).strip()

    # обработка даты принятия на обслуживание
    service_start_month = None
    if payload.get("service_start_month"):
        try:
            date_str = str(payload["service_start_month"]).strip()
            if date_str:
                year, month = date_str.split('-')
                service_start_month = datetime(int(year), int(month), 1).date()
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"ok": False, "error": "Некорректный формат месяца обслуживания"}, status=400)

    try:
        with transaction.atomic():
            obj = ContractDevice.objects.create(
                organization_id=payload["organization_id"],
                city_id=payload["city_id"],
                model_id=payload["model_id"],
                status_id=payload["status_id"],
                address=payload.get("address") or "",
                room_number=payload.get("room_number") or "",
                serial_number=payload.get("serial_number") or "",
                comment=payload.get("comment") or "",
                service_start_month=service_start_month,
            )
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "Нарушение уникальности (серийный номер в организации)."},
                            status=400)

    # перечитаем для ответа с названиями
    obj = (ContractDevice.objects
           .select_related("organization", "city", "model__manufacturer", "status", "printer")
           .get(pk=obj.pk))

    st = obj.status
    return JsonResponse({
        "ok": True,
        "device": {
            "id": obj.id,
            "address": obj.address,
            "room_number": obj.room_number,
            "serial_number": obj.serial_number,
            "comment": obj.comment,
            "service_start_month": obj.service_start_month.strftime('%Y-%m') if obj.service_start_month else "",
            "service_start_month_display": obj.service_start_month_display,
            "organization": {"id": obj.organization_id, "name": str(obj.organization)},
            "city": {"id": obj.city_id, "name": str(obj.city)},
            "manufacturer": {"id": obj.model.manufacturer_id, "name": str(obj.model.manufacturer)},
            "model": {"id": obj.model_id, "name": obj.model.name},
            "status": {
                "id": st.id if st else None,
                "name": st.name if st else "",
                "color": st.color if st else "#6c757d",
                "is_active": st.is_active if st else True,
            },
            "has_printer": bool(obj.printer_id),
            "printer_id": obj.printer_id,
        }
    })


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.export_contracts", raise_exception=True)
def contractdevice_export_excel(request):
    # 1) собрать queryset — те же фильтры/поиск/сортировка
    qs = (ContractDevice.objects
          .select_related("organization", "city", "model__manufacturer", "status", "printer"))

    g = request.GET

    _filters = {
        "org": ("organization__name__icontains", g.get("org")),
        "city": ("city__name__icontains", g.get("city")),
        "address": ("address__icontains", g.get("address")),
        "room": ("room_number__icontains", g.get("room")),
        "mfr": ("model__manufacturer__name__icontains", g.get("mfr")),
        "model": ("model__name__icontains", g.get("model")),
        "serial": ("serial_number__icontains", g.get("serial")),
        "status": ("status__name__icontains", g.get("status")),
        "service_month": ("service_start_month__icontains", g.get("service_month")),
        "comment": ("comment__icontains", g.get("comment")),
    }
    for key, (lookup, val) in _filters.items():
        if val:
            if key == "service_month":
                # Специальная обработка для фильтра месяца
                filter_val = val.strip()
                if '.' in filter_val:
                    try:
                        month, year = filter_val.split('.')
                        month, year = int(month), int(year)
                        qs = qs.filter(
                            service_start_month__year=year,
                            service_start_month__month=month
                        )
                        continue
                    except (ValueError, TypeError):
                        pass
                qs = qs.extra(
                    where=["to_char(service_start_month, 'MM.YYYY') ILIKE %s"],
                    params=[f'%{filter_val}%']
                )
            else:
                qs = qs.filter(**{lookup: val})

    q = g.get("q")
    if q:
        qs = qs.filter(
            Q(serial_number__icontains=q) |
            Q(address__icontains=q) |
            Q(room_number__icontains=q) |
            Q(comment__icontains=q) |
            Q(model__name__icontains=q) |
            Q(model__manufacturer__name__icontains=q) |
            Q(organization__name__icontains=q) |
            Q(city__name__icontains=q) |
            Q(status__name__icontains=q)
        )

    allowed = {
        "org": "organization__name",
        "city": "city__name",
        "address": "address",
        "room": "room_number",
        "mfr": "model__manufacturer__name",
        "model": "model__name",
        "serial": "serial_number",
        "status": "status__name",
        "service_month": "service_start_month",
        "comment": "comment",
    }
    sort = g.get("sort")
    if sort:
        desc = sort.startswith("-")
        key = sort[1:] if desc else sort
        if key in allowed:
            field = allowed[key]
            qs = qs.order_by(("-" if desc else "") + field)
    else:
        qs = qs.order_by("organization__name", "city__name", "address", "room_number")

    # 2) helpers для цвета статуса
    def xl_color(hex_color: str) -> str:
        if not hex_color:
            return "FF6C757D"
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return ("FF" + h.upper())[:8]  # ARGB

    def contrast_font(hex_color: str) -> str:
        try:
            h = hex_color.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            y = (r * 299 + g * 587 + b * 114) / 1000
            return "FF000000" if y > 140 else "FFFFFFFF"  # черный / белый
        except Exception:
            return "FF000000"

    # 3) сформировать книгу
    wb = Workbook()
    ws = wb.active
    ws.title = "Устройства"

    headers = [
        "№", "Организация", "Город", "Адрес", "№ кабинета",
        "Производитель", "Модель", "Серийный номер", "Месяц обслуживания", "Статус", "Комментарий"
    ]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
        cell.fill = PatternFill("solid", fgColor="FFE9ECEF")  # светло-серый заголовок

    # 4) строки
    row = 2
    for i, d in enumerate(qs.iterator(), start=1):
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=str(d.organization))
        ws.cell(row=row, column=3, value=str(d.city))
        ws.cell(row=row, column=4, value=d.address or "").alignment = Alignment(wrap_text=True)
        ws.cell(row=row, column=5, value=d.room_number or "")

        ws.cell(row=row, column=6, value=str(d.model.manufacturer))
        ws.cell(row=row, column=7, value=d.model.name)
        ws.cell(row=row, column=8, value=d.serial_number or "")

        # Месяц обслуживания
        service_month_value = d.service_start_month_display if d.service_start_month else ""
        ws.cell(row=row, column=9, value=service_month_value)

        # Статус
        st_name = d.status.name if d.status else ""
        st_cell = ws.cell(row=row, column=10, value=st_name)
        st_cell.alignment = Alignment(wrap_text=True)
        if d.status and d.status.color:
            st_cell.fill = PatternFill("solid", fgColor=xl_color(d.status.color))
            st_cell.font = Font(color=contrast_font(d.status.color))

        ws.cell(row=row, column=11, value=d.comment or "").alignment = Alignment(wrap_text=True)
        row += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    # 5) автоширина колонок (ограничим разумно)
    for col_cells in ws.columns:
        letter = col_cells[0].column_letter
        max_len = 0
        for c in col_cells:
            v = c.value
            if v is None:
                continue
            s = str(v)
            if "\n" in s:
                s = max(s.split("\n"), key=len)
            max_len = max(max_len, len(s))
        ws.column_dimensions[letter].width = min(60, max(8, max_len + 2))

    # 6) ответ
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"contract_devices_{now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
    return HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.view_contractdevice", raise_exception=True)
def contractdevice_lookup_by_serial_api(request):
    serial = (request.GET.get("serial") or "").strip()
    if not serial:
        return JsonResponse({"ok": False, "error": "serial не передан"}, status=400)

    try:
        dev = (ContractDevice.objects
               .select_related("organization", "city", "model__manufacturer")
               .get(serial_number__iexact=serial))
    except ContractDevice.DoesNotExist:
        return JsonResponse({"ok": True, "found": False})

    return JsonResponse({
        "ok": True,
        "found": True,
        "device": {
            "id": dev.id,
            "serial_number": dev.serial_number,
            "organization": {"id": dev.organization_id, "name": str(dev.organization) if dev.organization else ""},
            "city": {"id": dev.city_id, "name": str(dev.city) if dev.city else ""},
            "model": {"id": dev.model_id, "name": dev.model.name if dev.model_id else ""},
            "manufacturer": {
                "id": dev.model.manufacturer_id if dev.model_id else None,
                "name": str(dev.model.manufacturer) if dev.model_id else ""
            },
            "service_start_month": dev.service_start_month_display,
        }
    })


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.view_contractdevice", raise_exception=True)
def generate_email_msg(request, pk: int):
    """
    Генерирует .eml файл (email) с заявкой на картридж для устройства.
    """
    return generate_email_for_device(
        device_id=pk,
        user_email=request.user.email or 'sd@abi.com.ru'
    )