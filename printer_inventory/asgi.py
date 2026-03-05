import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import inventory.routing
import monthly_report.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "printer_inventory.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(inventory.routing.websocket_urlpatterns + monthly_report.routing.websocket_urlpatterns)
        ),
    }
)
