"""Local launcher for Windows/WSL — starts Beacon with the correct SQLite path."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_root = Path(__file__).resolve().parent
_load_dotenv(_root / ".env")

# On Windows use the local Downloads copy only — never the WSL UNC path (causes locks).
if platform.system() == "Windows":
    _candidates = [
        Path(r"C:\Users\Falcon\Downloads\beacon.db"),
        Path(r"C:\Users\Falcon\Downloads\beacon_prod.db"),
    ]
else:
    _candidates = [
        _root / "beacon_prod.db",
        Path("/mnt/c/Users/Falcon/Downloads/beacon.db"),
    ]
for candidate in _candidates:
    if candidate.exists():
        os.environ["SQLITE_DB_PATH"] = str(candidate)
        break

os.environ.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8003")
os.environ.setdefault("PORT", "8003")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8003"))
    os.chdir(_root)
    sys.path.insert(0, str(_root))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
