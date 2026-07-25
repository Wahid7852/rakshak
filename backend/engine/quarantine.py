# Quarantine storage for files flagged malicious - encrypted at rest, integrity-checked.
from __future__ import annotations

import hashlib, hmac, json, os, stat, time, uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from .utils.hashing import sha256_bytes

DEFAULT_QUARANTINE_DIR = Path(__file__).resolve().parents[2] / "quarantine"


@dataclass
class QuarantineEntry:
    quarantine_id: str
    original_path: str
    quarantine_file: str
    reason: str
    sha256: str
    timestamp: float = field(default_factory=time.time)


class QuarantineManager:
    """Moves flagged files into encrypted, integrity-checked storage.

    The original is only ever removed after the encrypted copy has been
    written and verified - quarantining a file can never result in silent
    data loss (unlike the write-nothing-then-delete bug this replaces).
    """

    def __init__(self, quarantine_dir: str | Path | None = None):
        self.dir = Path(quarantine_dir) if quarantine_dir is not None else DEFAULT_QUARANTINE_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.dir / "quarantine_db.json"
        self._key_path = self.dir / "key.bin"
        self._key = self._load_or_create_key()
        self._fernet = Fernet(self._key)
        self._db: Dict[str, QuarantineEntry] = self._load_db()

    # ---------- setup ----------

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes()
        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        os.chmod(self._key_path, stat.S_IRUSR | stat.S_IWUSR)
        return key

    def _hmac_db(self, raw: bytes) -> str:
        return hmac.new(self._key, raw, hashlib.sha256).hexdigest()

    def _load_db(self) -> Dict[str, QuarantineEntry]:
        if not self._db_path.exists():
            return {}
        try:
            raw = self._db_path.read_bytes()
            payload = json.loads(raw.decode())
            entries_raw = payload.get("entries", {})
            signature = payload.get("hmac", "")
            expected = self._hmac_db(json.dumps(entries_raw, sort_keys=True).encode())
            if not hmac.compare_digest(signature, expected):
                raise ValueError("quarantine db failed integrity check (tampered or corrupt)")
            return {k: QuarantineEntry(**v) for k, v in entries_raw.items()}
        except Exception:
            return {}

    def _save_db(self) -> None:
        entries_raw = {k: asdict(v) for k, v in self._db.items()}
        body = json.dumps(entries_raw, sort_keys=True).encode()
        payload = {"entries": entries_raw, "hmac": self._hmac_db(body)}
        self._db_path.write_text(json.dumps(payload, indent=2))

    # ---------- operations ----------

    def quarantine_file(self, file_path: str | Path, reason: str) -> Optional[QuarantineEntry]:
        src = Path(file_path)
        if not src.is_file():
            return None

        data = src.read_bytes()
        digest = sha256_bytes(data).hex()
        qid = uuid.uuid4().hex
        dest = self.dir / f"{qid}.enc"

        token = self._fernet.encrypt(data)
        dest.write_bytes(token)

        # verify the encrypted copy round-trips before touching the original
        if self._fernet.decrypt(dest.read_bytes()) != data:
            dest.unlink(missing_ok=True)
            return None

        entry = QuarantineEntry(
            quarantine_id=qid,
            original_path=str(src.resolve()),
            quarantine_file=dest.name,
            reason=reason,
            sha256=digest,
        )
        self._db[qid] = entry
        self._save_db()

        src.unlink()
        return entry

    def restore_file(self, quarantine_id: str, dest_path: Optional[str | Path] = None) -> bool:
        entry = self._db.get(quarantine_id)
        if entry is None:
            return False

        target = Path(dest_path) if dest_path else Path(entry.original_path)
        if target.exists():
            return False

        src = self.dir / entry.quarantine_file
        if not src.exists():
            return False

        try:
            data = self._fernet.decrypt(src.read_bytes())
        except InvalidToken:
            return False

        if sha256_bytes(data).hex() != entry.sha256:
            return False

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        src.unlink()
        del self._db[quarantine_id]
        self._save_db()
        return True

    def remove_file(self, quarantine_id: str) -> bool:
        entry = self._db.get(quarantine_id)
        if entry is None:
            return False
        (self.dir / entry.quarantine_file).unlink(missing_ok=True)
        del self._db[quarantine_id]
        self._save_db()
        return True

    def list_quarantined(self) -> List[QuarantineEntry]:
        return list(self._db.values())

    def is_quarantined(self, file_path: str | Path) -> bool:
        target = str(Path(file_path).resolve())
        return any(e.original_path == target for e in self._db.values())
