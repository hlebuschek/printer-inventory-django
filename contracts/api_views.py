"""
API views для приложения contracts (Vue.js frontend)
"""
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q

from .models import (
    ContractDevice, ContractStatus, City, Manufacturer,
    DeviceModel
)
from inventory.models import Organization


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.view_contractdevice", raise_exception=True)
def api_contract_devices(request):
    """
    API для получения списка устройств по договорам с фильтрацией и пагинацией
    """
    # Базовый queryset
    qs = (
        ContractDevice.objects
        .select_related("organization", "city", "model__manufacturer", "printer", "status")
    )

    # Фильтрация
    filters = {}

    # Фильтры с поддержкой множественного выбора
    filter_fields = {
        "organization": "organization__name",
        "city": "city__name",
        "address": "address",
        "room": "room_number",
        "manufacturer": "model__manufacturer__name",
        "model": "model__name",
        "serial": "serial_number",
        "status": "status__name",
        "comment": "comment",
    }

    for param_key, field_name in filter_fields.items():
        # Множественные значения (разделенные ||)
        multi_value = request.GET.get(f'{param_key}__in', '').strip()
        single_value = request.GET.get(param_key, '').strip()

        if multi_value:
            values = [v.strip() for v in multi_value.split('||') if v.strip()]
            if values:
                qs = qs.filter(**{f'{field_name}__in': values})
        elif single_value:
            qs = qs.filter(**{f'{field_name}__icontains': single_value})

    # Фильтр по месяцу обслуживания
    service_multi = request.GET.get('service_month__in', '').strip()
    service_single = request.GET.get('service_month', '').strip()

    if service_multi:
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
                pass

    # Пагинация
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 50))

    # Ограничение per_page разумными значениями
    if per_page not in [25, 50, 100, 200, 500, 1000]:
        per_page = 50

    total_count = qs.count()
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(page_number)

    # Сериализация данных
    devices = []
    for device in page:
        devices.append({
            'id': device.id,
            'organization': device.organization.name,
            'organization_id': device.organization.id,
            'city': device.city.name,
            'city_id': device.city.id,
            'address': device.address,
            'room_number': device.room_number,
            'manufacturer': device.model.manufacturer.name,
            'model': device.model.name,
            'model_id': device.model.id,
            'serial_number': device.serial_number,
            'status': device.status.name,
            'status_id': device.status.id,
            'status_color': device.status.color,
            'service_start_month': device.service_start_month_display,
            'service_start_month_iso': device.service_start_month.isoformat() if device.service_start_month else None,
            'comment': device.comment,
            'printer_id': device.printer.id if device.printer else None,
            'created_at': device.created_at.isoformat(),
            'updated_at': device.updated_at.isoformat(),
        })

    return JsonResponse({
        'devices': devices,
        'pagination': {
            'total_count': total_count,
            'total_pages': paginator.num_pages,
            'current_page': page.number,
            'per_page': per_page,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
        }
    })


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
def api_contract_filters(request):
    """
    API для получения данных для фильтров (списки организаций, городов, и т.д.)
    """
    return JsonResponse({
        'organizations': list(Organization.objects.values('id', 'name').order_by('name')),
        'cities': list(City.objects.values('id', 'name').order_by('name')),
        'manufacturers': list(Manufacturer.objects.values('id', 'name').order_by('name')),
        'statuses': list(ContractStatus.objects.filter(is_active=True).values('id', 'name', 'color').order_by('name')),
    })


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
def api_device_models_by_manufacturer(request):
    """
    API для получения моделей по производителю
    """
    manufacturer_id = request.GET.get('manufacturer_id')
    if not manufacturer_id:
        return JsonResponse({'models': []})

    models = DeviceModel.objects.filter(
        manufacturer_id=manufacturer_id
    ).values('id', 'name', 'device_type').order_by('name')

    return JsonResponse({'models': list(models)})
