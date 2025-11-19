# monthly_report/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class MonthlyReportConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer для real-time обновлений в monthly_report

    Обрабатывает:
    - Подключение к комнате по месяцу (year-month, например "2024-01")
    - Получение обновлений счетчиков от других пользователей
    - Уведомления о конфликтах редактирования
    """

    async def connect(self):
        """
        Подключение клиента к WebSocket
        Клиент присоединяется к группе по месяцу (year-month)
        """
        # Получаем параметры из URL (год и месяц)
        self.year = self.scope['url_route']['kwargs'].get('year')
        self.month = self.scope['url_route']['kwargs'].get('month')

        # Формируем имя группы: monthly_report_2024_01
        self.room_group_name = f'monthly_report_{self.year}_{self.month}'

        # Присоединяем к группе
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """
        Отключение клиента от WebSocket
        """
        # Покидаем группу
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def counter_update(self, event):
        """
        Обработчик события обновления счетчика
        Отправляет обновление всем клиентам в группе

        event содержит:
        - type: 'counter_update'
        - report_id: ID записи MonthlyReport
        - field: название поля (например, 'a4_bw_end')
        - old_value: старое значение
        - new_value: новое значение
        - user_username: имя пользователя, который изменил
        - user_full_name: полное имя пользователя
        - timestamp: время изменения
        """
        # Отправляем сообщение клиенту
        await self.send_json({
            'type': 'counter_update',
            'report_id': event['report_id'],
            'field': event['field'],
            'old_value': event['old_value'],
            'new_value': event['new_value'],
            'user_username': event['user_username'],
            'user_full_name': event['user_full_name'],
            'timestamp': event['timestamp'],
        })

    async def total_prints_update(self, event):
        """
        Обработчик события обновления total_prints после пересчета группы
        Отправляет обновление всем клиентам в группе

        event содержит:
        - type: 'total_prints_update'
        - report_id: ID записи MonthlyReport
        - total_prints: новое значение total_prints
        - is_anomaly: флаг аномалии
        - anomaly_info: детали аномалии (optional)
        """
        await self.send_json({
            'type': 'total_prints_update',
            'report_id': event['report_id'],
            'total_prints': event['total_prints'],
            'is_anomaly': event['is_anomaly'],
            'anomaly_info': event.get('anomaly_info', {}),
        })

    async def editing_notification(self, event):
        """
        Уведомление о том, что пользователь начал редактировать ячейку

        event содержит:
        - type: 'editing_notification'
        - report_id: ID записи MonthlyReport
        - field: название поля
        - user_username: имя пользователя
        - action: 'start' или 'stop'
        """
        await self.send_json({
            'type': 'editing_notification',
            'report_id': event['report_id'],
            'field': event['field'],
            'user_username': event['user_username'],
            'action': event['action'],
        })
