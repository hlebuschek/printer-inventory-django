from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from ..models import MonthlyReport, CounterChangeLog, BulkChangeLog

User = get_user_model()


class AuditService:
    """
    Сервис для записи истории изменений
    """

    @staticmethod
    def log_counter_change(
            monthly_report: MonthlyReport,
            user: User,
            field_name: str,
            old_value: Any,
            new_value: Any,
            request=None,
            change_source='manual',
            comment=''
    ):
        """
        Записывает изменение одного поля счетчика
        """
        # Извлекаем метаданные из request
        ip_address = None
        user_agent = ''

        if request:
            # Получаем IP из заголовков (учитывая proxy)
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # ограничиваем длину

        # Приводим значения к int или None
        def safe_int(value):
            if value in (None, ''):
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        old_int = safe_int(old_value)
        new_int = safe_int(new_value)

        # Не логируем если значения одинаковые
        if old_int == new_int:
            return None

        return CounterChangeLog.objects.create(
            monthly_report=monthly_report,
            user=user,
            field_name=field_name,
            old_value=old_int,
            new_value=new_int,
            ip_address=ip_address,
            user_agent=user_agent,
            change_source=change_source,
            comment=comment,
        )

    @staticmethod
    def log_multiple_changes(
            monthly_report: MonthlyReport,
            user: User,
            changes: Dict[str, tuple],  # {field_name: (old_value, new_value)}
            request=None,
            change_source='manual',
            comment=''
    ):
        """
        Записывает несколько изменений одновременно (batch)
        """
        logs = []

        with transaction.atomic():
            for field_name, (old_value, new_value) in changes.items():
                log_entry = AuditService.log_counter_change(
                    monthly_report=monthly_report,
                    user=user,
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    request=request,
                    change_source=change_source,
                    comment=comment
                )
                if log_entry:
                    logs.append(log_entry)

        return logs

    @staticmethod
    def start_bulk_operation(
            user: User,
            operation_type: str,
            operation_params: Dict = None,
            request=None,
            month=None
    ) -> BulkChangeLog:
        """
        Начинает запись массовой операции
        """
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

        return BulkChangeLog.objects.create(
            user=user,
            operation_type=operation_type,
            operation_params=operation_params or {},
            started_at=timezone.now(),
            ip_address=ip_address,
            month=month,
        )

    @staticmethod
    def finish_bulk_operation(
            bulk_log: BulkChangeLog,
            records_affected: int,
            fields_changed: list,
            success: bool = True,
            error_message: str = ''
    ):
        """
        Завершает запись массовой операции
        """
        bulk_log.finished_at = timezone.now()
        bulk_log.records_affected = records_affected
        bulk_log.fields_changed = fields_changed
        bulk_log.success = success
        bulk_log.error_message = error_message
        bulk_log.save()

    @staticmethod
    def get_change_history(monthly_report: MonthlyReport, limit: int = 50):
        """
        Получает историю изменений для записи
        """
        return (
            CounterChangeLog.objects
            .filter(monthly_report=monthly_report)
            .select_related('user')
            .order_by('-timestamp')[:limit]
        )

    @staticmethod
    def get_user_activity(user: User, days: int = 30):
        """
        Получает активность пользователя за N дней
        """
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)

        return {
            'changes': CounterChangeLog.objects.filter(
                user=user,
                timestamp__gte=since
            ).count(),
            'bulk_operations': BulkChangeLog.objects.filter(
                user=user,
                started_at__gte=since
            ).count(),
            'recent_changes': CounterChangeLog.objects.filter(
                user=user,
                timestamp__gte=since
            ).select_related('monthly_report')[:10]
        }

    @staticmethod
    def revert_change(change_log: CounterChangeLog, user: User, request=None):
        """
        Откатывает изменение (устанавливает старое значение)
        """
        if change_log.old_value is None:
            raise ValueError("Невозможно откатить изменение: старое значение неизвестно")

        monthly_report = change_log.monthly_report
        field_name = change_log.field_name

        # Получаем текущее значение
        current_value = getattr(monthly_report, field_name)

        # Устанавливаем старое значение
        setattr(monthly_report, field_name, change_log.old_value)
        monthly_report.save(update_fields=[field_name])

        # Логируем откат
        AuditService.log_counter_change(
            monthly_report=monthly_report,
            user=user,
            field_name=field_name,
            old_value=current_value,
            new_value=change_log.old_value,
            request=request,
            change_source='manual',
            comment=f'Откат изменения #{change_log.id}'
        )

        # Пересчитываем группу
        from ..services import recompute_group
        recompute_group(
            monthly_report.month,
            monthly_report.serial_number,
            monthly_report.inventory_number
        )

        return True