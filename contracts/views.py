from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.db.models import Q
from .models import ContractDevice
from .forms import ContractDeviceForm

@method_decorator(login_required, name="dispatch")
class ContractDeviceListView(ListView):
    model = ContractDevice
    template_name = "contracts/contractdevice_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = (ContractDevice.objects
              .select_related("organization", "city", "model__manufacturer", "printer", "status"))

        g = self.request.GET

        # колоночные фильтры (icontains, как в Excel)
        _filters = {
            "org":    ("organization__name__icontains",        g.get("org")),
            "city":   ("city__name__icontains",                g.get("city")),
            "address":("address__icontains",                   g.get("address")),
            "room":   ("room_number__icontains",               g.get("room")),
            "mfr":    ("model__manufacturer__name__icontains", g.get("mfr")),
            "model":  ("model__name__icontains",               g.get("model")),
            "serial": ("serial_number__icontains",             g.get("serial")),
            "status": ("status__name__icontains",              g.get("status")),
            "comment":("comment__icontains",                   g.get("comment")),
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

        # в контекст
        self._filters_dict = {k: (v[1] or "") for k, v in _filters.items()}
        self._sort = sort or ""
        self._qs_for_choices = qs  # подсказки строим на уже отфильтрованной выборке
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # для пагинации/сортировки сохраняем все текущие фильтры
        qs = self.request.GET.copy()
        qs.pop("page", None)
        ctx["base_qs"] = qs.urlencode()
        ctx["filters"] = self._filters_dict
        ctx["current_sort"] = self._sort

        # уникальные значения для выпадающих подсказок
        def uniq(field, limit=200):
            q = {f"{field}__isnull": False}
            return list(
                self._qs_for_choices.filter(**q)
                .exclude(**{field: ""})
                .values_list(field, flat=True)
                .distinct().order_by(field)[:limit]
            )

        ctx["choices"] = {
            "org":    uniq("organization__name"),
            "city":   uniq("city__name"),
            "address":uniq("address"),
            "room":   uniq("room_number"),
            "mfr":    uniq("model__manufacturer__name"),
            "model":  uniq("model__name"),
            "serial": uniq("serial_number"),
            "status": uniq("status__name"),
            "comment":uniq("comment"),
        }
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
