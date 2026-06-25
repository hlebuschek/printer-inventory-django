-- Обновление VIEW dm_itil.contract_device с добавлением колонки "Количество заявок Okdesk"
-- Дата: 2026-04-29

CREATE OR REPLACE VIEW dm_itil.contract_device
AS SELECT
    o.name AS "Организация",
    ci.name AS "Город",
    d.address AS "Адрес",
    d.room_number AS "№ кабинета",
    m.name AS "Производитель",
    dm.name AS "Модель оборудования",
    CASE
        WHEN dm.has_network_port THEN 'Да'::text
        ELSE 'Нет'::text
    END AS "Наличие сетевого порта",
    d.serial_number AS "Серийный номер",
    to_char(d.service_start_month::timestamp with time zone, 'MM.YYYY'::text) AS "Месяц принятия на обслуживание",
    s.name AS "Статус",
    d.comment AS "Комментарий",
    CASE
        WHEN ip.serial_number IS NOT NULL THEN 1
        ELSE 0
    END AS "Сетевой",
    COALESCE(okdesk.issue_count, 0) AS "Количество заявок Okdesk"
FROM dw_itil.contracts_contractdevice d
    LEFT JOIN dw_itil.inventory_organization o ON d.organization_id = o.id
    LEFT JOIN dw_itil.contracts_city ci ON d.city_id = ci.id
    LEFT JOIN dw_itil.contracts_devicemodel dm ON d.model_id = dm.id
    LEFT JOIN dw_itil.contracts_manufacturer m ON dm.manufacturer_id = m.id
    LEFT JOIN dw_itil.contracts_contractstatus s ON d.status_id = s.id
    LEFT JOIN dw_itil.inventory_printer ip ON d.serial_number::text = ip.serial_number
    LEFT JOIN (
        -- Подсчет заявок Okdesk по серийному номеру
        -- Логика поиска соответствует integrations/views.py:279-284
        SELECT
            d2.id as device_id,
            COUNT(oi.id) as issue_count
        FROM dw_itil.contracts_contractdevice d2
        LEFT JOIN dw_itil.integrations_okdeskissue oi ON (
            d2.serial_number IS NOT NULL
            AND d2.serial_number != ''
            AND (
                oi.serial_numbers = d2.serial_number
                OR oi.serial_numbers LIKE d2.serial_number || ',%'
                OR oi.serial_numbers LIKE '%, ' || d2.serial_number
                OR oi.serial_numbers LIKE '%, ' || d2.serial_number || ',%'
            )
        )
        GROUP BY d2.id
    ) okdesk ON okdesk.device_id = d.id;

-- Комментарий к колонке
COMMENT ON COLUMN dm_itil.contract_device."Количество заявок Okdesk" IS
'Количество заявок из системы Okdesk, связанных с устройством по серийному номеру. Поиск выполняется по полю serial_numbers (через запятую).';
