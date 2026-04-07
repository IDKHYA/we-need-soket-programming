from __future__ import annotations

import hashlib
import hmac
import secrets


class PasswordHasher:
    PREFIX = "pbkdf2_sha256"

    def hash_password(self, raw_password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("utf-8"),
            200_000,
        ).hex()
        return f"{self.PREFIX}${salt}${digest}"

    def verify(self, raw_password: str, stored_hash: str) -> bool:
        try:
            prefix, salt, digest = stored_hash.split("$", 2)
        except ValueError:
            return False
        if prefix != self.PREFIX:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("utf-8"),
            200_000,
        ).hex()
        return hmac.compare_digest(candidate, digest)
