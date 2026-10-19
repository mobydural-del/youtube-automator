#!/usr/bin/env python3
"""
Subida de shorts a YouTube mediante la YouTube Data API v3 (OAuth 2.0).

Lee las credenciales de:
  - Variables de entorno (YOUTUBE_TOKEN_JSON / CLIENT_SECRETS_JSON) para CI.
  - Archivos locales token.json / client_secrets.json para uso en local.
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional

import config as _config

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _materialize_secret(env_name: str, dest: Path) -> None:
    """Si el archivo no existe pero sí la variable de entorno, lo escribe en disco (CI)."""
    if dest.exists() or not os.environ.get(env_name):
        return
    raw = os.environ[env_name].strip()
    dest.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")


def get_authenticated_service():
    """Devuelve un cliente autenticado de la API de YouTube."""
    if not _GOOGLE_AVAILABLE:
        raise ImportError(
            "Faltan las librerías de Google. Instálalas con: "
            "pip install google-api-python-client google-auth-oauthlib"
        )

    _materialize_secret("YOUTUBE_TOKEN_JSON", _config.TOKEN_FILE)
    _materialize_secret("CLIENT_SECRETS_JSON", _config.CLIENT_SECRETS_FILE)

    creds = None
    if _config.TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_config.TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _config.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise FileNotFoundError(
                f"Falta un token de YouTube válido en {_config.TOKEN_FILE}.\n"
                "Ejecuta `python3 auth_youtube.py` en local para autorizar tu canal."
            )

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_short(video_path: Path, metadata: Dict, privacy_status: Optional[str] = None) -> str:
    """Sube el vídeo a YouTube y devuelve el video_id."""
    yt_cfg = _config.load().get("publicacion", {}).get("youtube", {})
    if privacy_status is None:
        privacy_status = yt_cfg.get("privacidad", "public")

    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata["description"][:5000],
            "tags": metadata["tags"][:50],
            "categoryId": str(yt_cfg.get("categoria_id", "24")),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"Subiendo short a YouTube: {metadata['title']} ({privacy_status})...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Progreso de subida: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Short subido: https://youtube.com/shorts/{video_id}")
    return video_id


def list_channel_titles(max_titles: int = 200) -> set:
    """Devuelve los títulos publicados en el canal (para detectar duplicados)."""
    youtube = get_authenticated_service()
    channel = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_id = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    titles: set = set()
    page_token = None
    while len(titles) < max_titles:
        res = youtube.playlistItems().list(
            part="snippet", playlistId=uploads_id, maxResults=50, pageToken=page_token
        ).execute()
        for item in res.get("items", []):
            title = item.get("snippet", {}).get("title", "").strip()
            if title:
                titles.add(title)
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return titles
