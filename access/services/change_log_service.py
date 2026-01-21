"""
Сервис для логирования изменений сущностей.
Поддерживает логирование создания, изменения и удаления любых моделей.
"""
import logging
from typing import Any, Dict, Optional, List
from django.contrib.contenttypes.models import ContentType
from django.db import models

from ..models import EntityChangeLog

logger = logging.getLogger(__name__)


class ChangeLogService:
    """
    Сервис для создания записей в логе изменений.

    Использование:
        # В view при создании
        ChangeLogService.log_create(instance, user, request)

        # В view при изменении (нужно сохранить старые значения ДО save)
        old_values = ChangeLogService.get_model_data(instance)
        instance.field = new_value
        instance.save()
        ChangeLogService.log_update(instance, user, request, old_values)

        # В view при удалении
        ChangeLogService.log_delete(instance, user, request)
    """

    # Поля, которые нужно игнорировать при логировании
    IGNORED_FIELDS = {
        'id', 'pk', 'created_at', 'updated_at', 'last_updated',
        'password', 'web_password',  # Чувствительные данные
    }

    # Маппинг verbose_name для моделей (если нужно переопределить)
    MODEL_VERBOSE_NAMES = {}

    @classmethod
    def get_ip_from_request(cls, request) -> Optional[str]:
        """Извлекает IP адрес из request"""
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @classmethod
    def get_user_agent(cls, request) -> str:
        """Извлекает User Agent из request"""
        if not request:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')[:500]

    @classmethod
    def get_field_verbose_name(cls, model: type, field_name: str) -> str:
        """Получает человекочитаемое название поля"""
        try:
            field = model._meta.get_field(field_name)
            return field.verbose_name or field_name
        except Exception:
            return field_name

    @classmethod
    def serialize_value(cls, value: Any) -> Any:
        """Сериализует значение для хранения в JSON"""
        if value is None:
            return None
        if isinstance(value, models.Model):
            return str(value)
        if hasattr(value, 'isoformat'):  # datetime, date
            return value.isoformat()
        if isinstance(value, (list, tuple)):
            return [cls.serialize_value(v) for v in value]
        return str(value) if not isinstance(value, (str, int, float, bool)) else value

    @classmethod
    def get_model_data(cls, instance: models.Model, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Получает данные модели для сравнения.

        Args:
            instance: Экземпляр модели
            fields: Список полей для извлечения (если None - все поля)

        Returns:
            Словарь {field_name: value}
        """
        data = {}
        model = instance.__class__

        for field in model._meta.get_fields():
            # Пропускаем обратные связи и M2M
            if field.is_relation and (field.one_to_many or field.many_to_many):
                continue

            field_name = field.name

            # Пропускаем игнорируемые поля
            if field_name in cls.IGNORED_FIELDS:
                continue

            # Если указан список полей - фильтруем
            if fields and field_name not in fields:
                continue

            try:
                value = getattr(instance, field_name, None)
                data[field_name] = cls.serialize_value(value)
            except Exception as e:
                logger.debug(f"Не удалось получить значение поля {field_name}: {e}")

        return data

    @classmethod
    def compute_changes(
        cls,
        model: type,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any]
    ) -> Dict[str, Dict]:
        """
        Вычисляет разницу между старыми и новыми данными.

        Returns:
            Словарь {field_name: {'old': old_value, 'new': new_value, 'label': verbose_name}}
        """
        changes = {}
        all_fields = set(old_data.keys()) | set(new_data.keys())

        for field_name in all_fields:
            old_val = old_data.get(field_name)
            new_val = new_data.get(field_name)

            # Сравниваем с учетом None и пустых строк
            old_normalized = old_val if old_val not in (None, '') else None
            new_normalized = new_val if new_val not in (None, '') else None

            if old_normalized != new_normalized:
                changes[field_name] = {
                    'old': old_val,
                    'new': new_val,
                    'label': cls.get_field_verbose_name(model, field_name),
                }

        return changes

    @classmethod
    def log_create(
        cls,
        instance: models.Model,
        user=None,
        request=None,
    ) -> EntityChangeLog:
        """
        Логирует создание объекта.
        """
        model = instance.__class__
        content_type = ContentType.objects.get_for_model(model)

        # Получаем все данные как "новые"
        new_data = cls.get_model_data(instance)
        changes = {
            field: {'old': None, 'new': value, 'label': cls.get_field_verbose_name(model, field)}
            for field, value in new_data.items()
            if value not in (None, '', [])  # Не логируем пустые значения при создании
        }

        return EntityChangeLog.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            action='create',
            user=user,
            changes=changes,
            object_repr=str(instance)[:500],
            ip_address=cls.get_ip_from_request(request),
            user_agent=cls.get_user_agent(request),
        )

    @classmethod
    def log_update(
        cls,
        instance: models.Model,
        user=None,
        request=None,
        old_data: Dict[str, Any] = None,
    ) -> Optional[EntityChangeLog]:
        """
        Логирует изменение объекта.

        Args:
            instance: Обновлённый экземпляр модели (ПОСЛЕ save)
            user: Пользователь, выполнивший изменение
            request: HTTP request (для IP и User-Agent)
            old_data: Данные ДО изменения (от get_model_data)

        Returns:
            EntityChangeLog или None если изменений нет
        """
        if old_data is None:
            logger.warning("log_update вызван без old_data - изменения не будут записаны")
            return None

        model = instance.__class__
        content_type = ContentType.objects.get_for_model(model)

        # Получаем новые данные
        new_data = cls.get_model_data(instance)

        # Вычисляем изменения
        changes = cls.compute_changes(model, old_data, new_data)

        if not changes:
            # Нет изменений - не создаём запись
            return None

        return EntityChangeLog.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            action='update',
            user=user,
            changes=changes,
            object_repr=str(instance)[:500],
            ip_address=cls.get_ip_from_request(request),
            user_agent=cls.get_user_agent(request),
        )

    @classmethod
    def log_delete(
        cls,
        instance: models.Model,
        user=None,
        request=None,
    ) -> EntityChangeLog:
        """
        Логирует удаление объекта.
        Важно: вызывать ДО delete()!
        """
        model = instance.__class__
        content_type = ContentType.objects.get_for_model(model)

        # Сохраняем все данные как "старые"
        old_data = cls.get_model_data(instance)
        changes = {
            field: {'old': value, 'new': None, 'label': cls.get_field_verbose_name(model, field)}
            for field, value in old_data.items()
            if value not in (None, '', [])  # Не логируем пустые значения
        }

        return EntityChangeLog.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            action='delete',
            user=user,
            changes=changes,
            object_repr=str(instance)[:500],
            ip_address=cls.get_ip_from_request(request),
            user_agent=cls.get_user_agent(request),
        )

    @classmethod
    def get_history(
        cls,
        instance: models.Model = None,
        model: type = None,
        object_id: int = None,
        limit: int = 50
    ):
        """
        Получает историю изменений для объекта или модели.

        Args:
            instance: Экземпляр модели
            model: Класс модели (альтернатива instance)
            object_id: ID объекта (используется с model)
            limit: Максимальное количество записей
        """
        if instance:
            model = instance.__class__
            object_id = instance.pk

        content_type = ContentType.objects.get_for_model(model)

        qs = EntityChangeLog.objects.filter(content_type=content_type)

        if object_id:
            qs = qs.filter(object_id=object_id)

        return qs.select_related('user')[:limit]
