from django.test import SimpleTestCase

from access.crypto import decrypt_token, encrypt_token


class CryptoTests(SimpleTestCase):
    def test_roundtrip(self):
        token = "super-secret-api-token-123"
        self.assertEqual(decrypt_token(encrypt_token(token)), token)

    def test_ciphertext_differs_from_plaintext(self):
        token = "hello"
        self.assertNotEqual(encrypt_token(token), token)

    def test_unicode_roundtrip(self):
        token = "токен-Тест-✓"
        self.assertEqual(decrypt_token(encrypt_token(token)), token)

    def test_encrypt_is_nondeterministic(self):
        # Fernet включает timestamp+IV → шифртексты разные, но расшифровка совпадает.
        a, b = encrypt_token("same"), encrypt_token("same")
        self.assertNotEqual(a, b)
        self.assertEqual(decrypt_token(a), decrypt_token(b))
