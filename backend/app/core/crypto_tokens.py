"""Encrypt sensitive tokens at rest using Fernet derived from SECRET_KEY."""

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    from app.config import get_settings

    digest = hashlib.sha256(get_settings().secret_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_str(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_str(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
