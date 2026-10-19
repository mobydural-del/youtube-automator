#!/usr/bin/env python3
"""
Subida directa a Instagram (Reels e Stories) con la Meta Graph API.

La subida es resumible (upload_type=resumable): el vídeo viaja en binario
desde tu máquina o runner de CI directamente a Meta, sin buckets intermedios.

Credenciales:
  - Variables de entorno INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_ACCOUNT_ID (CI).
  - O archivo local instagram_credentials.json:
      {"access_token": "...", "instagram_account_id": "..."}
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

import config as _config

GRAPH_API_VERSION = "v21.0"
BASE_GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def load_credentials() -> Dict[str, str]:
    """Carga credenciales desde variables de entorno o el archivo local."""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")
    if token and account_id:
        return {"access_token": token.strip(), "instagram_account_id": account_id.strip()}

    if _config.INSTAGRAM_CREDS_FILE.exists():
        with open(_config.INSTAGRAM_CREDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "access_token": data.get("access_token", ""),
            "instagram_account_id": data.get("instagram_account_id", ""),
        }

    raise FileNotFoundError(
        "No hay credenciales de Instagram. Usa INSTAGRAM_ACCESS_TOKEN / "
        "INSTAGRAM_ACCOUNT_ID o crea instagram_credentials.json (ver docs/3_INSTAGRAM.md)."
    )


def _resumable_upload(video_path: Path, media_type: str, caption: Optional[str] = None) -> str:
    """Sube un vídeo a Instagram como REELS o STORIES y devuelve el media_id."""
    creds = load_credentials()
    token = creds["access_token"]
    account_id = creds["instagram_account_id"]
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")
    file_size = video_path.stat().st_size

    init_data = {
        "media_type": media_type,
        "upload_type": "resumable",
        "access_token": token,
    }
    if caption and media_type == "REELS":
        init_data["caption"] = caption
        init_data["share_to_feed"] = "true"

    init_res = requests.post(f"{BASE_GRAPH_URL}/{account_id}/media", data=init_data, timeout=60)
    if init_res.status_code != 200:
        raise RuntimeError(f"Error creando contenedor {media_type}: {init_res.text}")
    init_json = init_res.json()
    container_id = init_json["id"]
    upload_uri = init_json["uri"]

    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
    }
    with open(video_path, "rb") as f:
        upload_res = requests.post(upload_uri, headers=headers, data=f, timeout=600)
    if upload_res.status_code not in (200, 201):
        raise RuntimeError(f"Error transfiriendo vídeo a Meta: {upload_res.text}")

    for _ in range(40):
        time.sleep(5)
        st_res = requests.get(
            f"{BASE_GRAPH_URL}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        )
        if st_res.status_code == 200:
            code = st_res.json().get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise RuntimeError(f"Meta reportó fallo en transcodificación: {st_res.text}")
    else:
        raise TimeoutError(f"Tiempo agotado esperando el procesamiento de {media_type}")

    pub_res = requests.post(
        f"{BASE_GRAPH_URL}/{account_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    if pub_res.status_code != 200:
        raise RuntimeError(f"Error publicando {media_type}: {pub_res.text}")
    return pub_res.json()["id"]


def upload_reel(video_path: Path, caption: str) -> Dict[str, str]:
    """Publica un Reel en el feed de Instagram y devuelve {id, url}."""
    print(f"[Instagram Reels] Publicando: {caption.splitlines()[0] if caption else 'Reel'}...")
    media_id = _resumable_upload(Path(video_path), "REELS", caption=caption)
    url = f"https://www.instagram.com/reel/{media_id}/"
    print(f"[Instagram Reels] Publicado: {url}")
    return {"id": media_id, "url": url}


def upload_story(video_path: Path) -> Dict[str, str]:
    """Publica el clip en las Historias de Instagram y devuelve {id, url}."""
    print("[Instagram Stories] Publicando historia...")
    media_id = _resumable_upload(Path(video_path), "STORIES")
    print(f"[Instagram Stories] Publicado (media id {media_id})")
    return {"id": media_id, "url": "https://www.instagram.com/stories/"}
