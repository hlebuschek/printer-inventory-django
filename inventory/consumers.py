from channels.generic.websocket import AsyncJsonWebsocketConsumer

class InventoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('inventory_updates', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('inventory_updates', self.channel_name)

    async def inventory_start(self, event):
        # показываем старт опроса
        await self.send_json(event)

    async def inventory_update(self, event):
        # показываем завершение опроса
        await self.send_json(event)