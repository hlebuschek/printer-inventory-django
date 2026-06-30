# printer_inventory/manual_schema.py
"""
Ручная генерация OpenAPI схемы для всех endpoints.
Используется когда drf-spectacular auto-discovery не работает с Django views.
"""


def get_manual_schema():
    """Генерирует OpenAPI схему вручную для всех URL patterns."""

    # Регистрируем все API endpoints вручную
    schema = {
        "openapi": "3.0.3",
        "info": {
            "title": "Printer Inventory API",
            "description": "API для управления инвентаризацией принтеров, отчётами и интеграциями",
            "version": "1.0.0",
        },
        "paths": {},
        "tags": [
            {"name": "printers", "description": "Управление принтерами"},
            {"name": "inventory", "description": "Опрос устройств"},
            {"name": "contracts", "description": "Договоры и устройства"},
            {"name": "dashboard", "description": "Статистика и метрики"},
            {"name": "monthly_report", "description": "Ежемесячные отчёты"},
            {"name": "supplies_report", "description": "Отчёты по расходникам"},
            {"name": "integrations", "description": "Интеграции с GLPI, Okdesk"},
            {"name": "system", "description": "Системное состояние"},
        ],
    }

    return schema
