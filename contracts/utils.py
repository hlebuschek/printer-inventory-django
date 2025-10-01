import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from .models import ContractDevice


def generate_email_for_device(device_id=None, serial_number=None, user_email='user@example.com'):
    """
    Генерирует .eml файл с заявкой на картридж для устройства.

    Args:
        device_id: ID устройства в ContractDevice (опционально)
        serial_number: Серийный номер для поиска устройства (опционально)
        user_email: Email отправителя

    Returns:
        FileResponse с .eml файлом

    Raises:
        Http404: Если устройство не найдено
    """
    # Получаем устройство по ID или серийному номеру
    if device_id:
        device = get_object_or_404(
            ContractDevice.objects
            .select_related('organization', 'city', 'model__manufacturer', 'status')
            .prefetch_related('model__model_cartridges__cartridge'),
            pk=device_id
        )
    elif serial_number:
        try:
            device = (ContractDevice.objects
                      .select_related('organization', 'city', 'model__manufacturer', 'status')
                      .prefetch_related('model__model_cartridges__cartridge')
                      .get(serial_number__iexact=serial_number))
        except ContractDevice.DoesNotExist:
            raise Http404(f"Устройство с серийным номером {serial_number} не найдено в договорах")
    else:
        raise ValueError("Необходимо указать device_id или serial_number")

    # Получаем картриджи для этой модели
    cartridges = device.model.model_cartridges.select_related("cartridge").all()

    # Формируем строку с картриджами
    if cartridges:
        primary = [mc.cartridge for mc in cartridges if mc.is_primary]
        other = [mc.cartridge for mc in cartridges if not mc.is_primary]

        cartridge_list = []
        for c in (primary + other):
            parts = [c.name]
            if c.part_number:
                parts.append(f"({c.part_number})")
            if c.color and c.color != "black":
                parts.append(f"[{c.get_color_display()}]")
            cartridge_list.append(" ".join(parts))

        cartridge_text = ", ".join(cartridge_list)
    else:
        cartridge_text = ""

    # Создаем email сообщение
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Заявка на картридж'
    msg['From'] = user_email
    msg['To'] = ''
    msg['Date'] = formatdate(localtime=True)

    # HTML версия письма
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                font-size: 11pt;
                color: #000;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #000;
                padding: 8px;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background-color: #d9d9d9;
                font-weight: bold;
                text-align: center;
            }}
            .editable {{
                background-color: #fff;
                min-height: 20px;
            }}
            .auto-filled {{
                background-color: #e8f4f8;
            }}
        </style>
    </head>
    <body>
        <table>
            <thead>
                <tr>
                    <th>№</th>
                    <th>Организация</th>
                    <th>Филиал</th>
                    <th>Город</th>
                    <th>Адрес</th>
                    <th>Кабинет</th>
                    <th>Производитель</th>
                    <th>Модель</th>
                    <th>Серийный номер</th>
                    <th>Инв номер</th>
                    <th>Картридж</th>
                    <th>Ремонт/обслуживание</th>
                    <th>Комментарии</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="text-align: center;">1</td>
                    <td>{device.organization.name}</td>
                    <td class="editable"></td>
                    <td>{device.city.name}</td>
                    <td>{device.address or ''}</td>
                    <td>{device.room_number or ''}</td>
                    <td>{device.model.manufacturer.name}</td>
                    <td>{device.model.name}</td>
                    <td>{device.serial_number or ''}</td>
                    <td class="editable"></td>
                    <td class="{'auto-filled' if cartridge_text else 'editable'}">{cartridge_text}</td>
                    <td class="editable"></td>
                    <td class="editable">{device.comment or ''}</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """

    # Текстовая версия
    text_body = f"""
Заявка на картридж

№ | Организация | Филиал | Город | Адрес | Кабинет | Производитель | Модель | Серийный номер | Инв номер | Картридж | Ремонт/обслуживание | Комментарии
--|-------------|--------|-------|-------|---------|---------------|--------|----------------|-----------|----------|---------------------|-------------
1 | {device.organization.name} | _______ | {device.city.name} | {device.address or '_______'} | {device.room_number or '_______'} | {device.model.manufacturer.name} | {device.model.name} | {device.serial_number or '_______'} | _______ | {cartridge_text or '_______'} | _______ | {device.comment or '_______'}

Заполните пустые поля перед отправкой.
    """

    # Прикрепляем обе версии
    part1 = MIMEText(text_body, 'plain', 'utf-8')
    part2 = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)

    # Сохраняем как .eml
    email_content = msg.as_bytes()

    # Создаем безопасное имя файла
    safe_org = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                       for c in device.organization.name[:30])

    filename = f"Заявка_на_картридж_{safe_org}_{device.serial_number or 'nosn'}.eml"
    filename = filename[:200]

    # Возвращаем файл
    buffer = io.BytesIO(email_content)
    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type='message/rfc822'
    )