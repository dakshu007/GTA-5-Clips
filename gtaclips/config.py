"""Paths and process-level configuration (things that must be known before the DB opens)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
FONTS_DIR = PACKAGE_DIR / "assets" / "fonts"

DATA_DIR = Path(os.environ.get("GTACLIPS_DATA", Path.cwd() / "data")).resolve()
DB_PATH = DATA_DIR / "gtaclips.sqlite"
BUFFERS_DIR = DATA_DIR / "buffers"
CLIPS_DIR = DATA_DIR / "clips"
UPLOADS_DIR = DATA_DIR / "uploads"
MODELS_DIR = DATA_DIR / "models"

HOST = os.environ.get("GTACLIPS_HOST", "127.0.0.1")
PORT = int(os.environ.get("GTACLIPS_PORT", "8000"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, BUFFERS_DIR, CLIPS_DIR, UPLOADS_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def secret_key() -> str:
    """Per-install secret used to sign session cookies and media links."""
    ensure_dirs()
    path = DATA_DIR / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()
