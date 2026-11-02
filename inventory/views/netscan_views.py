# inventory/views/netscan_views.py
"""Сети для сканирования: CRUD (CBV), запуск скана и ручные действия над найденными устройствами (FBV)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from ..forms import ScanNetworkForm
from ..models import DiscoveredDevice, NetworkScanRun, ScanNetwork
from ..services_netscan import (
    missing_after,
    move_printer_ip,
    network_chunks,
    run_progress,
    start_run,
    visible_missing_q,
)

PERM = "inventory.manage_network_scan"

# Вкладки страницы сети: ключ → (заголовок, фильтр)
TABS = [
    ("attention", "Требуют внимания"),
    (DiscoveredDevice.IP_CHANGE_PENDING, "IP сменился — проверить"),
    (DiscoveredDevice.NOT_IN_CONTRACT, "Нет в договоре"),
    (DiscoveredDevice.CONFLICT, "Конфликты"),
    (DiscoveredDevice.MISSING, "Не отвечают"),
    (DiscoveredDevice.ADDED, "Заведены в опрос"),
    (DiscoveredDevice.IP_CHANGED, "IP обновлён"),
    (DiscoveredDevice.OK, "OK"),
    ("ignored", "Скрытые"),
    ("all", "Все"),
]
ATTENTION = [DiscoveredDevice.IP_CHANGE_PENDING, DiscoveredDevice.NOT_IN_CONTRACT, DiscoveredDevice.CONFLICT]


def _tab_filter(key):
    if key == "ignored":
        return Q(is_ignored=True)
    if key == "all":
        return Q()
    base = Q(is_ignored=False)
    if key == "attention":
        return base & (Q(status__in=ATTENTION) | visible_missing_q())
    if key == DiscoveredDevice.MISSING:
        return base & visible_missing_q()
    return base & Q(status=key)


class NetscanMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = PERM

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["app"] = "netscan"  # не подсвечивать «Опрос устройств» в меню
        return ctx


class ScanNetworkListView(NetscanMixin, ListView):
    model = ScanNetwork
    template_name = "inventory/netscan/network_list.html"
    context_object_name = "networks"

    def get_queryset(self):
        attention = Q(devices__is_ignored=False) & (
            Q(devices__status__in=ATTENTION)
            | Q(devices__status=DiscoveredDevice.MISSING, devices__missed_scans__gte=missing_after())
        )
        return (
            ScanNetwork.objects.prefetch_related("organizations")
            .annotate(
                devices_total=Count("devices", filter=~Q(devices__status=DiscoveredDevice.MISSING), distinct=True),
                attention_total=Count("devices", filter=attention, distinct=True),
            )
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        last_runs = {}
        for run in NetworkScanRun.objects.filter(network__in=ctx["networks"]).order_by("network_id", "-started_at"):
            last_runs.setdefault(run.network_id, run)
        for network in ctx["networks"]:
            network.last_run = last_runs.get(network.id)
        return ctx


class ScanNetworkCreateView(NetscanMixin, CreateView):
    model = ScanNetwork
    form_class = ScanNetworkForm
    template_name = "inventory/netscan/network_form.html"

    def get_success_url(self):
        messages.success(
            self.request, f"Сеть {self.object.cidr} добавлена — запустите сканирование или дождитесь расписания"
        )
        return reverse("inventory:netscan_detail", args=[self.object.pk])


class ScanNetworkUpdateView(NetscanMixin, UpdateView):
    model = ScanNetwork
    form_class = ScanNetworkForm
    template_name = "inventory/netscan/network_form.html"

    def get_success_url(self):
        return reverse("inventory:netscan_detail", args=[self.object.pk])


class ScanNetworkDeleteView(NetscanMixin, DeleteView):
    model = ScanNetwork
    template_name = "inventory/netscan/network_confirm_delete.html"
    success_url = reverse_lazy("inventory:netscan_list")


class ScanNetworkDetailView(NetscanMixin, DetailView):
    model = ScanNetwork
    template_name = "inventory/netscan/network_detail.html"
    context_object_name = "network"

    def get_queryset(self):
        return ScanNetwork.objects.prefetch_related("organizations")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        network = self.object
        devices = network.devices.all()
        tab = self.request.GET.get("tab") or "attention"
        if tab not in dict(TABS):
            tab = "attention"

        counts = devices.aggregate(**{key: Count("id", filter=_tab_filter(key)) for key, _ in TABS})
        ctx["tabs"] = [{"key": key, "title": title, "count": counts[key]} for key, title in TABS]
        ctx["tab"] = tab
        ctx["devices"] = (
            devices.filter(_tab_filter(tab))
            .select_related("printer", "contract_device", "contract_device__organization")
            .order_by("ip_address")
        )
        ctx["runs"] = network.runs.select_related("triggered_by")[:10]
        ctx["running"] = network.runs.filter(status=NetworkScanRun.RUNNING).first()
        ctx["chunks"] = len(network_chunks(network.cidr))
        return ctx


@login_required
@permission_required(PERM, raise_exception=True)
@require_POST
def netscan_run_now(request, pk):
    from ..tasks import NETSCAN_QUEUE, scan_network_chunk_task

    network = get_object_or_404(ScanNetwork, pk=pk)
    run = start_run(network, user=request.user)
    if run is None:
        messages.warning(request, "Сканирование этой сети уже выполняется")
    else:
        scan_network_chunk_task.apply_async((run.id, 0), queue=NETSCAN_QUEUE)
        messages.success(request, f"Сканирование {network.cidr} поставлено в очередь ({run.chunks_total} кусков)")
    return redirect("inventory:netscan_detail", pk=pk)


@login_required
@permission_required(PERM, raise_exception=True)
@require_POST
def netscan_device_move_ip(request, pk):
    """Ручной перенос IP, когда автоматические проверки (MAC, старый адрес) не дали перенести сами."""
    from ..services_netscan import _queue_poll

    device = get_object_or_404(DiscoveredDevice.objects.select_related("printer"), pk=pk)
    printer = device.printer
    if device.status != DiscoveredDevice.IP_CHANGE_PENDING or not printer or not printer.is_active:
        messages.error(request, "Перенос недоступен для этой записи")
    elif not device.ip_address:
        messages.error(request, "У записи нет IP-адреса")
    else:
        old_ip = printer.ip_address
        try:
            move_printer_ip(
                printer,
                device.ip_address,
                device.mac_address,
                comment=f"Сканирование сети, вручную ({request.user.username}): {old_ip} → {device.ip_address}",
                manual=True,
            )
        except IntegrityError:
            messages.error(request, f"IP {device.ip_address} занят другим активным принтером")
        else:
            device.status = DiscoveredDevice.IP_CHANGED
            device.message = f"IP обновлён вручную: {old_ip} → {device.ip_address}"
            device.save(update_fields=["status", "message", "updated_at"])
            _queue_poll(printer)
            messages.success(request, device.message)
    return redirect(
        f"{reverse('inventory:netscan_detail', args=[device.network_id])}?tab={request.POST.get('tab', '')}"
    )


@login_required
@permission_required(PERM, raise_exception=True)
@require_POST
def netscan_device_toggle_ignore(request, pk):
    device = get_object_or_404(DiscoveredDevice, pk=pk)
    device.is_ignored = not device.is_ignored
    device.save(update_fields=["is_ignored", "updated_at"])
    return redirect(
        f"{reverse('inventory:netscan_detail', args=[device.network_id])}?tab={request.POST.get('tab', '')}"
    )


@login_required
@permission_required(PERM, raise_exception=True)
@require_GET
def netscan_run_status(request, pk):
    """Прогресс текущего (или последнего) прогона — страница опрашивает его каждые 3 секунды, пока идёт скан."""
    network = get_object_or_404(ScanNetwork, pk=pk)
    run = network.runs.select_related("network").order_by("-started_at").first()
    return JsonResponse({"run": run_progress(run) if run else None})
