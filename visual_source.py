#!/usr/bin/env python3
"""
Resuelve y prepara el clip de vídeo de entrada a partir del campo `source` de un tema.

Tipos de fuente:
  - "local":    ruta a un archivo de vídeo en tu disco.
  - "url":      enlace directo a un vídeo (descarga con yt-dlp).
  - "busqueda": término de búsqueda; yt-dlp elige el primer resultado (ej: ytsearch1:...).

El clip se recorta a la duración de la locución (o al límite de config.video.duracion_objetivo).
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import config as _config


def get_media_duration(file_path: Path) -> float:
    """Devuelve la duración en segundos de un archivo multimedia (ffprobe)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(res.stdout.strip())
    except ValueError:
        raise RuntimeError(f"No se pudo obtener la duración de {file_path}: {res.stderr.strip()}")


def _download_url(url: str, dest: Path) -> Path:
    """Descarga un vídeo con yt-dlp en el mejor formato H.264 disponible."""
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("Falta yt-dlp. Instálalo con: pip install yt-dlp")

    dest_noext = dest.with_suffix("")
    ydl_opts = {
        "format": "bv*[vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b",
        "outtmpl": str(dest_noext) + ".%(ext)s",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "max_filesize": 300 * 1024 * 1024,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    candidates = sorted(dest_noext.parent.glob(dest_noext.name + ".*"))
    candidates = [c for c in candidates if c.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if not candidates:
        raise RuntimeError(f"yt-dlp no produjo ningún archivo de vídeo para {url}")
    final = candidates[0]
    if final != dest:
        shutil.move(str(final), str(dest))
    return dest


def _source_query(source: Dict) -> str:
    tipo = source.get("tipo", "local")
    valor = (source.get("valor") or "").strip()
    if tipo == "busqueda":
        return f"ytsearch1:{valor}"
    return valor


def resolve_source(tema: Dict, dest_path: Path, duration_sec: float) -> Path:
    """
    Prepara el clip de entrada en dest_path (mp4) listo para el compositor.
    `duration_sec` es la duración de la locución (se limita por config.video.duracion_objetivo).
    """
    cfg = _config.load()
    max_dur = float(cfg.get("video", {}).get("duracion_objetivo", 45))
    wanted = min(duration_sec, max_dur) + 0.5

    source = tema.get("source") or {}
    tipo = source.get("tipo", "local")
    valor = (source.get("valor") or "").strip()
    offset = float(source.get("offset_segundos") or 0)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if tipo == "local":
        local = Path(valor)
        if not local.is_absolute():
            local = _config.BASE_DIR / local
        if not local.exists():
            raise FileNotFoundError(f"Fuente local no encontrada: {local}")
        raw = local
    elif tipo in ("url", "busqueda"):
        query = _source_query(source)
        raw = dest_path.parent / f"{tema['id']}_descarga{dest_path.suffix}"
        if raw.exists():
            raw.unlink()
        _download_url(query, raw)
    else:
        raise ValueError(f"Tipo de fuente desconocido: {tipo!r} (usa local, url o busqueda)")

    actual = get_media_duration(raw)
    need_cut = offset > 0 or actual > wanted

    if not need_cut:
        if raw != dest_path:
            shutil.copyfile(str(raw), str(dest_path))
        return dest_path

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{offset:.2f}",
        "-t", f"{wanted:.2f}",
        "-i", str(raw),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(dest_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg falló al recortar el clip de entrada: {res.stderr[-600:]}")

    if raw != dest_path and raw.exists() and raw.name.endswith("_descarga" + dest_path.suffix):
        try:
            raw.unlink()
        except OSError:
            pass

    return dest_path


def fetch_header_image(tema: Dict, dest_path: Path) -> Optional[Path]:
    """
    Devuelve una imagen de cabecera si config.video.cabecera_imagen o el tema la definen.
    Si no hay ninguna, devuelve None (el compositor usará layout 'completo').
    """
    cfg = _config.load()
    custom = tema.get("cabecera_imagen") or cfg.get("video", {}).get("cabecera_imagen")
    if not custom:
        return None
    src = Path(custom)
    if not src.is_absolute():
        src = _config.BASE_DIR / src
    if not src.exists():
        print(f"Aviso: imagen de cabecera no encontrada ({src}). Se ignora.")
        return None
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(dest_path))
    return dest_path
