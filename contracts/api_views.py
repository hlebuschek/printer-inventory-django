"""
API views для приложения contracts (Vue.js frontend)
"""
import json
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch

from .models import (
    ContractDevice, ContractStatus, City, Manufacturer,
    DeviceModel
)
from inventory.models import Organization

logger = logging.getLogger(__name__)


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.view_contractdevice", raise_exception=True)
def api_contract_devices(request):
    """
    API для получения списка устройств по договорам с фильтрацией и пагинацией
    """
    # Проверяем доступность integrations приложения
    try:
        from integrations.models import GLPISync
        has_integrations = True
    except ImportError:
        has_integrations = False

    # Базовый queryset
    qs = (
        ContractDevice.objects
        .select_related("organization", "city", "model__manufacturer", "printer", "status")
    )

    # Добавляем GLPI синхронизацию если приложение установлено
    if has_integrations:
        # Prefetch только последнюю синхронизацию для каждого устройства
        latest_sync_prefetch = Prefetch(
            'glpi_syncs',
            queryset=GLPISync.objects.order_by('-checked_at')[:1],
            to_attr='latest_glpi_sync'
        )
        qs = qs.prefetch_related(latest_sync_prefetch)

    # Поиск по ключевому слову (q)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(serial_number__icontains=q) |
            Q(address__icontains=q) |
            Q(model__name__icontains=q) |
            Q(comment__icontains=q)
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

    # Фильтр по GLPI статусу
    if has_integrations:
        glpi_status_multi = request.GET.get('glpi_status__in', '').strip()
        glpi_status_single = request.GET.get('glpi_status', '').strip()
        logger.info(f"[GLPI FILTER] Входящие параметры - glpi_status__in: '{glpi_status_multi}', glpi_status: '{glpi_status_single}'")

        # Обрабатываем множественный выбор (__in) или одиночный
        status_labels = []
        if glpi_status_multi:
            status_labels = [v.strip() for v in glpi_status_multi.split('||') if v.strip()]
            logger.info(f"[GLPI FILTER] Множественный выбор, распознанные лейблы: {status_labels}")
        elif glpi_status_single:
            status_labels = [glpi_status_single]
            logger.info(f"[GLPI FILTER] Одиночный выбор, лейбл: {glpi_status_single}")

        if status_labels:
            logger.info(f"[GLPI FILTER] Итоговые лейблы для фильтрации: {status_labels}")

            try:
                # Маппинг лейблов в коды статусов (должны совпадать с STATUS_CHOICES в модели)
                label_to_code = {
                    'Найден (1 карточка)': 'FOUND_SINGLE',
                    'Найдено несколько карточек': 'FOUND_MULTIPLE',
                    'Не найден в GLPI': 'NOT_FOUND',
                    'Ошибка при проверке': 'ERROR'
                }
                status_values = [label_to_code.get(label, label) for label in status_labels]
                logger.info(f"[GLPI FILTER] Коды статусов для фильтрации: {status_values}")

                # Получаем ID устройств с нужными статусами (только последняя синхронизация)
                from integrations.models import GLPISync
                from django.db.models import Max

                logger.info(f"[GLPI FILTER] Начинаем запрос к GLPISync...")
                # Получаем последнюю дату проверки для каждого устройства с нужным статусом
                # Группируем по contract_device_id и берем максимальную дату
                latest_syncs = GLPISync.objects.filter(
                    status__in=status_values
                ).values('contract_device_id').annotate(
                    latest_check=Max('checked_at')
                ).values_list('contract_device_id', 'latest_check')

                latest_syncs_list = list(latest_syncs)
                logger.info(f"[GLPI FILTER] Найдено синхронизаций с нужными статусами: {len(latest_syncs_list)}")

                # Теперь получаем ID всех устройств, у которых последняя синхронизация
                # имеет нужный статус
                device_ids = set()
                for contract_device_id, latest_check in latest_syncs_list:
                    # Проверяем что это действительно последняя синхронизация для устройства
                    # (а не просто последняя с нужным статусом)
                    is_latest = not GLPISync.objects.filter(
                        contract_device_id=contract_device_id,
                        checked_at__gt=latest_check
                    ).exists()

                    if is_latest:
                        device_ids.add(contract_device_id)
                        logger.debug(f"[GLPI FILTER] Device {contract_device_id} добавлен (последняя синхронизация: {latest_check})")
                    else:
                        logger.debug(f"[GLPI FILTER] Device {contract_device_id} пропущен (не последняя синхронизация)")

                logger.info(f"[GLPI FILTER] Итоговый список device_ids для фильтрации: {device_ids}")
                logger.info(f"[GLPI FILTER] Количество устройств ДО фильтра: {qs.count()}")

                if device_ids:
                    qs = qs.filter(id__in=device_ids)
                    logger.info(f"[GLPI FILTER] Количество устройств ПОСЛЕ фильтра: {qs.count()}")
                else:
                    # Если нет устройств с таким статусом, вернуть пустой queryset
                    logger.warning(f"[GLPI FILTER] Не найдено устройств с статусами {status_values}, возвращаем пустой queryset")
                    qs = qs.none()

            except Exception as e:
                logger.error(f"[GLPI FILTER] ОШИБКА при фильтрации GLPI: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[GLPI FILTER] Traceback:\n{traceback.format_exc()}")
                # Не применяем фильтр при ошибке - показываем все устройства
                pass

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
        device_data = {
            'id': device.id,
            'organization': device.organization.name,
            'organization_id': device.organization.id,
            'city': device.city.name,
            'city_id': device.city.id,
            'address': device.address,
            'room_number': device.room_number,
            'manufacturer': device.model.manufacturer.name,
            'manufacturer_id': device.model.manufacturer.id,
            'model': device.model.name,
            'model_id': device.model.id,
            'has_network_port': device.model.has_network_port,
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
        }

        # Добавляем данные GLPI синхронизации если доступно
        if has_integrations and hasattr(device, 'latest_glpi_sync') and device.latest_glpi_sync:
            sync = device.latest_glpi_sync[0]
            device_data.update({
                'glpi_status': sync.status,
                'glpi_status_display': sync.get_status_display(),
                'glpi_count': sync.glpi_count,
                'glpi_ids': sync.glpi_ids,
                'glpi_checked_at': sync.checked_at.isoformat(),
                'glpi_is_synced': sync.is_synced,
                'glpi_has_conflict': sync.has_conflict,
            })
        else:
            device_data.update({
                'glpi_status': None,
                'glpi_status_display': None,
                'glpi_count': 0,
                'glpi_ids': [],
                'glpi_checked_at': None,
                'glpi_is_synced': False,
                'glpi_has_conflict': False,
            })

        devices.append(device_data)

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
    # Проверяем доступность integrations приложения
    try:
        from integrations.models import GLPISync
        has_integrations = True
    except ImportError:
        has_integrations = False

    # Базовый queryset
    devices = ContractDevice.objects.select_related(
        'organization', 'city', 'model__manufacturer', 'status'
    )

    # Добавляем GLPI синхронизацию если приложение установлено
    if has_integrations:
        # Prefetch только последнюю синхронизацию для каждого устройства
        latest_sync_prefetch = Prefetch(
            'glpi_syncs',
            queryset=GLPISync.objects.order_by('-checked_at')[:1],
            to_attr='latest_glpi_sync'
        )
        devices = devices.prefetch_related(latest_sync_prefetch)

    # Применяем текущие фильтры для кросс-фильтрации
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
        multi_value = request.GET.get(f'{param_key}__in', '').strip()
        single_value = request.GET.get(param_key, '').strip()

        if multi_value:
            values = [v.strip() for v in multi_value.split('||') if v.strip()]
            if values:
                devices = devices.filter(**{f'{field_name}__in': values})
        elif single_value:
            devices = devices.filter(**{f'{field_name}__icontains': single_value})

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
                elif '-' in filter_val and len(filter_val) == 7:
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
                devices = devices.filter(combined_q)
    elif service_single:
        filter_val = service_single
        if '.' in filter_val:
            try:
                month, year = filter_val.split('.')
                month, year = int(month), int(year)
                devices = devices.filter(
                    service_start_month__year=year,
                    service_start_month__month=month
                )
            except (ValueError, TypeError):
                pass

    # Уникальные значения для фильтров (с учетом примененных фильтров)
    choices = {
        'org': sorted(set(d.organization.name for d in devices if d.organization)),
        'city': sorted(set(d.city.name for d in devices if d.city)),
        'address': sorted(set(d.address for d in devices if d.address)),
        'room': sorted(set(d.room_number for d in devices if d.room_number)),
        'mfr': sorted(set(d.model.manufacturer.name for d in devices if d.model and d.model.manufacturer)),
        'model': sorted(set(d.model.name for d in devices if d.model)),
        'serial': sorted(set(d.serial_number for d in devices if d.serial_number)),
        'status': sorted(set(d.status.name for d in devices if d.status)),
        'service_month': sorted(set(d.service_start_month_display for d in devices if d.service_start_month)),
        'comment': [],  # Too many unique values, don't provide suggestions
    }

    # Добавляем GLPI статусы - ТОЛЬКО те которые реально есть в данных (как все остальные столбцы)
    if has_integrations:
        # Маппинг кодов в лейблы (как в api_contract_devices)
        code_to_label = {
            'FOUND_SINGLE': 'Найден (1 карточка)',
            'FOUND_MULTIPLE': 'Найдено несколько карточек',
            'NOT_FOUND': 'Не найден в GLPI',
            'ERROR': 'Ошибка при проверке'
        }
        # Собираем уникальные статусы из реальных данных (точно так же как другие столбцы)
        unique_statuses = set()
        for d in devices:
            if hasattr(d, 'latest_glpi_sync') and d.latest_glpi_sync:
                sync = d.latest_glpi_sync[0]
                if sync.status:
                    unique_statuses.add(sync.status)

        # Конвертируем коды в лейблы и сортируем
        choices['glpi'] = sorted([code_to_label.get(status) for status in unique_statuses if code_to_label.get(status)])
    else:
        choices['glpi'] = []

    return JsonResponse({
        'organizations': list(Organization.objects.values('id', 'name').order_by('name')),
        'cities': list(City.objects.values('id', 'name').order_by('name')),
        'manufacturers': list(Manufacturer.objects.values('id', 'name').order_by('name')),
        'statuses': list(ContractStatus.objects.filter(is_active=True).values('id', 'name', 'color').order_by('name')),
        'choices': choices,
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
