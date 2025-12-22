"""
API endpoints для интеграций.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import ensure_csrf_cookie

from contracts.models import ContractDevice
from .glpi.services import (
    check_device_in_glpi,
    check_multiple_devices_in_glpi,
    get_last_sync_for_device,
    get_devices_with_conflicts,
    get_devices_not_in_glpi
)

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
@permission_required('contracts.view_contractdevice', raise_exception=True)
@ensure_csrf_cookie
def check_device_glpi(request, device_id):
    """
    Проверяет одно устройство в GLPI.

    POST /integrations/glpi/check-device/<device_id>/
    """
    try:
        device = ContractDevice.objects.get(id=device_id)
    except ContractDevice.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Устройство не найдено'
        }, status=404)

    # Принудительная проверка или использовать кэш?
    force_check = request.POST.get('force', 'false').lower() == 'true'

    try:
        sync = check_device_in_glpi(device, user=request.user, force_check=force_check)

        return JsonResponse({
            'ok': True,
            'sync': {
                'id': sync.id,
                'status': sync.status,
                'status_display': sync.get_status_display(),
                'glpi_ids': sync.glpi_ids,
                'glpi_count': sync.glpi_count,
                'is_synced': sync.is_synced,
                'has_conflict': sync.has_conflict,
                'error_message': sync.error_message,
                'checked_at': sync.checked_at.isoformat(),
                'checked_by': sync.checked_by.username if sync.checked_by else None,
            }
        })

    except Exception as e:
        logger.exception(f"Ошибка при проверке устройства {device_id} в GLPI: {e}")
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@login_required
@permission_required('contracts.view_contractdevice', raise_exception=True)
@ensure_csrf_cookie
def check_multiple_devices_glpi(request):
    """
    Проверяет несколько устройств в GLPI.

    POST /integrations/glpi/check-multiple/
    Body: {"device_ids": [1, 2, 3]}
    """
    import json

    try:
        data = json.loads(request.body)
        device_ids = data.get('device_ids', [])

        if not device_ids:
            return JsonResponse({
                'ok': False,
                'error': 'Не указаны ID устройств'
            }, status=400)

        # Ограничение на количество
        if len(device_ids) > 100:
            return JsonResponse({
                'ok': False,
                'error': 'Максимум 100 устройств за один запрос'
            }, status=400)

        stats = check_multiple_devices_in_glpi(device_ids, user=request.user)

        return JsonResponse({
            'ok': True,
            'stats': stats
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'ok': False,
            'error': 'Неверный формат JSON'
        }, status=400)
    except Exception as e:
        logger.exception(f"Ошибка при массовой проверке устройств в GLPI: {e}")
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
@login_required
@permission_required('contracts.view_contractdevice', raise_exception=True)
def get_device_sync_status(request, device_id):
    """
    Получает статус последней синхронизации для устройства.

    GET /integrations/glpi/sync-status/<device_id>/
    """
    try:
        device = ContractDevice.objects.get(id=device_id)
    except ContractDevice.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Устройство не найдено'
        }, status=404)

    sync = get_last_sync_for_device(device)

    if not sync:
        return JsonResponse({
            'ok': True,
            'sync': None,
            'message': 'Устройство ещё не проверялось в GLPI'
        })

    return JsonResponse({
        'ok': True,
        'sync': {
            'id': sync.id,
            'status': sync.status,
            'status_display': sync.get_status_display(),
            'glpi_ids': sync.glpi_ids,
            'glpi_count': sync.glpi_count,
            'is_synced': sync.is_synced,
            'has_conflict': sync.has_conflict,
            'error_message': sync.error_message,
            'checked_at': sync.checked_at.isoformat(),
            'checked_by': sync.checked_by.username if sync.checked_by else None,
        }
    })


@require_http_methods(["GET"])
@login_required
@permission_required('contracts.view_contractdevice', raise_exception=True)
def get_glpi_conflicts(request):
    """
    Получает список устройств с конфликтами в GLPI (найдено несколько карточек).

    GET /integrations/glpi/conflicts/
    """
    devices = get_devices_with_conflicts()

    results = []
    for device in devices:
        sync = get_last_sync_for_device(device)
        results.append({
            'device_id': device.id,
            'serial_number': device.serial_number,
            'model': str(device.model),
            'organization': device.organization.name,
            'glpi_count': sync.glpi_count if sync else 0,
            'glpi_ids': sync.glpi_ids if sync else [],
            'checked_at': sync.checked_at.isoformat() if sync else None,
        })

    return JsonResponse({
        'ok': True,
        'count': len(results),
        'devices': results
    })


@require_http_methods(["GET"])
@login_required
@permission_required('contracts.view_contractdevice', raise_exception=True)
def get_devices_not_in_glpi_view(request):
    """
    Получает список устройств, не найденных в GLPI.

    GET /integrations/glpi/not-found/
    """
    devices = get_devices_not_in_glpi()

    results = []
    for device in devices:
        sync = get_last_sync_for_device(device)
        results.append({
            'device_id': device.id,
            'serial_number': device.serial_number,
            'model': str(device.model),
            'organization': device.organization.name,
            'checked_at': sync.checked_at.isoformat() if sync else None,
        })

    return JsonResponse({
        'ok': True,
        'count': len(results),
        'devices': results
    })
