import hashlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client, TestCase

URL = "https://printer.example/status.html"


class ProxyPageHeaderTests(TestCase):
    """Чужой HTML отдаётся с нашего origin, поэтому обязан приходить в песочнице."""

    def setUp(self):
        user = get_user_model().objects.create_user(username="viewer", password="p")
        for codename in ("access_inventory_app", "view_web_parsing"):
            user.user_permissions.add(Permission.objects.get(codename=codename))

        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

        # Отвечаем из кэша, чтобы не ходить в сеть
        cache_key = hashlib.md5(f"{URL}_".encode()).hexdigest()
        cache.set(f"proxy_page_{cache_key}", "<html><body>hi</body></html>", 60)
        self.addCleanup(cache.delete, f"proxy_page_{cache_key}")

    def test_response_is_sandboxed(self):
        response = self.client.get("/inventory/api/web-parser/proxy-page/", {"url": URL})

        self.assertEqual(response.status_code, 200)
        csp = response["Content-Security-Policy"]
        self.assertIn("sandbox", csp)
        # allow-same-origin вернуло бы документу наш origin вместе с куками
        self.assertNotIn("allow-same-origin", csp)
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
