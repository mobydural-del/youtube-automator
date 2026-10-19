#!/usr/bin/env python3
"""
Orquestador principal (autopilot).

Flujo por ejecución:
  1. Carga la cola (queue.json) y el registro anti-duplicados (published_log.json).
  2. Toma el siguiente tema pendiente (sin repetir jamás uno ya publicado).
  3. Genera guion -> locución -> subtítulos -> clip de entrada -> render FFmpeg.
  4. Sube a YouTube e Instagram (Reels y Stories) según config.publicacion.
  5. Registra el resultado y lo guarda en la cola.

Uso:
  python3 autopilot.py                  # publica el siguiente pendiente
  python3 autopilot.py --dry-run        # simula todo sin subir nada
  python3 autopilot.py --count 3        # procesa hasta 3 temas
  python3 autopilot.py <id>             # fuerza un tema concreto de content_bank
  python3 autopilot.py --list           # muestra la cola y sale
"""
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import config as _config
import script_generator
import tts_and_subtitles
import visual_source
import video_composer

BANK_DIR = _config.CONTENT_BANK_DIR


# ------------------------------------------------------------------ banco ----
def load_bank() -> List[Dict]:
    """Carga todos los temas de content_bank/*.json sin duplicar ids."""
    temas: List[Dict] = []
    seen = set()
    for path in sorted(BANK_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Aviso: no se pudo leer {path.name}: {e}")
            continue
        if not isinstance(data, list):
            print(f"Aviso: {path.name} no es una lista JSON, se omite.")
            continue
        for tema in data:
            tid = tema.get("id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            temas.append(tema)
    print(f"Banco cargado: {len(temas)} temas en {len(list(BANK_DIR.glob('*.json')))} archivos.")
    return temas


# ------------------------------------------------------- cola y duplicados ----
_published_ids: Optional[set] = None


def _load_published_ids() -> set:
    global _published_ids
    if _published_ids is None:
        _published_ids = set()
        try:
            with open(_config.PUBLISHED_LOG_FILE, "r", encoding="utf-8") as f:
                for entry in json.load(f):
                    if isinstance(entry, dict) and entry.get("id"):
                        _published_ids.add(entry["id"])
        except FileNotFoundError:
            _config.PUBLISHED_LOG_FILE.write_text("[]", encoding="utf-8")
        except Exception as e:
            print(f"Aviso al leer published_log.json: {e}")
    return _published_ids


def is_published(item: Dict) -> bool:
    tid = item.get("tema", {}).get("id")
    return (
        item.get("estado") == "publicado"
        or bool(item.get("youtube_id"))
        or (tid in _load_published_ids())
    )


def record_published(item: Dict) -> None:
    tid = item.get("tema", {}).get("id")
    if not tid or tid in _load_published_ids():
        return
    entries = []
    if _config.PUBLISHED_LOG_FILE.exists():
        try:
            with open(_config.PUBLISHED_LOG_FILE, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.append({
        "id": tid,
        "titulo": item.get("tema", {}).get("titulo", ""),
        "youtube_id": item.get("youtube_id", ""),
        "youtube_url": item.get("youtube_url", ""),
        "instagram_url": item.get("instagram_url"),
        "instagram_story_id": item.get("instagram_story_id"),
        "publicado_en": item.get("publicado_en", ""),
    })
    with open(_config.PUBLISHED_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    _load_published_ids().add(tid)


def load_queue() -> List[Dict]:
    if not _config.QUEUE_FILE.exists():
        _config.QUEUE_FILE.write_text("[]", encoding="utf-8")
    with open(_config.QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: List[Dict]) -> None:
    with open(_config.QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def replenish_queue(queue: List[Dict]) -> List[Dict]:
    """Añade a la cola solo temas nuevos del banco; nunca reabre publicados."""
    existing = {q.get("tema", {}).get("id") for q in queue}
    added = 0
    for tema in load_bank():
        if tema.get("id") not in existing:
            queue.append({"estado": "pendiente", "tema": tema, "intentos": 0})
            existing.add(tema.get("id"))
            added += 1
    if added:
        print(f"Auto-reposición: {added} temas nuevos incorporados a la cola.")
        save_queue(queue)
    return queue


def heal_queue(queue: List[Dict]) -> List[Dict]:
    """Marca como publicado cualquier tema con youtube_id o presente en el log."""
    healed = 0
    for item in queue:
        tid = item.get("tema", {}).get("id")
        if item.get("estado") != "publicado" and is_published(item):
            item["estado"] = "publicado"
            healed += 1
        if item.get("youtube_id") or tid in _load_published_ids():
            record_published(item)
    if healed:
        print(f"Cola autorreparada: {healed} entradas ya publicadas pasan a 'publicado'.")
        save_queue(queue)
    return queue


def sync_with_channel(queue: List[Dict]) -> List[Dict]:
    """Comprueba el canal en vivo y ciega contra duplicados por título exacto."""
    try:
        import youtube_uploader
        titles = {t.casefold() for t in youtube_uploader.list_channel_titles()}
        synced = 0
        for item in queue:
            t = item.get("tema", {}).get("titulo", "").strip().casefold()
            if t and t in titles and item.get("estado") != "publicado":
                item["estado"] = "publicado"
                record_published(item)
                synced += 1
        if synced:
            print(f"Sincronización con el canal: {synced} vídeos ya publicados blindados.")
            save_queue(queue)
    except Exception as e:
        print(f"Comprobación en vivo del canal omitida: {e}")
    return queue


# --------------------------------------------------------------- publicación ----
def notify_issue(item: Dict) -> None:
    """Crea un Issue de GitHub con el resumen de la publicación (opcional)."""
    if not _config.load().get("autopilot", {}).get("notificar_issue"):
        return
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return
    tema = item.get("tema", {})
    ig_line = f"Instagram Reel: {item.get('instagram_url', '')}\n" if item.get("instagram_url") else ""
    story_line = (
        f"Instagram Story ID: {item.get('instagram_story_id', '')}\n"
        if item.get("instagram_story_id") else ""
    )
    body = (
        "Publicación automática realizada con éxito.\n\n"
        f"Tema: {tema.get('titulo', '')} ({tema.get('categoria', '')})\n"
        f"YouTube: {item.get('youtube_url', '')}\n"
        f"{ig_line}{story_line}"
        f"Fecha: {item.get('publicado_en', '')}\n"
    )
    try:
        import subprocess
        res = subprocess.run(
            ["gh", "issue", "create", "-R", repo,
             "--title", f"Short publicado: {tema.get('titulo', '')}", "--body", body],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if res.returncode == 0:
            print(f"Notificación emitida vía GitHub Issue: {res.stdout.strip()}")
        else:
            print(f"Aviso al emitir el Issue: {res.stderr.strip()}")
    except Exception as e:
        print(f"Aviso al notificar Issue: {e}")


def process_item(item: Dict, dry_run: bool = False) -> Dict:
    """Procesa un tema completo: guion, voz, subtítulos, render y subida."""
    tema = script_generator.ensure_script(item["tema"])
    item["tema"] = tema
    tid = tema["id"]

    print("\n" + "=" * 65)
    print(f"Procesando tema: {tema.get('titulo', tid)} [{tid}]")
    print("=" * 65)

    item_dir = _config.OUTPUT_DIR / tid
    item_dir.mkdir(parents=True, exist_ok=True)
    audio_path = item_dir / "voice.mp3"
    subs_path = item_dir / "subtitles.ass"
    source_path = item_dir / "source.mp4"
    header_path = item_dir / "header.jpg"
    final_path = item_dir / f"{tid}_short.mp4"

    print("\n[1/5] Construyendo guion y metadatos...")
    spoken_text = script_generator.build_spoken_script(tema)
    metadata = script_generator.build_metadata(tema)

    if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
        print(f"Vídeo ya renderizado previamente, reutilizando: {final_path}")
    else:
        print("\n[2/5] Generando locución y subtítulos...")
        duration = tts_and_subtitles.process_voice_and_subtitles(spoken_text, audio_path, subs_path)
        print(f"      Duración: {duration:.1f} segundos")

        print("\n[3/5] Preparando clip de entrada y cabecera...")
        visual_source.resolve_source(tema, source_path, duration)
        header = visual_source.fetch_header_image(tema, header_path)

        print("\n[4/5] Componiendo vídeo vertical...")
        video_composer.compose_short(
            source_video=source_path,
            voice_audio=audio_path,
            subtitles_ass=subs_path,
            output_video=final_path,
            duration_sec=duration,
            header_image=header,
        )

    if dry_run:
        print("\n[5/5] Modo simulación: vídeo listo, NO se sube a ninguna parte.")
        print(f"      Puedes revisarlo en: {final_path}")
        return item

    print("\n[5/5] Publicando...")
    pub = _config.load().get("publicacion", {})

    if pub.get("youtube", {}).get("activo", True):
        import youtube_uploader
        video_id = youtube_uploader.upload_short(final_path, metadata)
        item["youtube_id"] = video_id
        item["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
    else:
        print("YouTube desactivado en config.publicacion.youtube.activo.")

    ig_cfg = pub.get("instagram", {})
    if ig_cfg.get("activo", False):
        import instagram_uploader
        if ig_cfg.get("reels", True) and not item.get("instagram_url"):
            try:
                ig_res = instagram_uploader.upload_reel(final_path, metadata["caption_instagram"])
                item["instagram_id"] = ig_res["id"]
                item["instagram_url"] = ig_res["url"]
            except Exception as e:
                print(f"Aviso al publicar en Instagram Reels: {e}")
        if ig_cfg.get("stories", True) and not item.get("instagram_story_id"):
            try:
                story_res = instagram_uploader.upload_story(final_path)
                item["instagram_story_id"] = story_res["id"]
            except Exception as e:
                print(f"Aviso al publicar en Instagram Stories: {e}")

    item["estado"] = "publicado"
    item["publicado_en"] = datetime.now(timezone.utc).isoformat()
    record_published(item)
    notify_issue(item)

    print(f"\nPublicado con éxito:")
    print(f"  YouTube:  {item.get('youtube_url', '-')}")
    print(f"  Reel:     {item.get('instagram_url', '-')}")
    print(f"  Story id: {item.get('instagram_story_id', '-')}")

    try:
        if source_path.exists():
            source_path.unlink()
    except OSError:
        pass

    return item


def sync_git_state() -> None:
    """Commitea y empuja el estado de la cola en local (en CI lo hace el workflow)."""
    if os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        import subprocess
        subprocess.run(["git", "add", "queue.json", "published_log.json"], check=False)
        diff = subprocess.run(["git", "diff", "--staged", "--quiet"], check=False)
        if diff.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", "chore: sincronizar cola de publicaciones [skip ci]"],
                check=False,
            )
            res = subprocess.run(["git", "push"], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, check=False)
            if res.returncode == 0:
                print("Cambios de cola sincronizados con el remoto.")
            else:
                print(f"Aviso al empujar la cola: {res.stderr.strip()}")
    except Exception as e:
        print(f"Aviso en sincronización git: {e}")


def run_pipeline(count: int = 1, dry_run: bool = False,
                 item_id: Optional[str] = None, force: bool = False) -> None:
    print("=" * 65)
    print(f"Autopilot: procesando hasta {count} vídeo(s)" + (" (SIMULACIÓN)" if dry_run else ""))
    print("=" * 65)

    queue = load_queue()
    queue = heal_queue(queue)
    queue = replenish_queue(queue)
    if not dry_run:
        queue = sync_with_channel(queue)

    published = 0
    attempted = set()
    max_attempts = count + 4

    while published < count and len(attempted) < max_attempts:
        item = None
        if item_id:
            for q in queue:
                if q.get("tema", {}).get("id") == item_id:
                    item = q
                    break
            if item is None:
                print(f"El tema '{item_id}' no está en la cola.")
                return
        else:
            for q in queue:
                tid = q.get("tema", {}).get("id")
                if q.get("estado") == "pendiente" and not is_published(q) and tid not in attempted:
                    item = q
                    break

        if item is None:
            break
        attempted.add(item.get("tema", {}).get("id"))

        if not force and is_published(item):
            print(f"Omitido: '{item['tema'].get('titulo')}' ya fue publicado.")
            item["estado"] = "publicado"
            save_queue(queue)
            if item_id:
                return
            continue

        try:
            item = process_item(item, dry_run=dry_run)
            if not dry_run:
                save_queue(queue)
                sync_git_state()
            published += 1
            item.pop("intentos", None)
            item.pop("ultimo_error", None)
            item.pop("last_attempt", None)
            save_queue(queue)
        except KeyboardInterrupt:
            print("\nInterrupción del usuario.")
            save_queue(queue)
            sys.exit(130)
        except Exception as e:
            print(f"Error procesando {item.get('tema', {}).get('id')}: {e}")
            traceback.print_exc()
            item["intentos"] = item.get("intentos", 0) + 1
            item["ultimo_error"] = str(e)
            item["last_attempt"] = datetime.now(timezone.utc).isoformat()
            if item["intentos"] >= 3:
                item["estado"] = "fallido"
                print(f"El tema '{item.get('tema', {}).get('id')}' se marca como fallido tras 3 intentos.")
            else:
                queue = [q for q in queue if q is not item]
                queue.append(item)
            save_queue(queue)
            if item_id:
                sys.exit(1)

        if item_id:
            return

    print("\n" + "=" * 65)
    if published == 0:
        total_pub = len(_load_published_ids())
        pendientes = sum(1 for q in queue if q.get("estado") == "pendiente")
        if pendientes == 0:
            print("No quedan temas nuevos pendientes en la cola. Añade temas a content_bank/.")
        else:
            print(f"Ningún vídeo completado. Publicados históricos: {total_pub}.")
    else:
        print(f"Proceso finalizado: {published} vídeo(s) {'simulados' if dry_run else 'publicados'}.")
    print("=" * 65)


def show_queue() -> None:
    queue = load_queue()
    for item in queue:
        estado = item.get("estado", "?")
        tid = item.get("tema", {}).get("id", "?")
        titulo = item.get("tema", {}).get("titulo", "")
        url = item.get("youtube_url", "")
        print(f"  [{estado:10}] {tid:30} {titulo[:40]:40} {url}")
    print(f"\nTotal: {len(queue)} entradas | publicados en log: {len(_load_published_ids())}")


if __name__ == "__main__":
    args = sys.argv[1:]
    is_dry = "--dry-run" in args
    force = "--force" in args
    if "--list" in args:
        show_queue()
        sys.exit(0)

    count = 1
    item_id = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--count" and i + 1 < len(args):
            try:
                count = int(args[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        if not arg.startswith("--"):
            item_id = arg
        i += 1

    run_pipeline(count=count, dry_run=is_dry, item_id=item_id, force=force)
