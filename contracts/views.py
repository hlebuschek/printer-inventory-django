import json
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from .models import ContractDevice, ContractStatus, City, Manufacturer, DeviceModel
from inventory.models import Organization
from .forms import ContractDeviceForm

@method_decorator([login_required, ensure_csrf_cookie], name="dispatch")
class ContractDeviceListView(ListView):
    model = ContractDevice
    template_name = "contracts/contractdevice_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            ContractDevice.objects
            .select_related("organization", "city", "model__manufacturer", "printer", "status")
        )

        g = self.request.GET
        # фильтры «как в Excel» по колонкам
        _filters = {
            "org":     ("organization__name__icontains",        g.get("org")),
            "city":    ("city__name__icontains",                g.get("city")),
            "address": ("address__icontains",                   g.get("address")),
            "room":    ("room_number__icontains",               g.get("room")),
            "mfr":     ("model__manufacturer__name__icontains", g.get("mfr")),
            "model":   ("model__name__icontains",               g.get("model")),
            "serial":  ("serial_number__icontains",             g.get("serial")),
            "status":  ("status__name__icontains",              g.get("status")),
            "comment": ("comment__icontains",                   g.get("comment")),
        }
        for lookup, val in _filters.values():
            if val:
                qs = qs.filter(**{lookup: val})

        # общий поиск
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

        # сортировка
        allowed = {
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
        sort = g.get("sort")
        if sort:
            desc = sort.startswith("-")
            key = sort[1:] if desc else sort
            if key in allowed:
                field = allowed[key]
                qs = qs.order_by(("-" if desc else "") + field)
        else:
            qs = qs.order_by("organization__name", "city__name", "address", "room_number")

        # вспомогательные значения для контекста
        self._filters_dict = {k: (v[1] or "") for k, v in _filters.items()}
        self._sort = sort or ""
        self._qs_for_choices = qs  # подсказки строим на уже отфильтрованной выборке
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # базовый QS без page (для пагинации/сортировок)
        qs = self.request.GET.copy()
        qs.pop("page", None)
        ctx["base_qs"] = qs.urlencode()
        ctx["filters"] = self._filters_dict
        ctx["current_sort"] = self._sort

        # уникальные значения для выпадающих подсказок в фильтрах
        def uniq(field, limit=200):
            q = {f"{field}__isnull": False}
            return list(
                self._qs_for_choices.filter(**q)
                .exclude(**{field: ""})
                .values_list(field, flat=True)
                .distinct().order_by(field)[:limit]
            )

        ctx["choices"] = {
            "org":     uniq("organization__name"),
            "city":    uniq("city__name"),
            "address": uniq("address"),
            "room":    uniq("room_number"),
            "mfr":     uniq("model__manufacturer__name"),
            "model":   uniq("model__name"),
            "serial":  uniq("serial_number"),
            "status":  uniq("status__name"),
            "comment": uniq("comment"),
        }

        # данные для инлайн-редактора (селекты)
        statuses = ContractStatus.objects.all().order_by("name")
        orgs     = Organization.objects.order_by("name").values("id", "name")
        cities   = City.objects.order_by("name").values("id", "name")
        mfrs     = Manufacturer.objects.order_by("name").values("id", "name")
        models   = DeviceModel.objects.order_by("manufacturer__name", "name") \
                                      .values("id", "name", "manufacturer_id")

        ctx["statuses_json"] = json.dumps(
            [{"id": s.id, "name": s.name, "color": s.color, "is_active": s.is_active} for s in statuses],
            ensure_ascii=False
        )
        ctx["orgs_json"]   = json.dumps(list(orgs), ensure_ascii=False)
        ctx["cities_json"] = json.dumps(list(cities), ensure_ascii=False)
        ctx["mfrs_json"]   = json.dumps(list(mfrs), ensure_ascii=False)
        ctx["models_json"] = json.dumps(list(models), ensure_ascii=False)
        return ctx


@method_decorator(login_required, name="dispatch")
class ContractDeviceCreateView(CreateView):
    model = ContractDevice
    form_class = ContractDeviceForm
    template_name = "contracts/contractdevice_form.html"
    success_url = reverse_lazy("contracts:list")


@method_decorator(login_required, name="dispatch")
class ContractDeviceUpdateView(UpdateView):
    model = ContractDevice
    form_class = ContractDeviceForm
    template_name = "contracts/contractdevice_form.html"
    success_url = reverse_lazy("contracts:list")


# ── API: частичное обновление (инлайн-редактор) ──────────────────────────────
@login_required
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
        "organization_id", "city_id", "model_id"
    )
    data = {k: v for k, v in payload.items() if k in allowed}

    # нормализация текстовых полей
    for key in ("address", "room_number", "serial_number", "comment"):
        if key in data and data[key] is not None:
            data[key] = str(data[key]).strip()

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
            "status": {
                "id": st.id if st else None,
                "name": st.name if st else "",
                "color": st.color if st else "#6c757d",
                "is_active": st.is_active if st else True,
            },
            "organization": {"id": obj.organization_id, "name": str(obj.organization)},
            "city":         {"id": obj.city_id,         "name": str(obj.city)},
            "manufacturer": {"id": obj.model.manufacturer_id, "name": str(obj.model.manufacturer)},
            "model":        {"id": obj.model_id,        "name": obj.model.name},
        }
    })


# ── API: удаление ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def contractdevice_delete_api(request, pk: int):
    try:
        obj = ContractDevice.objects.get(pk=pk)
    except ContractDevice.DoesNotExist:
        raise Http404("Device not found")
    obj.delete()
    return JsonResponse({"ok": True})

@login_required
@require_POST
def contractdevice_create_api(request):
    """
    Создать устройство договора.
    Ожидает JSON:
    {
      organization_id, city_id, model_id, status_id,
      address, room_number, serial_number, comment
    }
    """
    import json
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
            )
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "Нарушение уникальности (серийный номер в организации)."}, status=400)

    # перечитаем для ответа с названиями
    obj = (ContractDevice.objects
           .select_related("organization","city","model__manufacturer","status","printer")
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
            "organization": {"id": obj.organization_id, "name": str(obj.organization)},
            "city":         {"id": obj.city_id,         "name": str(obj.city)},
            "manufacturer": {"id": obj.model.manufacturer_id, "name": str(obj.model.manufacturer)},
            "model":        {"id": obj.model_id, "name": obj.model.name},
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