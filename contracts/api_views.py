"""
API views для приложения contracts (Vue.js frontend)
"""

import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, Max, OuterRef, Subquery, Value, CharField, F
from django.db.models.functions import Concat, Cast, ExtractMonth, ExtractYear, LPad
from django.http import JsonResponse

from inventory.models import Organization

from .models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer

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
    qs = ContractDevice.objects.select_related("organization", "city", "model__manufacturer", "printer", "status")

    # Добавляем GLPI синхронизацию если приложение установлено
    if has_integrations:
        # Prefetch только последнюю синхронизацию для каждого устройства
        latest_sync_prefetch = Prefetch(
            "glpi_syncs", queryset=GLPISync.objects.order_by("-checked_at")[:1], to_attr="latest_glpi_sync"
        )
        qs = qs.prefetch_related(latest_sync_prefetch)

    # Поиск по ключевому слову (q)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(serial_number__icontains=q)
            | Q(address__icontains=q)
            | Q(model__name__icontains=q)
            | Q(comment__icontains=q)
        )

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
        multi_value = request.GET.get(f"{param_key}__in", "").strip()
        single_value = request.GET.get(param_key, "").strip()

        if multi_value:
            values = [v.strip() for v in multi_value.split("||") if v.strip()]
            if values:
                qs = qs.filter(**{f"{field_name}__in": values})
        elif single_value:
            qs = qs.filter(**{f"{field_name}__icontains": single_value})

    # Фильтр по GLPI статусу
    if has_integrations:
        glpi_status_multi = request.GET.get("glpi_status__in", "").strip()
        glpi_status_single = request.GET.get("glpi_status", "").strip()
        logger.info(
            f"[GLPI FILTER] Входящие параметры - glpi_status__in: '{glpi_status_multi}', glpi_status: '{glpi_status_single}'"
        )

        # Обрабатываем множественный выбор (__in) или одиночный
        status_labels = []
        if glpi_status_multi:
            status_labels = [v.strip() for v in glpi_status_multi.split("||") if v.strip()]
            logger.info(f"[GLPI FILTER] Множественный выбор, распознанные лейблы: {status_labels}")
        elif glpi_status_single:
            status_labels = [glpi_status_single]
            logger.info(f"[GLPI FILTER] Одиночный выбор, лейбл: {glpi_status_single}")

        if status_labels:
            logger.info(f"[GLPI FILTER] Итоговые лейблы для фильтрации: {status_labels}")

            try:
                # Маппинг лейблов в коды статусов (должны совпадать с STATUS_CHOICES в модели)
                label_to_code = {
                    "Найден (1 карточка)": "FOUND_SINGLE",
                    "Найдено несколько карточек": "FOUND_MULTIPLE",
                    "Не найден в GLPI": "NOT_FOUND",
                    "Ошибка при проверке": "ERROR",
                }
                status_values = [label_to_code.get(label, label) for label in status_labels]
                logger.info(f"[GLPI FILTER] Коды статусов для фильтрации: {status_values}")

                from integrations.models import GLPISync

                # Получаем ID устройств, у которых последняя синхронизация имеет нужный статус
                # Один запрос через Subquery
                latest_sync_subquery = (
                    GLPISync.objects.filter(contract_device_id=OuterRef("contract_device_id"))
                    .order_by("-checked_at")
                    .values("checked_at")[:1]
                )

                device_ids = set(
                    GLPISync.objects.filter(status__in=status_values)
                    .annotate(latest_check_overall=Subquery(latest_sync_subquery))
                    .filter(checked_at=F("latest_check_overall"))
                    .values_list("contract_device_id", flat=True)
                    .distinct()
                )

                logger.debug(f"[GLPI FILTER] Итоговый список device_ids для фильтрации: {device_ids}")

                if device_ids:
                    qs = qs.filter(id__in=device_ids)
                else:
                    # Если нет устройств с таким статусом, вернуть пустой queryset
                    logger.warning(
                        f"[GLPI FILTER] Не найдено устройств с статусами {status_values}, возвращаем пустой queryset"
                    )
                    qs = qs.none()

            except Exception as e:
                logger.error(f"[GLPI FILTER] ОШИБКА при фильтрации GLPI: {type(e).__name__}: {str(e)}")
                import traceback

                logger.error(f"[GLPI FILTER] Traceback:\n{traceback.format_exc()}")
                # Не применяем фильтр при ошибке - показываем все устройства
                pass

        # Фильтр по состоянию в GLPI (glpi_state_name)
        glpi_state_multi = request.GET.get("glpi_state__in", "").strip()
        glpi_state_single = request.GET.get("glpi_state", "").strip()

        state_names = []
        if glpi_state_multi:
            state_names = [v.strip() for v in glpi_state_multi.split("||") if v.strip()]
        elif glpi_state_single:
            state_names = [glpi_state_single]

        if state_names:
            try:
                from integrations.models import GLPISync

                # Получаем ID устройств, у которых последняя синхронизация имеет нужное состояние
                # Один запрос через Subquery
                latest_sync_subquery = (
                    GLPISync.objects.filter(contract_device_id=OuterRef("contract_device_id"))
                    .order_by("-checked_at")
                    .values("checked_at")[:1]
                )

                device_ids = set(
                    GLPISync.objects.filter(glpi_state_name__in=state_names)
                    .annotate(latest_check_overall=Subquery(latest_sync_subquery))
                    .filter(checked_at=F("latest_check_overall"))
                    .values_list("contract_device_id", flat=True)
                    .distinct()
                )

                if device_ids:
                    qs = qs.filter(id__in=device_ids)
                else:
                    qs = qs.none()

            except Exception as e:
                logger.error(f"[GLPI STATE FILTER] ОШИБКА: {type(e).__name__}: {str(e)}")
                pass

    # Фильтр по месяцу обслуживания
    service_multi = request.GET.get("service_month__in", "").strip()
    service_single = request.GET.get("service_month", "").strip()

    if service_multi:
        values = [v.strip() for v in service_multi.split("||") if v.strip()]
        if values:
            q_objects = []
            for filter_val in values:
                if "." in filter_val:
                    try:
                        month, year = filter_val.split(".")
                        month, year = int(month), int(year)
                        q_objects.append(Q(service_start_month__year=year, service_start_month__month=month))
                    except (ValueError, TypeError):
                        pass
                elif "-" in filter_val and len(filter_val) == 7:  # YYYY-MM
                    try:
                        year, month = filter_val.split("-")
                        month, year = int(month), int(year)
                        q_objects.append(Q(service_start_month__year=year, service_start_month__month=month))
                    except (ValueError, TypeError):
                        pass

            if q_objects:
                combined_q = q_objects[0]
                for q_obj in q_objects[1:]:
                    combined_q |= q_obj
                qs = qs.filter(combined_q)
    elif service_single:
        filter_val = service_single
        if "." in filter_val:
            try:
                month, year = filter_val.split(".")
                month, year = int(month), int(year)
                qs = qs.filter(service_start_month__year=year, service_start_month__month=month)
            except (ValueError, TypeError):
                pass

    # Фильтр по автору заявки Okdesk
    okdesk_author_filter = (
        request.GET.get("okdesk_author__in", "").strip() or request.GET.get("okdesk_author", "").strip()
    )
    if okdesk_author_filter:
        try:
            from integrations.models import OkdeskIssue

            author_names = [v.strip() for v in okdesk_author_filter.split("||") if v.strip()]
            _author_serials = set()
            for issue in (
                OkdeskIssue.objects.exclude(status_name="Закрыта")
                .filter(author_name__in=author_names)
                .only("serial_numbers")
            ):
                issue_serials = {s.strip() for s in issue.serial_numbers.split(",") if s.strip()}
                _author_serials.update(issue_serials)

            if _author_serials:
                qs = qs.filter(serial_number__in=_author_serials)
            else:
                qs = qs.none()
        except ImportError:
            pass

    # Фильтр по активным/просроченным заявкам Okdesk
    okdesk_active_filter = (
        request.GET.get("okdesk_active__in", "").strip() or request.GET.get("okdesk_active", "").strip()
    )
    okdesk_overdue_filter = (
        request.GET.get("okdesk_overdue__in", "").strip() or request.GET.get("okdesk_overdue", "").strip()
    )

    if okdesk_active_filter or okdesk_overdue_filter:
        try:
            from integrations.models import OkdeskIssue

            # Собираем серийники с активными/просроченными заявками
            _active_serials = set()
            _overdue_serials = set()
            for issue in OkdeskIssue.objects.exclude(status_name="Закрыта").only("serial_numbers", "is_overdue"):
                issue_serials = {s.strip() for s in issue.serial_numbers.split(",") if s.strip()}
                _active_serials.update(issue_serials)
                if issue.is_overdue:
                    _overdue_serials.update(issue_serials)

            if okdesk_active_filter:
                want_active = "Да" in okdesk_active_filter
                if want_active:
                    qs = qs.filter(serial_number__in=_active_serials)
                else:
                    qs = qs.exclude(serial_number__in=_active_serials)

            if okdesk_overdue_filter:
                want_overdue = "Да" in okdesk_overdue_filter
                if want_overdue:
                    qs = qs.filter(serial_number__in=_overdue_serials)
                else:
                    qs = qs.exclude(serial_number__in=_overdue_serials)
        except ImportError:
            pass

    # Пагинация
    page_number = request.GET.get("page", 1)
    per_page = int(request.GET.get("per_page", 50))

    # Ограничение per_page разумными значениями
    if per_page not in [25, 50, 100, 200, 500, 1000]:
        per_page = 50

    total_count = qs.count()
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(page_number)

    # Предзагрузка данных Okdesk по серийным номерам для текущей страницы
    page_serials = {d.serial_number for d in page if d.serial_number}
    serials_with_active_issues = set()
    serials_with_overdue_issues = set()
    serial_to_okdesk_author = {}

    if page_serials:
        try:
            from integrations.models import OkdeskIssue

            # Незакрытые заявки
            active_issues = OkdeskIssue.objects.exclude(status_name="Закрыта")
            for issue in active_issues.only("serial_numbers", "is_overdue", "author_name", "created_at"):
                issue_serials = {s.strip() for s in issue.serial_numbers.split(",") if s.strip()}
                matched = issue_serials & page_serials
                if matched:
                    serials_with_active_issues.update(matched)
                    if issue.is_overdue:
                        serials_with_overdue_issues.update(matched)
                    # Сохраняем автора последней активной заявки
                    if issue.author_name:
                        for s in matched:
                            existing = serial_to_okdesk_author.get(s)
                            if not existing or (issue.created_at and existing[1] and issue.created_at > existing[1]):
                                serial_to_okdesk_author[s] = (issue.author_name, issue.created_at)
        except ImportError:
            pass

    # Сериализация данных
    devices = []
    for device in page:
        device_data = {
            "id": device.id,
            "organization": device.organization.name,
            "organization_id": device.organization.id,
            "city": device.city.name,
            "city_id": device.city.id,
            "address": device.address,
            "room_number": device.room_number,
            "manufacturer": device.model.manufacturer.name,
            "manufacturer_id": device.model.manufacturer.id,
            "model": device.model.name,
            "model_id": device.model.id,
            "has_network_port": device.model.has_network_port,
            "serial_number": device.serial_number,
            "status": device.status.name,
            "status_id": device.status.id,
            "status_color": device.status.color,
            "service_start_month": device.service_start_month_display,
            "service_start_month_iso": (
                device.service_start_month.strftime("%Y-%m") if device.service_start_month else None
            ),
            "comment": device.comment,
            "printer_id": device.printer.id if device.printer else None,
            "created_at": device.created_at.isoformat(),
            "updated_at": device.updated_at.isoformat(),
            "has_active_issues": device.serial_number in serials_with_active_issues,
            "has_overdue_issues": device.serial_number in serials_with_overdue_issues,
            "okdesk_author_name": serial_to_okdesk_author.get(device.serial_number, (None,))[0] or "",
        }

        # Добавляем данные GLPI синхронизации если доступно
        if has_integrations and hasattr(device, "latest_glpi_sync") and device.latest_glpi_sync:
            sync = device.latest_glpi_sync[0]
            device_data.update(
                {
                    "glpi_status": sync.status,
                    "glpi_status_display": sync.get_status_display(),
                    "glpi_count": sync.glpi_count,
                    "glpi_ids": sync.glpi_ids,
                    "glpi_checked_at": sync.checked_at.isoformat(),
                    "glpi_is_synced": sync.is_synced,
                    "glpi_has_conflict": sync.has_conflict,
                    "glpi_state_id": sync.glpi_state_id,
                    "glpi_state_name": sync.glpi_state_name,
                }
            )
        else:
            device_data.update(
                {
                    "glpi_status": None,
                    "glpi_status_display": None,
                    "glpi_count": 0,
                    "glpi_ids": [],
                    "glpi_checked_at": None,
                    "glpi_is_synced": False,
                    "glpi_has_conflict": False,
                    "glpi_state_id": None,
                    "glpi_state_name": "",
                }
            )

        devices.append(device_data)

    return JsonResponse(
        {
            "devices": devices,
            "pagination": {
                "total_count": total_count,
                "total_pages": paginator.num_pages,
                "current_page": page.number,
                "per_page": per_page,
                "has_next": page.has_next(),
                "has_previous": page.has_previous(),
            },
        }
    )


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
def api_contract_filters(request):
    """
    API для получения данных для фильтров (списки организаций, городов, и т.д.)
    Кэшируется на 5 минут для ускорения загрузки страницы.
    """
    import hashlib
    import json
    from django.core.cache import cache

    # Создаём ключ кэша на основе GET-параметров (для кросс-фильтрации)
    cache_key_data = sorted(request.GET.items())
    cache_key_hash = hashlib.md5(json.dumps(cache_key_data).encode()).hexdigest()
    cache_key = f"contract_filters:{cache_key_hash}"

    # Проверяем кэш
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return JsonResponse(cached_result)

    # Проверяем доступность integrations приложения
    try:
        from integrations.models import GLPISync

        has_integrations = True
    except ImportError:
        has_integrations = False

    # Базовый queryset
    devices = ContractDevice.objects.select_related("organization", "city", "model__manufacturer", "status")

    # Добавляем GLPI синхронизацию если приложение установлено
    if has_integrations:
        # Prefetch только последнюю синхронизацию для каждого устройства
        latest_sync_prefetch = Prefetch(
            "glpi_syncs", queryset=GLPISync.objects.order_by("-checked_at")[:1], to_attr="latest_glpi_sync"
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
        multi_value = request.GET.get(f"{param_key}__in", "").strip()
        single_value = request.GET.get(param_key, "").strip()

        if multi_value:
            values = [v.strip() for v in multi_value.split("||") if v.strip()]
            if values:
                devices = devices.filter(**{f"{field_name}__in": values})
        elif single_value:
            devices = devices.filter(**{f"{field_name}__icontains": single_value})

    # Фильтр по GLPI статусу (для кросс-фильтрации)
    if has_integrations:
        glpi_status_multi = request.GET.get("glpi_status__in", "").strip()
        glpi_status_single = request.GET.get("glpi_status", "").strip()

        status_labels = []
        if glpi_status_multi:
            status_labels = [v.strip() for v in glpi_status_multi.split("||") if v.strip()]
        elif glpi_status_single:
            status_labels = [glpi_status_single]

        if status_labels:
            # Маппинг лейблов в коды статусов
            label_to_code = {
                "Найден (1 карточка)": "FOUND_SINGLE",
                "Найдено несколько карточек": "FOUND_MULTIPLE",
                "Не найден в GLPI": "NOT_FOUND",
                "Ошибка при проверке": "ERROR",
            }
            status_values = [label_to_code.get(label, label) for label in status_labels]

            # Оптимизация: один запрос вместо N+1 через Subquery
            latest_sync_subquery = (
                GLPISync.objects.filter(contract_device_id=OuterRef("contract_device_id"))
                .order_by("-checked_at")
                .values("checked_at")[:1]
            )

            device_ids = set(
                GLPISync.objects.filter(status__in=status_values)
                .annotate(latest_check_overall=Subquery(latest_sync_subquery))
                .filter(checked_at=F("latest_check_overall"))
                .values_list("contract_device_id", flat=True)
                .distinct()
            )

            if device_ids:
                devices = devices.filter(id__in=device_ids)
            else:
                devices = devices.none()

        # Фильтр по состоянию в GLPI (для кросс-фильтрации)
        glpi_state_multi = request.GET.get("glpi_state__in", "").strip()
        glpi_state_single = request.GET.get("glpi_state", "").strip()

        state_names = []
        if glpi_state_multi:
            state_names = [v.strip() for v in glpi_state_multi.split("||") if v.strip()]
        elif glpi_state_single:
            state_names = [glpi_state_single]

        if state_names:
            from django.db.models import Max

            # Оптимизация: один запрос вместо N+1 через Subquery
            latest_sync_subquery = (
                GLPISync.objects.filter(contract_device_id=OuterRef("contract_device_id"))
                .order_by("-checked_at")
                .values("checked_at")[:1]
            )

            device_ids = set(
                GLPISync.objects.filter(glpi_state_name__in=state_names)
                .annotate(latest_check_overall=Subquery(latest_sync_subquery))
                .filter(checked_at=F("latest_check_overall"))
                .values_list("contract_device_id", flat=True)
                .distinct()
            )

            if device_ids:
                devices = devices.filter(id__in=device_ids)
            else:
                devices = devices.none()

    # Фильтр по месяцу обслуживания
    service_multi = request.GET.get("service_month__in", "").strip()
    service_single = request.GET.get("service_month", "").strip()

    if service_multi:
        values = [v.strip() for v in service_multi.split("||") if v.strip()]
        if values:
            q_objects = []
            for filter_val in values:
                if "." in filter_val:
                    try:
                        month, year = filter_val.split(".")
                        month, year = int(month), int(year)
                        q_objects.append(Q(service_start_month__year=year, service_start_month__month=month))
                    except (ValueError, TypeError):
                        pass
                elif "-" in filter_val and len(filter_val) == 7:
                    try:
                        year, month = filter_val.split("-")
                        month, year = int(month), int(year)
                        q_objects.append(Q(service_start_month__year=year, service_start_month__month=month))
                    except (ValueError, TypeError):
                        pass

            if q_objects:
                combined_q = q_objects[0]
                for q_obj in q_objects[1:]:
                    combined_q |= q_obj
                devices = devices.filter(combined_q)
    elif service_single:
        filter_val = service_single
        if "." in filter_val:
            try:
                month, year = filter_val.split(".")
                month, year = int(month), int(year)
                devices = devices.filter(service_start_month__year=year, service_start_month__month=month)
            except (ValueError, TypeError):
                pass

    # Уникальные значения для фильтров (с учетом примененных фильтров)
    # Агрегация в Postgres вместо Python-циклов
    choices = {
        "org": sorted(
            devices.filter(organization__isnull=False).values_list("organization__name", flat=True).distinct()
        ),
        "city": sorted(devices.filter(city__isnull=False).values_list("city__name", flat=True).distinct()),
        "address": sorted(devices.exclude(address="").values_list("address", flat=True).distinct()),
        "room": sorted(devices.exclude(room_number="").values_list("room_number", flat=True).distinct()),
        "mfr": sorted(
            devices.filter(model__manufacturer__isnull=False)
            .values_list("model__manufacturer__name", flat=True)
            .distinct()
        ),
        "model": sorted(devices.filter(model__isnull=False).values_list("model__name", flat=True).distinct()),
        "serial": sorted(devices.exclude(serial_number="").values_list("serial_number", flat=True).distinct()),
        "status": sorted(devices.filter(status__isnull=False).values_list("status__name", flat=True).distinct()),
        "service_month": sorted(
            devices.filter(service_start_month__isnull=False)
            .annotate(
                month_display=Concat(
                    LPad(
                        Cast(ExtractMonth("service_start_month"), output_field=CharField()),
                        2,
                        Value("0"),
                    ),
                    Value("."),
                    Cast(ExtractYear("service_start_month"), output_field=CharField()),
                    output_field=CharField(),
                )
            )
            .values_list("month_display", flat=True)
            .distinct()
        ),
        "comment": sorted(devices.exclude(comment="").values_list("comment", flat=True).distinct()),
    }

    # Добавляем GLPI статусы - ТОЛЬКО те которые реально есть в данных (как все остальные столбцы)
    if has_integrations:
        # Маппинг кодов в лейблы (как в api_contract_devices)
        code_to_label = {
            "FOUND_SINGLE": "Найден (1 карточка)",
            "FOUND_MULTIPLE": "Найдено несколько карточек",
            "NOT_FOUND": "Не найден в GLPI",
            "ERROR": "Ошибка при проверке",
        }

        # Оптимизация: используем distinct() с order_by для получения последних записей (Postgres window function)
        device_ids = list(devices.values_list("id", flat=True))

        if device_ids:
            # Получаем последние синхронизации через distinct on (Postgres-specific)
            latest_syncs = (
                GLPISync.objects.filter(contract_device_id__in=device_ids)
                .order_by("contract_device_id", "-checked_at")
                .distinct("contract_device_id")
            )

            # Собираем уникальные статусы
            unique_statuses = set(latest_syncs.exclude(status="").values_list("status", flat=True))
            choices["glpi"] = sorted(
                [code_to_label.get(status) for status in unique_statuses if code_to_label.get(status)]
            )

            # Собираем уникальные состояния из GLPI
            unique_states = set(latest_syncs.exclude(glpi_state_name="").values_list("glpi_state_name", flat=True))
            choices["glpi_state"] = sorted(unique_states)
        else:
            choices["glpi"] = []
            choices["glpi_state"] = []
    else:
        choices["glpi"] = []
        choices["glpi_state"] = []

    # Okdesk: варианты для фильтров
    try:
        from integrations.models import OkdeskIssue

        okdesk_authors = set(
            OkdeskIssue.objects.exclude(status_name="Закрыта")
            .exclude(author_name="")
            .values_list("author_name", flat=True)
        )
        choices["okdesk_author"] = sorted(okdesk_authors)
    except ImportError:
        choices["okdesk_author"] = []
    choices["okdesk_active"] = ["Да", "Нет"]
    choices["okdesk_overdue"] = ["Да", "Нет"]

    result = {
        "organizations": list(Organization.objects.values("id", "name").order_by("name")),
        "cities": list(City.objects.values("id", "name").order_by("name")),
        "manufacturers": list(Manufacturer.objects.values("id", "name").order_by("name")),
        "statuses": list(ContractStatus.objects.filter(is_active=True).values("id", "name", "color").order_by("name")),
        "choices": choices,
    }

    # Кэшируем результат на 5 минут (300 секунд)
    cache.set(cache_key, result, 300)

    return JsonResponse(result)


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
def api_device_models_by_manufacturer(request):
    """
    API для получения моделей по производителю
    """
    manufacturer_id = request.GET.get("manufacturer_id")
    if not manufacturer_id:
        return JsonResponse({"models": []})

    models = (
        DeviceModel.objects.filter(manufacturer_id=manufacturer_id).values("id", "name", "device_type").order_by("name")
    )

    return JsonResponse({"models": list(models)})
