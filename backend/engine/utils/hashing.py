# Supports backend engine runtime behavior for hashing.
import hashlib

def sha256_bytes(b: bytes) -> bytes:
    h = hashlib.sha256()
    h.update(b)
    return h.digest()
