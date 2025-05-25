import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import inventory.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            inventory.routing.websocket_urlpatterns
        )
    ),
})