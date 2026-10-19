#!/usr/bin/env python3
"""
Autenticación OAuth 2.0 con Google Cloud para subir a YouTube.

Ejecútalo UNA vez en local:
  1. Crea una app OAuth en Google Cloud (ver docs/2_GOOGLE_CLOUD.md).
  2. Coloca el JSON descargado como client_secrets.json en la raíz del repo.
  3. Ejecuta: python3 auth_youtube.py
  4. Sigue el flujo en el navegador (si tienes canal de marca, elígelo).
  5. Se genera token.json; súbelo como secreto de GitHub (docs/4_GITHUB_SECRETS.md).
"""
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config as _config
from youtube_uploader import SCOPES


def main() -> None:
    print("=" * 60)
    print("AUTENTICACIÓN GOOGLE / YOUTUBE")
    print("=" * 60)

    if not _config.CLIENT_SECRETS_FILE.exists():
        print(f"No se encuentra {_config.CLIENT_SECRETS_FILE}.")
        print("Descarga el JSON de tu app OAuth desde Google Cloud y colócalo ahí.")
        sys.exit(1)

    print("\nPasos en la pantalla de Google:")
    print("1. Elige la cuenta de Google vinculada a tu canal.")
    print("2. Si aparece el selector de canal de marca, elige tu canal (no tu cuenta personal).")
    print("3. Concede los permisos solicitados.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(_config.CLIENT_SECRETS_FILE), SCOPES)
    try:
        creds = flow.run_local_server(port=8090, prompt="select_account consent", access_type="offline")
    except Exception as e:
        print(f"Puerto 8090 no disponible ({e}); usando puerto aleatorio...")
        creds = flow.run_local_server(port=0, prompt="select_account consent", access_type="offline")

    _config.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nToken guardado en: {_config.TOKEN_FILE}")

    try:
        youtube = build("youtube", "v3", credentials=creds)
        res = youtube.channels().list(mine=True, part="snippet").execute()
        items = res.get("items", [])
        if items:
            print(f"Canal vinculado: '{items[0]['snippet']['title']}' (ID: {items[0]['id']})")
            print("Si este NO es tu canal, vuelve a ejecutar el script y elige el correcto.")
        else:
            print("Aviso: no se encontró un canal asociado a esta cuenta.")
    except Exception as e:
        print(f"Aviso al comprobar el canal: {e}")

    print("\nSiguiente paso: sube el token como secreto de GitHub (docs/4_GITHUB_SECRETS.md):")
    print("  gh secret set YOUTUBE_TOKEN_JSON < token.json")


if __name__ == "__main__":
    main()
