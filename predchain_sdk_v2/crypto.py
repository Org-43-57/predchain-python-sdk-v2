from __future__ import annotations

import base64
import hashlib

from coincurve import PrivateKey


def normalize_hex(value: str) -> str:
    raw = value.strip()
    if raw.startswith(("0x", "0X")):
        raw = raw[2:]
    return raw


def decode_hex(value: str) -> bytes:
    raw = normalize_hex(value)
    if len(raw) % 2 == 1:
        raw = f"0{raw}"
    return bytes.fromhex(raw)


def encode_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def compressed_pubkey_from_private_key_hex(private_key_hex: str) -> bytes:
    return PrivateKey(decode_hex(private_key_hex)).public_key.format(compressed=True)


def sign_direct(private_key_hex: str, sign_doc_bytes: bytes) -> bytes:
    private_key = PrivateKey(decode_hex(private_key_hex))
    signature = private_key.sign_recoverable(sign_doc_bytes, hasher=hashlib.sha256)
    return signature[:64]
