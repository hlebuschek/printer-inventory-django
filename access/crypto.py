"""
Утилиты шифрования для хранения секретных данных (API-токены и т.д.).
Использует Fernet (AES-128-CBC) с ключом на основе SECRET_KEY.
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet():
    """Создаёт Fernet на основе SECRET_KEY проекта."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_token(plaintext: str) -> str:
    """Шифрует строку и возвращает base64-строку."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Расшифровывает base64-строку обратно."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
