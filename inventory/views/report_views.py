# inventory/views/report_views.py
"""
Report generation views.
Handles email generation and other specialized reports based on inventory data.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect
from django.http import Http404

from ..models import Printer
from contracts.utils import generate_email_for_device

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL GENERATION
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def generate_email_from_inventory(request, pk: int):
    """
    Генерирует .eml файл для принтера из инвентаря.
    Ищет соответствующее устройство в договорах по серийному номеру.

    Интеграция между модулем inventory и contracts:
    - Берёт серийный номер из inventory.Printer
    - Ищет устройство в contracts.ContractDevice
    - Генерирует email на основе данных договора
    """
    try:
        printer = Printer.objects.get(pk=pk)
    except Printer.DoesNotExist:
        messages.error(request, 'Принтер не найден')
        return redirect('inventory:printer_list')

    if not printer.serial_number:
        messages.error(
            request,
            f'У принтера {printer.ip_address} отсутствует серийный номер. '
            f'Выполните инвентаризацию для получения серийного номера.'
        )
        return redirect('inventory:printer_list')

    try:
        return generate_email_for_device(
            serial_number=printer.serial_number,
            user_email=request.user.email or 'user@example.com'
        )
    except Http404:
        messages.error(
            request,
            f'Устройство с серийным номером {printer.serial_number} не найдено в договорах. '
            f'Добавьте его сначала в раздел "Устройства в договоре" (модуль contracts).'
        )
        return redirect('inventory:printer_list')
    except Exception as e:
        logger.error(
            f"Error generating email for printer {pk} (SN: {printer.serial_number}): {e}",
            exc_info=True
        )
        messages.error(
            request,
            f'Ошибка при генерации email: {str(e)}'
        )
        return redirect('inventory:printer_list')