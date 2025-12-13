"""
Helpers to build and read encrypted CBT package (.cqt) files.

The .cqt file is a JSON container with a small header:
{
  "version": 1,
  "salt": "<b64>",
  "nonce": "<b64>",
  "ciphertext": "<b64>"
}
The ciphertext is AES-256-GCM over a UTF-8 JSON payload containing
questions, images (base64), and responses.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def _derive_key(password: str, salt: bytes, iterations: int = 200_000) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_payload(payload: bytes, password: str) -> dict:
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, payload, None)
    return {
        "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_payload(package_bytes: bytes, password: str) -> bytes:
    data = json.loads(package_bytes.decode("utf-8"))
    salt = base64.b64decode(data["salt"])
    nonce = base64.b64decode(data["nonce"])
    ciphertext = base64.b64decode(data["ciphertext"])
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def build_payload(list_name: str, questions: List[Dict[str, Any]]) -> bytes:
    payload = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "list_name": list_name,
        "questions": questions,
        "responses": {},  # student selections stored by question_id
        "evaluation_protection": {},  # salt/hash/iterations for eval password
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def save_cqt(output_path: str, payload: bytes, password: str) -> None:
    package = encrypt_payload(payload, password)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False)


def load_cqt(path: str, password: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = f.read().encode("utf-8")
    plaintext = decrypt_payload(data, password)
    return json.loads(plaintext.decode("utf-8"))


def save_cqt_payload(path: str, payload: Dict[str, Any], password: str) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    save_cqt(path, data, password)


def hash_eval_password(password: str, salt: bytes | None = None, iterations: int = 200_000) -> Dict[str, Any]:
    salt = salt or os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    pwd_hash = kdf.derive(password.encode("utf-8"))
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(pwd_hash).decode("ascii"),
        "iterations": iterations,
    }


def verify_eval_password(password: str, protection: Dict[str, Any]) -> bool:
    if not protection:
        return False
    try:
        salt = base64.b64decode(protection["salt"])
        expected = base64.b64decode(protection["hash"])
        iterations = int(protection.get("iterations", 200_000))
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        kdf.verify(password.encode("utf-8"), expected)
        return True
    except Exception:
        return False
