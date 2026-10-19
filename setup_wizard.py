#!/usr/bin/env python3
"""
Asistente de configuración de youtube-automator.

Te hace una serie de preguntas para montar TU proyecto (nicho, voz, horario,
destinos, motor de guion...) y deja todo listo: config.yaml, cola inicial,
content_bank de ejemplo y checklist de credenciales.

Ejecútalo en la raíz del repo:
  python3 setup_wizard.py
"""
import json
import re
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"
QUEUE_FILE = BASE_DIR / "queue.json"
PUBLISHED_LOG = BASE_DIR / "published_log.json"
BANK_DIR = BASE_DIR / "content_bank"
WORKFLOW_FILE = BASE_DIR / ".github" / "workflows" / "autopilot.yml"

VOICES_CACHE: list = []


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def ask_choice(prompt: str, choices: list, default: str) -> str:
    print(f"{prompt} ({'/'.join(choices)})")
    while True:
        val = ask("Elige", default).lower()
        if val in choices:
            return val
        print(f"  Opción no válida. Escribe una de: {', '.join(choices)}")


def ask_bool(prompt: str, default: bool = True) -> bool:
    d = "s" if default else "n"
    val = ask(f"{prompt} (s/n)", d).lower()
    return val.startswith("s")


def list_voices(lang: str) -> list:
    """Obtiene las voces Edge-TTS disponibles para un idioma (con caché en memoria)."""
    try:
        import asyncio
        import edge_tts
        if not VOICES_CACHE:
            VOICES_CACHE.extend(asyncio.run(edge_tts.list_voices()))
    except Exception as e:
        print(f"(No se pudo obtener la lista de voces: {e})")
        return []
    return [v["ShortName"] for v in VOICES_CACHE if v["ShortName"].lower().startswith(lang.lower())]


def patch_workflow_cron(hours: list) -> None:
    """Reescribe los crons del workflow a partir de las horas elegidas (hora local España peninsular)."""
    if not WORKFLOW_FILE.exists():
        return
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    crons = [f"    - cron: '15 {h} * * *'" for h in hours]
    new_block = "  schedule:\n    # Horario configurado por setup_wizard.py (hora UTC; ajusta para tu zona)\n" + "\n".join(crons)
    content = re.sub(r"  schedule:\n(    - cron:.*\n)+", new_block + "\n", content, count=1)
    WORKFLOW_FILE.write_text(content, encoding="utf-8")


def main() -> None:
    print("=" * 64)
    print(" ASISTENTE DE CONFIGURACIÓN - youtube-automator")
    print("=" * 64)
    print("Responde a las siguientes preguntas para montar tu proyecto.\n")

    cfg = {
        "canal": {},
        "video": {},
        "guion": {"llm": {}},
        "publicacion": {"youtube": {}, "instagram": {}},
        "autopilot": {},
        "audio": {},
    }

    print("--- IDENTIDAD DEL CANAL ---")
    cfg["canal"]["nombre"] = ask("Nombre de tu canal", "Mi Canal de Shorts")
    idioma = ask("Código de idioma del contenido (es, en, fr...)", "es")
    cfg["canal"]["idioma"] = idioma

    print("\n--- VOZ (Edge-TTS) ---")
    voices = list_voices(idioma)
    if voices:
        print("Voces disponibles para tu idioma:")
        for v in voices[:12]:
            print(f"  - {v}")
        default_voice = voices[0]
    else:
        default_voice = "es-ES-ElviraNeural" if idioma == "es" else "en-US-AriaNeural"
    cfg["canal"]["voz"] = ask("Voz a usar (ShortName)", default_voice)
    cfg["canal"]["tasa_voz"] = ask("Velocidad de habla (ej +0%, +10%, -5%)", "+0%")

    print("\n--- FORMATO DEL VÍDEO ---")
    cfg["video"]["ancho"] = int(ask("Ancho en px", "1080"))
    cfg["video"]["alto"] = int(ask("Alto en px", "1920"))
    cfg["video"]["fps"] = int(ask("FPS", "30"))
    cfg["video"]["duracion_objetivo"] = int(ask("Duración objetivo (segundos)", "40"))
    layout = ask_choice("Layout", ["completo", "franjas"], "completo")
    cfg["video"]["layout"] = layout
    cfg["video"]["cabecera_altura"] = int(ask("Alto de cabecera (solo franjas)", "460"))
    cfg["video"]["cabecera_imagen"] = ask("Imagen de cabecera (ruta, opcional)", "")
    cfg["video"]["subtitulos"] = {
        "activos": True,
        "tamaño": 68,
        "palabras_por_pantalla": 4,
        "color_principal": "&H00FFFFFF",
        "color_activo": "&H0000FFFF",
        "color_borde": "&H00000000",
        "margen_inferior": 250,
    }

    print("\n--- AUDIO ---")
    cfg["audio"]["voz_volumen"] = 1.0
    cfg["audio"]["fondo_volumen"] = float(ask("Volumen del audio del clip (0.0-1.0)", "0.25"))
    cfg["audio"]["sfx_intro"] = ask("Efecto de sonido inicial (ruta, opcional)", "")

    print("\n--- GENERACIÓN DE GUION ---")
    motor = ask_choice("Motor de guion", ["plantilla", "llm"], "plantilla")
    cfg["guion"]["motor"] = motor
    if motor == "llm":
        proveedor = ask_choice("Proveedor LLM", ["gemini", "openai"], "gemini")
        cfg["guion"]["llm"]["proveedor"] = proveedor
        default_model = "gemini-2.0-flash" if proveedor == "gemini" else "gpt-4o-mini"
        cfg["guion"]["llm"]["modelo"] = ask("Modelo", default_model)
        env_var = "GEMINI_API_KEY" if proveedor == "gemini" else "OPENAI_API_KEY"
        print(f"  Recuerda exportar {env_var} en tu entorno o añadirlo como secreto de GitHub.")

    print("\n--- PUBLICACIÓN ---")
    cfg["publicacion"]["youtube"]["activo"] = ask_bool("¿Publicar en YouTube?", True)
    cfg["publicacion"]["youtube"]["privacidad"] = ask_choice(
        "Privacidad inicial", ["public", "unlisted", "private"], "private"
    )
    print("  (Se recomienda 'private' las primeras veces y luego cambiar a 'public'.)")
    cfg["publicacion"]["youtube"]["categoria_id"] = ask("ID de categoría de YouTube (24=People & Blogs)", "24")
    cfg["publicacion"]["youtube"]["etiquetas_base"] = ["Shorts"]

    ig_on = ask_bool("¿Publicar en Instagram (Reels/Stories)?", False)
    cfg["publicacion"]["instagram"]["activo"] = ig_on
    if ig_on:
        cfg["publicacion"]["instagram"]["reels"] = ask_bool("¿Publicar también como Reel?", True)
        cfg["publicacion"]["instagram"]["stories"] = ask_bool("¿Publicar también en Stories?", True)
        tags = ask("Hashtags por defecto (separados por espacio)", "shorts viral fyp")
        cfg["publicacion"]["instagram"]["hashtags"] = [t.lstrip("#") for t in tags.split() if t]
    else:
        cfg["publicacion"]["instagram"]["reels"] = False
        cfg["publicacion"]["instagram"]["stories"] = False
        cfg["publicacion"]["instagram"]["hashtags"] = []

    print("\n--- AUTOPILOT ---")
    cfg["autopilot"]["videos_por_ejecucion"] = int(ask("Videos por ejecución", "1"))
    cfg["autopilot"]["notificar_issue"] = ask_bool("¿Crear un Issue de GitHub en cada publicación?", True)
    cfg["autopilot"]["horas_utc"] = [
        int(h) for h in ask("Horas UTC de publicación (separadas por coma, ej 12,18)", "12,18").split(",")
        if h.strip().isdigit()
    ]

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"\nConfiguración guardada en {CONFIG_FILE}")

    if cfg["autopilot"]["horas_utc"]:
        patch_workflow_cron(cfg["autopilot"]["horas_utc"])
        print(f"Horario del workflow actualizado: {cfg['autopilot']['horas_utc']}h UTC")

    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text("[]", encoding="utf-8")
    if not PUBLISHED_LOG.exists():
        PUBLISHED_LOG.write_text("[]", encoding="utf-8")

    sample = BANK_DIR / "ejemplo.json"
    if sample.exists():
        print("\nCola de ejemplo disponible en content_bank/ejemplo.json.")
        print("Sustitúyelo por tus propios temas (ver content_bank/_schema.json).")

    print("\n" + "=" * 64)
    print(" CHECKLIST FINAL")
    print("=" * 64)
    print("""1. [ ] Crea tu app OAuth en Google Cloud y coloca client_secrets.json
      (docs/2_GOOGLE_CLOUD.md)
2. [ ] Ejecuta `python3 auth_youtube.py` para generar token.json
3. [ ] Si usarás Instagram, sigue docs/3_INSTAGRAM.md
4. [ ] Sube los secretos a GitHub (docs/4_GITHUB_SECRETS.md)
5. [ ] Añade tus temas en content_bank/ y prueba:
      python3 autopilot.py --dry-run
6. [ ] Cuando todo funcione, haz el primer push y activa el workflow
      (docs/5_PERSONALIZACION.md)
""")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nAsistente cancelado.")
        sys.exit(1)
