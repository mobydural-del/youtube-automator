#!/usr/bin/env python3
"""
Carga la configuración del proyecto (config.yaml) y expone rutas base.
"""
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"
CONTENT_BANK_DIR = BASE_DIR / "content_bank"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
QUEUE_FILE = BASE_DIR / "queue.json"
PUBLISHED_LOG_FILE = BASE_DIR / "published_log.json"
ASSETS_DIR = BASE_DIR / "assets"
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"
INSTAGRAM_CREDS_FILE = BASE_DIR / "instagram_credentials.json"


def load() -> dict:
    """Lee config.yaml y devuelve un dict. Si falta el archivo, lanza error claro."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"No se encuentra {CONFIG_FILE}. "
            "Ejecuta `python3 setup_wizard.py` para crear tu configuración."
        )
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


for _dir in (OUTPUT_DIR, LOGS_DIR, ASSETS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
