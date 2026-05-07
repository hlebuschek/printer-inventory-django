"""Аутентификация USB-агентов по Bearer-токену."""

import functools
import logging

from django.http import JsonResponse

from .models import USBAgent
from .services_usb import hash_token

logger = logging.getLogger(__name__)


def usb_agent_required(view_func):
    """Проверяет Authorization: Bearer <token> и привязывает USBAgent к request.usb_agent.

    В БД хранится только SHA-256 hex от plaintext-токена (см. USBAgent.token_hash);
    plaintext знает только агент, был отдан ему при регистрации.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse({"error": "missing bearer token"}, status=401)

        token = auth_header[7:].strip()
        if not token:
            return JsonResponse({"error": "empty bearer token"}, status=401)

        token_h = hash_token(token)
        try:
            agent = USBAgent.objects.get(token_hash=token_h, is_active=True)
        except USBAgent.DoesNotExist:
            logger.warning("USB agent auth failed: unknown or inactive token (prefix=%s)", token[:8])
            return JsonResponse({"error": "unknown or inactive token"}, status=401)

        # auto_now=True у last_seen обновится при save
        agent.save(update_fields=["last_seen"])
        request.usb_agent = agent
        return view_func(request, *args, **kwargs)

    return wrapper
