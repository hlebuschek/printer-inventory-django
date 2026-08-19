# integrations/api_docs_decorators.py
"""
OpenAPI декораторы для integrations API views.

Порядок применения декораторов к функциям views:
@login_required → @api_*_schema → @permission_required → @require_GET/@require_http_methods
"""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.fields import BooleanField, CharField, IntegerField, ListField

# Импорт request serializers
from .serializers import (
    CheckDeviceGLPIRequestSerializer,
    CheckMultipleDevicesGLPIRequestSerializer,
    CreateServiceRequestSerializer,
    PostCommentRequestSerializer,
    SyncNowRequestSerializer,
)

# ──────────────────────────────────────────────────────────────────────────────
# RESPONSE SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

GLPI_SYNC_SCHEMA = inline_serializer(
    name="GLPISync",
    fields={
        "id": IntegerField(),
        "status": CharField(),
        "status_display": CharField(),
        "glpi_ids": ListField(child=IntegerField(), allow_null=True),
        "glpi_count": IntegerField(allow_null=True),
        "is_synced": BooleanField(),
        "has_conflict": BooleanField(),
        "glpi_state_id": IntegerField(allow_null=True),
        "glpi_state_name": CharField(allow_null=True),
        "error_message": CharField(allow_null=True),
        "checked_at": CharField(),
        "checked_by": CharField(allow_null=True),
    },
)

GLPI_DEVICE_CONFLICT_SCHEMA = inline_serializer(
    name="GLPIDeviceConflict",
    fields={
        "device_id": IntegerField(),
        "serial_number": CharField(allow_null=True),
        "model": CharField(),
        "organization": CharField(),
        "glpi_count": IntegerField(),
        "glpi_ids": ListField(child=IntegerField(), allow_null=True),
        "checked_at": CharField(allow_null=True),
    },
)

GLPI_DEVICE_NOT_FOUND_SCHEMA = inline_serializer(
    name="GLPIDeviceNotFound",
    fields={
        "device_id": IntegerField(),
        "serial_number": CharField(allow_null=True),
        "model": CharField(),
        "organization": CharField(),
        "checked_at": CharField(allow_null=True),
    },
)

DEVICE_INFO_SCHEMA = inline_serializer(
    name="DeviceInfo",
    fields={
        "organization": CharField(),
        "city": CharField(),
        "address": CharField(),
        "room_number": CharField(),
        "manufacturer": CharField(),
        "model": CharField(),
        "serial_number": CharField(),
        "cartridge": CharField(),
        "comment": CharField(),
    },
)

# Okdesk Issue schemas - defined inline to avoid reuse issues
OKDESK_ISSUES_RESPONSE_SCHEMA = inline_serializer(
    name="OkdeskIssuesResponse",
    fields={
        "ok": BooleanField(),
        "issues": serializers.ListField(
            child=inline_serializer(
                name="OkdeskIssue",
                fields={
                    # id заявки Okdesk либо наш номер журнала (2026-00042) — зависит от source
                    "id": CharField(),
                    "source": CharField(),
                    "title": CharField(),
                    "created_at": CharField(allow_null=True),
                    "completed_at": CharField(allow_null=True),
                    "status_name": CharField(allow_null=True),
                    "priority_name": CharField(allow_null=True),
                    "assignee_name": CharField(allow_null=True),
                    "is_overdue": BooleanField(),
                },
            )
        ),
        "count": IntegerField(),
        "has_okdesk_token": BooleanField(),
        "device_info": DEVICE_INFO_SCHEMA,
        "user_full_name": CharField(),
        "user_phone": CharField(),
    },
)

OKDESK_DAILY_STATS_SCHEMA = inline_serializer(
    name="OkdeskDailyStats",
    fields={
        "date": CharField(allow_null=True),
        "total_created": IntegerField(),
        "total_closed": IntegerField(),
        "active_count": IntegerField(),
        "overdue_count": IntegerField(),
        "comments_today": IntegerField(),
        "authors": serializers.ListField(child=CharField()),
    },
)

OKDESK_DAILY_COMMENTS_SCHEMA = inline_serializer(
    name="OkdeskDailyComments",
    fields={
        "comments": serializers.ListField(
            child=inline_serializer(
                name="OkdeskCommentInDaily",
                fields={
                    "id": IntegerField(),
                    "content": CharField(),
                    "author": CharField(allow_null=True),
                    "created_at": CharField(),
                    "is_public": BooleanField(),
                },
            )
        ),
        "page": IntegerField(),
        "per_page": IntegerField(),
        "total": IntegerField(),
        "pages": IntegerField(),
    },
)

OKDESK_STATUS_GROUP_SCHEMA = inline_serializer(
    name="OkdeskStatusGroup",
    fields={
        "status_name": CharField(),
        "count": IntegerField(),
        "issues": serializers.ListField(
            child=inline_serializer(
                name="OkdeskIssueInStatusGroup",
                fields={
                    "id": IntegerField(),
                    "title": CharField(),
                    "created_at": CharField(allow_null=True),
                    "completed_at": CharField(allow_null=True),
                    "status_name": CharField(allow_null=True),
                    "priority_name": CharField(allow_null=True),
                    "assignee_name": CharField(allow_null=True),
                    "is_overdue": BooleanField(),
                },
            )
        ),
    },
)

OKDESK_ACTIVE_GROUPED_SCHEMA = inline_serializer(
    name="OkdeskActiveGrouped",
    fields={
        "groups": serializers.ListField(child=OKDESK_STATUS_GROUP_SCHEMA),
    },
)

OKDESK_ISSUES_BY_STATUS_SCHEMA = inline_serializer(
    name="OkdeskIssuesByStatus",
    fields={
        "status_name": CharField(),
        "issues": serializers.ListField(
            child=inline_serializer(
                name="OkdeskIssueByStatus",
                fields={
                    "id": IntegerField(),
                    "title": CharField(),
                    "created_at": CharField(allow_null=True),
                    "completed_at": CharField(allow_null=True),
                    "status_name": CharField(allow_null=True),
                    "priority_name": CharField(allow_null=True),
                    "assignee_name": CharField(allow_null=True),
                    "is_overdue": BooleanField(),
                },
            )
        ),
        "page": IntegerField(),
        "per_page": IntegerField(),
        "total": IntegerField(),
        "pages": IntegerField(),
    },
)

OKDESK_AUTHORS_SCHEMA = inline_serializer(
    name="OkdeskAuthors",
    fields={
        "authors": serializers.ListField(child=CharField()),
    },
)

OKDESK_CLOSED_ISSUES_SCHEMA = inline_serializer(
    name="OkdeskClosedIssues",
    fields={
        "issues": serializers.ListField(
            child=inline_serializer(
                name="OkdeskClosedIssue",
                fields={
                    "id": IntegerField(),
                    "title": CharField(),
                    "created_at": CharField(allow_null=True),
                    "completed_at": CharField(allow_null=True),
                    "status_name": CharField(allow_null=True),
                    "priority_name": CharField(allow_null=True),
                    "assignee_name": CharField(allow_null=True),
                    "is_overdue": BooleanField(),
                },
            )
        ),
        "page": IntegerField(),
        "per_page": IntegerField(),
        "total": IntegerField(),
        "pages": IntegerField(),
    },
)

OKDESK_ISSUE_DETAIL_SCHEMA = inline_serializer(
    name="OkdeskIssueDetail",
    fields={
        "id": IntegerField(),
        "title": CharField(),
        "description": CharField(allow_null=True),
        "status_name": CharField(allow_null=True),
        "priority_name": CharField(allow_null=True),
        "created_at": CharField(allow_null=True),
        "completed_at": CharField(allow_null=True),
        "author_name": CharField(allow_null=True),
        "assignee_name": CharField(allow_null=True),
        "company_name": CharField(allow_null=True),
        "serial_numbers": CharField(allow_null=True),
        "is_overdue": BooleanField(),
        "comments": serializers.ListField(
            child=inline_serializer(
                name="OkdeskCommentInDetail",
                fields={
                    "id": IntegerField(),
                    "content": CharField(),
                    "author": CharField(allow_null=True),
                    "created_at": CharField(),
                    "is_public": BooleanField(),
                },
            )
        ),
    },
)


SYNC_STATUS_SCHEMA = inline_serializer(
    name="SyncStatus",
    fields={
        "ok": BooleanField(),
        "all_done": BooleanField(),
        "tasks": serializers.DictField(),
    },
)

OKDESK_POST_COMMENT_RESPONSE_SCHEMA = inline_serializer(
    name="OkdeskPostCommentResponse",
    fields={
        "ok": BooleanField(),
        "comment": inline_serializer(
            name="OkdeskCommentInResponse",
            fields={
                "id": IntegerField(),
                "content": CharField(),
                "author": CharField(allow_null=True),
                "created_at": CharField(),
                "is_public": BooleanField(),
            },
        ),
    },
)

SYNC_NOW_TASKS_SCHEMA = inline_serializer(
    name="SyncNowTasks",
    fields={
        "ok": BooleanField(),
        "tasks": serializers.DictField(child=CharField()),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# GLPI DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

check_device_glpi_schema = extend_schema(
    operation_id="check_device_glpi",
    tags=["integrations", "glpi"],
    summary="Проверить устройство в GLPI",
    description="Проверяет наличие устройства в GLPI по серийному номеру. "
    "Возвращает статус синхронизации и информацию из GLPI.",
    parameters=[
        OpenApiParameter(
            name="device_id",
            description="ID устройства",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    request=CheckDeviceGLPIRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="CheckDeviceGLPIResponse",
                fields={
                    "ok": BooleanField(),
                    "sync": GLPI_SYNC_SCHEMA,
                },
            ),
            description="Результат проверки",
        ),
        403: OpenApiResponse(description="Нет прав"),
        404: OpenApiResponse(description="Устройство не найдено"),
        500: OpenApiResponse(description="Ошибка сервера"),
    },
)

check_multiple_devices_glpi_schema = extend_schema(
    operation_id="check_multiple_devices_glpi",
    tags=["integrations", "glpi"],
    summary="Проверить несколько устройств в GLPI",
    description="Массовая проверка устройств в GLPI. Максимум 100 устройств за запрос.",
    request=CheckMultipleDevicesGLPIRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="CheckMultipleDevicesGLPIResponse",
                fields={
                    "ok": BooleanField(),
                    "stats": serializers.DictField(),
                },
            ),
            description="Результат проверки",
        ),
        400: OpenApiResponse(description="Неверный запрос"),
        403: OpenApiResponse(description="Нет прав"),
        500: OpenApiResponse(description="Ошибка сервера"),
    },
)

get_device_sync_status_schema = extend_schema(
    operation_id="get_device_sync_status",
    tags=["integrations", "glpi"],
    summary="Статус синхронизации устройства",
    description="Возвращает информацию о последней синхронизации устройства с GLPI.",
    parameters=[
        OpenApiParameter(
            name="device_id",
            description="ID устройства",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="DeviceSyncStatusResponse",
                fields={
                    "ok": BooleanField(),
                    "sync": GLPI_SYNC_SCHEMA,
                    "message": CharField(allow_null=True),
                },
            ),
            description="Статус синхронизации",
        ),
        403: OpenApiResponse(description="Нет прав"),
        404: OpenApiResponse(description="Устройство не найдено"),
    },
)

get_glpi_conflicts_schema = extend_schema(
    operation_id="get_glpi_conflicts",
    tags=["integrations", "glpi"],
    summary="Устройства с конфликтами в GLPI",
    description="Возвращает список устройств, для которых в GLPI найдено несколько карточек.",
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="GLPIConflictsResponse",
                fields={
                    "ok": BooleanField(),
                    "count": IntegerField(),
                    "devices": serializers.ListField(child=GLPI_DEVICE_CONFLICT_SCHEMA),
                },
            ),
            description="Список устройств с конфликтами",
        ),
        403: OpenApiResponse(description="Нет прав"),
    },
)

get_devices_not_in_glpi_schema = extend_schema(
    operation_id="get_devices_not_in_glpi",
    tags=["integrations", "glpi"],
    summary="Устройства, не найденные в GLPI",
    description="Возвращает список устройств, которые не были найдены в GLPI.",
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="DevicesNotInGLPIResponse",
                fields={
                    "ok": BooleanField(),
                    "count": IntegerField(),
                    "devices": serializers.ListField(child=GLPI_DEVICE_NOT_FOUND_SCHEMA),
                },
            ),
            description="Список устройств",
        ),
        403: OpenApiResponse(description="Нет прав"),
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# OKDESK DECORATORS
# ──────────────────────────────────────────────────────────────────────────────

get_okdesk_issues_schema = extend_schema(
    operation_id="get_okdesk_issues",
    tags=["integrations", "okdesk"],
    summary="Заявки по устройству",
    description="Возвращает заявки, связанные с устройством: зеркало Okdesk и наш журнал заявок "
    "(в том числе поданные почтой). Также возвращает информацию об устройстве и данные пользователя "
    "для создания заявки.",
    parameters=[
        OpenApiParameter(
            name="device_id",
            description="ID устройства",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_ISSUES_RESPONSE_SCHEMA, description="Заявки и информация об устройстве"),
        403: OpenApiResponse(description="Нет прав"),
        404: OpenApiResponse(description="Устройство не найдено"),
    },
)

create_service_request_schema = extend_schema(
    operation_id="create_service_request",
    tags=["integrations", "okdesk"],
    summary="Подать заявку подрядчику",
    description="Регистрирует заявку в журнале и передаёт подрядчику устройства (Okdesk API или почта сервис-деска).",
    request=CreateServiceRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="CreateServiceRequestResponse",
                fields={"ok": BooleanField(), "issue_id": IntegerField()},
            ),
            description="Заявка создана",
        ),
        400: OpenApiResponse(description="Неверный запрос"),
        403: OpenApiResponse(description="Нет прав или не настроен токен"),
        404: OpenApiResponse(description="Устройство не найдено"),
        502: OpenApiResponse(description="Ошибка соединения с Okdesk"),
        504: OpenApiResponse(description="Таймаут Okdesk"),
    },
)

api_okdesk_daily_stats_schema = extend_schema(
    operation_id="api_okdesk_daily_stats",
    tags=["integrations", "okdesk"],
    summary="Дневная статистика Okdesk",
    description="Возвращает статистику по заявкам за указанную дату (или сегодня).",
    parameters=[
        OpenApiParameter(name="date", description="Дата (YYYY-MM-DD)", type=str, required=False),
        OpenApiParameter(
            name="mine",
            description="Только мои заявки (1/true/yes)",
            type=bool,
            required=False,
        ),
        OpenApiParameter(name="q", description="Поиск по серийнику/организации/теме", type=str, required=False),
        OpenApiParameter(
            name="author", description="Фильтр по инициатору (можно указывать несколько)", type=str, required=False
        ),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_DAILY_STATS_SCHEMA, description="Статистика за день"),
    },
)

api_okdesk_daily_comments_schema = extend_schema(
    operation_id="api_okdesk_daily_comments",
    tags=["integrations", "okdesk"],
    summary="Комментарии за день",
    description="Возвращает комментарии к заявкам за указанную дату с пагинацией.",
    parameters=[
        OpenApiParameter(name="date", description="Дата (YYYY-MM-DD)", type=str, required=False),
        OpenApiParameter(name="page", description="Страница", type=int, required=False, default=1),
        OpenApiParameter(name="per_page", description="На странице (макс 200)", type=int, required=False, default=50),
        OpenApiParameter(name="mine", description="Только мои (1/true/yes)", type=bool, required=False),
        OpenApiParameter(name="q", description="Поиск", type=str, required=False),
        OpenApiParameter(name="author", description="Инициатор", type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_DAILY_COMMENTS_SCHEMA, description="Комментарии"),
    },
)

api_okdesk_active_grouped_schema = extend_schema(
    operation_id="api_okdesk_active_grouped",
    tags=["integrations", "okdesk"],
    summary="Активные заявки по статусам",
    description="Возвращает активные заявки, сгруппированные по статусам.",
    parameters=[
        OpenApiParameter(name="mine", description="Только мои (1/true/yes)", type=bool, required=False),
        OpenApiParameter(name="q", description="Поиск", type=str, required=False),
        OpenApiParameter(name="author", description="Инициатор", type=str, required=False),
        OpenApiParameter(name="date_from", description="Начало периода (YYYY-MM-DD)", type=str, required=False),
        OpenApiParameter(name="date_to", description="Конец периода (YYYY-MM-DD)", type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_ACTIVE_GROUPED_SCHEMA, description="Заявки по статусам"),
    },
)

api_okdesk_by_status_schema = extend_schema(
    operation_id="api_okdesk_by_status",
    tags=["integrations", "okdesk"],
    summary="Заявки по статусу",
    description="Возвращает заявки с указанным статусом с пагинацией.",
    parameters=[
        OpenApiParameter(
            name="status_name",
            description="Название статуса (URL-encoded)",
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
        ),
        OpenApiParameter(name="page", description="Страница", type=int, required=False, default=1),
        OpenApiParameter(name="mine", description="Только мои (1/true/yes)", type=bool, required=False),
        OpenApiParameter(name="q", description="Поиск", type=str, required=False),
        OpenApiParameter(name="author", description="Инициатор", type=str, required=False),
        OpenApiParameter(name="date_from", description="Начало периода (YYYY-MM-DD)", type=str, required=False),
        OpenApiParameter(name="date_to", description="Конец периода (YYYY-MM-DD)", type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_ISSUES_BY_STATUS_SCHEMA, description="Заявки по статусу"),
    },
)

api_okdesk_authors_schema = extend_schema(
    operation_id="api_okdesk_authors",
    tags=["integrations", "okdesk"],
    summary="Список инициаторов заявок",
    description="Возвращает список уникальных инициаторов заявок для автодополнения фильтра.",
    parameters=[
        OpenApiParameter(name="q", description="Поиск по имени", type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_AUTHORS_SCHEMA, description="Список инициаторов"),
    },
)

api_okdesk_closed_schema = extend_schema(
    operation_id="api_okdesk_closed",
    tags=["integrations", "okdesk"],
    summary="Закрытые заявки",
    description="Возвращает закрытые заявки с пагинацией.",
    parameters=[
        OpenApiParameter(name="page", description="Страница", type=int, required=False, default=1),
        OpenApiParameter(name="mine", description="Только мои (1/true/yes)", type=bool, required=False),
        OpenApiParameter(name="q", description="Поиск", type=str, required=False),
        OpenApiParameter(name="author", description="Инициатор", type=str, required=False),
        OpenApiParameter(name="date_from", description="Начало периода (YYYY-MM-DD)", type=str, required=False),
        OpenApiParameter(name="date_to", description="Конец периода (YYYY-MM-DD)", type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_CLOSED_ISSUES_SCHEMA, description="Закрытые заявки"),
    },
)

api_okdesk_issue_detail_schema = extend_schema(
    operation_id="api_okdesk_issue_detail",
    tags=["integrations", "okdesk"],
    summary="Детали заявки Okdesk",
    description="Возвращает подробную информацию о заявке с комментариями.",
    parameters=[
        OpenApiParameter(
            name="issue_id",
            description="ID заявки",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    responses={
        200: OpenApiResponse(response=OKDESK_ISSUE_DETAIL_SCHEMA, description="Детали заявки"),
        404: OpenApiResponse(description="Заявка не найдена"),
    },
)

okdesk_refresh_issue_comments_schema = extend_schema(
    operation_id="okdesk_refresh_issue_comments",
    tags=["integrations", "okdesk"],
    summary="Обновить комментарии заявки",
    description="Запускает фоновую синхронизацию комментариев для указанной заявки.",
    parameters=[
        OpenApiParameter(
            name="issue_id",
            description="ID заявки",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    responses={
        202: OpenApiResponse(
            response=inline_serializer(
                name="RefreshCommentsResponse",
                fields={"ok": BooleanField(), "task_id": CharField()},
            ),
            description="Синхронизация запущена",
        ),
        500: OpenApiResponse(description="Не удалось поставить задачу"),
    },
)

okdesk_post_comment_schema = extend_schema(
    operation_id="okdesk_post_comment",
    tags=["integrations", "okdesk"],
    summary="Отправить комментарий в Okdesk",
    description="Отправляет комментарий к заявке от имени пользователя. Требует личный API-токен.",
    parameters=[
        OpenApiParameter(
            name="issue_id",
            description="ID заявки",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
        ),
    ],
    request=PostCommentRequestSerializer,
    responses={
        200: OpenApiResponse(response=OKDESK_POST_COMMENT_RESPONSE_SCHEMA, description="Комментарий отправлен"),
        400: OpenApiResponse(description="Неверный запрос"),
        403: OpenApiResponse(description="Нет прав или неверный токен"),
        500: OpenApiResponse(description="Внутренняя ошибка"),
    },
)

okdesk_sync_now_schema = extend_schema(
    operation_id="okdesk_sync_now",
    tags=["integrations", "okdesk"],
    summary="Запустить синхронизацию Okdesk",
    description="Запускает ручную синхронизацию заявок и/или комментариев из Okdesk API.",
    request=SyncNowRequestSerializer,
    responses={
        200: OpenApiResponse(response=SYNC_NOW_TASKS_SCHEMA, description="Синхронизация запущена"),
        400: OpenApiResponse(description="Неверный запрос"),
        409: OpenApiResponse(description="Синхронизация уже запущена"),
        500: OpenApiResponse(description="Ошибка запуска"),
    },
)

okdesk_sync_status_schema = extend_schema(
    operation_id="okdesk_sync_status",
    tags=["integrations", "okdesk"],
    summary="Статус синхронизации Okdesk",
    description="Возвращает статус задач синхронизации по их ID.",
    parameters=[
        OpenApiParameter(
            name="ids",
            description="Список task_id через запятую",
            type=str,
            required=True,
        ),
        OpenApiParameter(
            name="release_lock",
            description="Снять anti-spam lock (1/true/yes)",
            type=bool,
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(response=SYNC_STATUS_SCHEMA, description="Статус задач"),
        400: OpenApiResponse(description="Не указаны IDs"),
    },
)
