from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.db.models import Q
from .models import ContractDevice
from .forms import ContractDeviceForm   # ← ВАЖНО: добавить

@method_decorator(login_required, name="dispatch")
class ContractDeviceListView(ListView):
    model = ContractDevice
    template_name = "contracts/contractdevice_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = (ContractDevice.objects
              .select_related("organization","city","model__manufacturer","printer"))
        org = self.request.GET.get("org")
        city = self.request.GET.get("city")
        mfr = self.request.GET.get("mfr")
        status = self.request.GET.get("status")
        q = self.request.GET.get("q")
        if org: qs = qs.filter(organization_id=org)
        if city: qs = qs.filter(city_id=city)
        if mfr: qs = qs.filter(model__manufacturer_id=mfr)
        if status: qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q) |
                Q(address__icontains=q) |
                Q(room_number__icontains=q) |
                Q(comment__icontains=q) |
                Q(model__name__icontains=q)
            )
        return qs.order_by("organization","city","address","room_number")

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
