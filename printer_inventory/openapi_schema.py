# printer_inventory/openapi_schema.py
"""
Ручное описание OpenAPI 3.0 схемы для API.
Используется вместо drf-spectacular для генерации документации.
"""
from django.conf import settings


def generate_openapi_schema(request):
    """
    Генерирует OpenAPI 3.0 схему для всех API endpoints.
    Возвращает словарь, который можно сериализовать в JSON.
    """
    # Получаем базовый URL из запроса
    scheme = request.scheme
    host = request.get_host()
    base_url = f"{scheme}://{host}"

    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": "Printer Inventory API",
            "description": "API для системы инвентаризации и мониторинга принтеров",
            "version": "2.0.0",
            "contact": {
                "name": "Printer Inventory System",
            },
        },
        "servers": [
            {
                "url": base_url,
                "description": "Текущий сервер",
            }
        ],
        "tags": [
            {
                "name": "printers",
                "description": "Управление принтерами",
            },
            {
                "name": "inventory",
                "description": "Опрос устройств",
            },
            {
                "name": "system",
                "description": "Статус системы",
            },
            {
                "name": "web-parser",
                "description": "Веб-парсинг",
            },
            {
                "name": "usb",
                "description": "USB-агенты",
            },
        ],
        "paths": {
            # ═══════════════════════════════════════════════════════════════
            # ПРИНТЕРЫ
            # ═══════════════════════════════════════════════════════════════
            "/inventory/api/printers/": {
                "get": {
                    "tags": ["printers"],
                    "summary": "Список принтеров",
                    "description": "Возвращает список принтеров с фильтрацией и пагинацией",
                    "operationId": "api_printers_list",
                    "parameters": [
                        {
                            "name": "q_ip",
                            "in": "query",
                            "description": "Фильтр по IP-адресу",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "q_serial",
                            "in": "query",
                            "description": "Фильтр по серийному номеру",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "q_org",
                            "in": "query",
                            "description": "Фильтр по организации",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "q_manufacturer",
                            "in": "query",
                            "description": "Фильтр по производителю (ID)",
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "q_device_model",
                            "in": "query",
                            "description": "Фильтр по модели (ID)",
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "q_model_text",
                            "in": "query",
                            "description": "Фильтр по названию модели",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "q_rule",
                            "in": "query",
                            "description": "Правило сопоставления",
                            "schema": {
                                "type": "string",
                                "enum": ["SN_MAC", "MAC_ONLY", "SN_ONLY", "NONE"],
                            },
                        },
                        {
                            "name": "q_active",
                            "in": "query",
                            "description": "Активность",
                            "schema": {
                                "type": "string",
                                "enum": ["true", "false", "all"],
                            },
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "description": "Номер страницы",
                            "schema": {"type": "integer", "default": 1},
                        },
                        {
                            "name": "per_page",
                            "in": "query",
                            "description": "Элементов на странице",
                            "schema": {
                                "type": "integer",
                                "enum": [10, 25, 50, 100, 250, 500, 1000, 2000, 5000],
                                "default": 50,
                            },
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Список принтеров",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PrinterList"},
                                }
                            },
                        },
                        "401": {"description": "Не авторизован"},
                        "403": {"description": "Нет прав"},
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/printer/{id}/": {
                "get": {
                    "tags": ["printers"],
                    "summary": "Детали принтера",
                    "description": "Детальная информация о принтере по ID",
                    "operationId": "api_printer_detail",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "description": "ID принтера",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Детали принтера",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Printer"},
                                }
                            },
                        },
                        "404": {
                            "description": "Принтер не найден",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"},
                                }
                            },
                        },
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/probe-serial/": {
                "post": {
                    "tags": ["inventory"],
                    "summary": "Опрос по serial",
                    "description": "Запускает SNMP/Web опрос принтера по serial number",
                    "operationId": "api_probe_serial",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["serial"],
                                    "properties": {
                                        "serial": {
                                            "type": "string",
                                            "description": "Серийный номер принтера",
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Результат опроса",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/InventoryResult"},
                                }
                            },
                        },
                        "400": {
                            "description": "Ошибка запроса",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"},
                                }
                            },
                        },
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/models-by-manufacturer/": {
                "get": {
                    "tags": ["printers"],
                    "summary": "Модели по производителю",
                    "description": "Список моделей принтеров указанного производителя",
                    "operationId": "api_models_by_manufacturer",
                    "parameters": [
                        {
                            "name": "manufacturer_id",
                            "in": "query",
                            "description": "ID производителя",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Список моделей",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/all-printer-models/": {
                "get": {
                    "tags": ["printers"],
                    "summary": "Все модели принтеров",
                    "description": "Полный список моделей с производительностью",
                    "operationId": "api_all_printer_models",
                    "responses": {
                        "200": {
                            "description": "Список моделей",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/printer/{id}/replacement-history/": {
                "get": {
                    "tags": ["printers"],
                    "summary": "История замен",
                    "description": "История замен принтера по ID",
                    "operationId": "api_printer_replacement_history",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "description": "ID принтера",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "История замен",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            # ═══════════════════════════════════════════════════════════════
            # СИСТЕМА
            # ═══════════════════════════════════════════════════════════════
            "/inventory/api/system-status/": {
                "get": {
                    "tags": ["system"],
                    "summary": "Статус системы",
                    "description": "Проверка состояния компонентов (Celery, Redis, БД)",
                    "operationId": "api_system_status",
                    "responses": {
                        "200": {
                            "description": "Статус системы",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SystemStatus"},
                                }
                            },
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/status-statistics/": {
                "get": {
                    "tags": ["system"],
                    "summary": "Статистика опросов",
                    "description": "Статистика по статусам опросов принтеров",
                    "operationId": "api_status_statistics",
                    "responses": {
                        "200": {
                            "description": "Статистика",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StatusStatistics"},
                                }
                            },
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            # ═══════════════════════════════════════════════════════════════
            # USB-АГЕНТЫ
            # ═══════════════════════════════════════════════════════════════
            "/api/v1/inventory/health/": {
                "get": {
                    "tags": ["usb"],
                    "summary": "Health check USB-агента",
                    "description": "Проверка доступности API для USB-агентов",
                    "operationId": "usb_health",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                }
            },
            "/api/v1/inventory/usb-agents/register/": {
                "post": {
                    "tags": ["usb"],
                    "summary": "Регистрация USB-агента",
                    "description": "Регистрация нового агента для опроса локальных принтеров",
                    "operationId": "usb_agent_register",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["agent_id", "token"],
                                    "properties": {
                                        "agent_id": {
                                            "type": "string",
                                            "description": "Уникальный ID агента",
                                        },
                                        "token": {
                                            "type": "string",
                                            "description": "Токен авторизации",
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Агент зарегистрирован"},
                        "401": {"description": "Неверный токен"},
                        "409": {"description": "Агент уже зарегистрирован"},
                    },
                }
            },
            "/api/v1/inventory/usb-readings/": {
                "post": {
                    "tags": ["usb"],
                    "summary": "Отправка показаний USB-принтера",
                    "description": "Приём показаний от USB-агента",
                    "operationId": "usb_readings",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/USBReading"},
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Показания приняты"},
                        "400": {"description": "Ошибка валидации"},
                        "401": {"description": "Не авторизован"},
                        "404": {"description": "Принтер не найден"},
                    },
                }
            },
            # ═══════════════════════════════════════════════════════════════
            # WEB-PARSER
            # ═══════════════════════════════════════════════════════════════
            "/inventory/api/web-parser/save-rule/": {
                "post": {
                    "tags": ["web-parser"],
                    "summary": "Сохранение правила веб-парсинга",
                    "description": "Создание или обновление правила для веб-парсинга",
                    "operationId": "save_web_parsing_rule",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/WebParsingRule"},
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Правило сохранено"},
                        "400": {"description": "Ошибка валидации"},
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/web-parser/rules/{printer_id}/": {
                "get": {
                    "tags": ["web-parser"],
                    "summary": "Получение правил",
                    "operationId": "get_rules",
                    "parameters": [
                        {
                            "name": "printer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Список правил",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
            "/inventory/api/web-parser/test-xpath/": {
                "post": {
                    "tags": ["web-parser"],
                    "summary": "Тест XPath",
                    "operationId": "test_xpath",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["url", "xpath"],
                                    "properties": {
                                        "url": {"type": "string"},
                                        "xpath": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Результат теста"},
                    },
                    "security": [{"sessionAuth": []}],
                }
            },
        },
        "components": {
            "securitySchemes": {
                "sessionAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "sessionid",
                    "description": "Django session authentication",
                }
            },
            "schemas": {
                "Printer": {
                    "type": "object",
                    "description": "Принтер",
                    "properties": {
                        "id": {"type": "integer", "description": "ID"},
                        "ip_address": {"type": "string", "description": "IP-адрес"},
                        "serial_number": {"type": "string", "nullable": True, "description": "Серийный номер"},
                        "model": {"type": "string", "nullable": True, "description": "Модель (legacy)"},
                        "organization": {"type": "string", "nullable": True, "description": "Организация"},
                        "device_model": {"type": "string", "nullable": True, "description": "Модель устройства"},
                        "manufacturer": {"type": "string", "nullable": True, "description": "Производитель"},
                        "location": {"type": "string", "nullable": True, "description": "Расположение"},
                        "is_active": {"type": "boolean", "description": "Активен"},
                        "snmp_community": {"type": "string", "nullable": True, "description": "SNMP community"},
                        "connection_type": {
                            "type": "string",
                            "enum": ["NETWORK", "USB"],
                            "description": "Тип подключения",
                        },
                        "polling_method": {
                            "type": "string",
                            "enum": ["SNMP", "WEB", "USB_API"],
                            "description": "Метод опроса",
                        },
                        "last_inventory": {"type": "string", "nullable": True, "format": "date-time"},
                        "last_inventory_status": {"type": "string", "nullable": True},
                        "a4_bw": {"type": "integer", "nullable": True, "description": "A4 Ч/Б"},
                        "a4_color": {"type": "integer", "nullable": True, "description": "A4 цвет"},
                        "a3_bw": {"type": "integer", "nullable": True, "description": "A3 Ч/Б"},
                        "a3_color": {"type": "integer", "nullable": True, "description": "A3 цвет"},
                    },
                },
                "PrinterList": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Всего"},
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                        "results": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Printer"},
                        },
                    },
                },
                "SystemStatus": {
                    "type": "object",
                    "description": "Статус системы",
                    "properties": {
                        "celery": {
                            "type": "string",
                            "enum": ["ok", "down", "unknown"],
                            "description": "Статус Celery",
                        },
                        "redis": {
                            "type": "string",
                            "enum": ["ok", "down", "unknown"],
                            "description": "Статус Redis",
                        },
                        "database": {
                            "type": "string",
                            "enum": ["ok", "down", "unknown"],
                            "description": "Статус БД",
                        },
                        "celery_workers": {
                            "type": "integer",
                            "nullable": True,
                            "description": "Количество воркеров",
                        },
                    },
                },
                "StatusStatistics": {
                    "type": "object",
                    "description": "Статистика опросов",
                    "properties": {
                        "total": {"type": "integer", "description": "Всего принтеров"},
                        "success": {"type": "integer", "description": "Успешные опросы"},
                        "failed": {"type": "integer", "description": "Неудачные опросы"},
                        "pending": {"type": "integer", "description": "Ожидают опроса"},
                        "success_rate": {"type": "string", "description": "% успешных"},
                    },
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string", "description": "Тип ошибки"},
                        "message": {"type": "string", "description": "Сообщение"},
                    },
                },
                "InventoryResult": {
                    "type": "object",
                    "description": "Результат опроса",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"},
                        "data": {"type": "object", "nullable": True},
                    },
                },
                "USBReading": {
                    "type": "object",
                    "required": ["agent_id", "usb_identifier", "readings"],
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "ID агента",
                        },
                        "usb_identifier": {
                            "type": "string",
                            "description": "USB идентификатор принтера",
                        },
                        "serial_number": {
                            "type": "string",
                            "description": "Серийный номер",
                        },
                        "readings": {
                            "type": "object",
                            "description": "Показания счётчиков",
                        },
                    },
                },
                "WebParsingRule": {
                    "type": "object",
                    "properties": {
                        "printer_id": {"type": "integer"},
                        "page_type": {
                            "type": "string",
                            "enum": ["COUNTERS", "CONSUMABLES", "STATUS"],
                        },
                        "url_template": {"type": "string"},
                        "xpath_expression": {"type": "string"},
                        "regex_pattern": {"type": "string", "nullable": True},
                        "json_path": {"type": "string", "nullable": True},
                    },
                },
            },
        },
    }

    return schema
