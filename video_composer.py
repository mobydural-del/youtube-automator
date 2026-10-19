#!/usr/bin/env python3
"""
Compositor FFmpeg del vídeo vertical final (por defecto 1080x1920).

Layouts disponibles (config.video.layout):
  - "completo": el clip de entrada cubre todo el lienzo (escala + crop) y los
                subtítulos se superponen abajo. Es el más simple y recomendado.
  - "franjas":  fondo desenfocado del propio clip + imagen de cabecera arriba
                + clip de entrada centrado + subtítulos abajo.

Mezcla de audio: locución (voz) + audio original del clip atenuado + SFX opcional.
Todos los inputs se registran con su rol para que los índices del filter_complex
siempre sean correctos.
"""
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import config as _config


def has_audio_stream(file_path: Path) -> bool:
    """Comprueba si el archivo tiene una pista de audio utilizable."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(file_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return "audio" in res.stdout.lower()


def _escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _build_inputs(
    source_video: Path,
    header_image: Optional[Path],
    voice_audio: Path,
    sfx_file: Optional[Path],
) -> Tuple[List[str], dict]:
    """Devuelve (argv_inputs, roles) donde roles mapea rol -> índice ffmpeg."""
    argv: List[str] = []
    roles: dict = {}

    def add(path: Path, *, loop: bool = False, stream_loop: bool = False):
        idx = len(roles)
        if stream_loop:
            argv.extend(["-stream_loop", "-1"])
        elif loop:
            argv.extend(["-loop", "1"])
        argv.extend(["-i", str(path)])
        return idx

    roles["source"] = add(source_video, stream_loop=True)
    if header_image is not None:
        roles["header"] = add(header_image, loop=True)
    if sfx_file is not None:
        roles["sfx"] = add(sfx_file)
    roles["voice"] = add(voice_audio)
    if has_audio_stream(source_video):
        roles["source_audio"] = add(source_video)

    return argv, roles


def compose_short(
    source_video: Path,
    voice_audio: Path,
    subtitles_ass: Path,
    output_video: Path,
    duration_sec: float,
    header_image: Optional[Path] = None,
) -> Path:
    """Renderiza el vídeo final con FFmpeg y lo escribe en output_video."""
    cfg = _config.load()
    v = cfg.get("video", {})
    a = cfg.get("audio", {})

    width = v.get("ancho", 1080)
    height = v.get("alto", 1920)
    fps = v.get("fps", 30)
    layout = v.get("layout", "completo")
    header_h = v.get("cabecera_altura", 460)
    subtitles_on = v.get("subtitulos", {}).get("activos", True)

    voice_vol = a.get("voz_volumen", 1.0)
    bg_vol = a.get("fondo_volumen", 0.25)
    sfx_path = a.get("sfx_intro") or ""
    sfx_file = Path(sfx_path) if sfx_path else None
    if sfx_file and not sfx_file.is_absolute():
        sfx_file = _config.BASE_DIR / sfx_file
    if sfx_file and not sfx_file.exists():
        print(f"Aviso: sfx_intro no encontrado ({sfx_file}). Se omite.")
        sfx_file = None

    use_header = layout == "franjas" and header_image is not None and header_image.exists()

    inputs, roles = _build_inputs(source_video, header_image if use_header else None,
                                  voice_audio, sfx_file)

    filters: List[str] = []
    dur = f"{duration_sec:.2f}"

    if use_header:
        video_area_h = height - header_h
        filters += [
            f"[{roles['source']}:v]trim=duration={dur},setpts=PTS-STARTPTS,"
            f"scale={width}:{video_area_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{video_area_h}[vg]",
            f"[{roles['source']}:v]trim=end_frame=1,setpts=PTS-STARTPTS,"
            f"loop=size=1:loop=-1:start=0,trim=duration={dur},setpts=PTS-STARTPTS,"
            f"scale={width}:{height},boxblur=luma_radius=28:luma_power=2,eq=brightness=-0.25:contrast=0.85[bg]",
            f"[vg][bg]overlay=0:{header_h}[vcore]",
            f"[{roles['header']}:v]scale={width}:{header_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{header_h}[hdr]",
            "[vcore][hdr]overlay=0:0[vhead]",
        ]
        last_v = "[vhead]"
    else:
        filters += [
            f"[{roles['source']}:v]trim=duration={dur},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[vbase]",
        ]
        last_v = "[vbase]"

    if subtitles_on:
        escaped_ass = _escape_filter_path(subtitles_ass)
        filters.append(f"{last_v}subtitles='{escaped_ass}'[vout]")
    else:
        filters.append(f"{last_v}null[vout]")

    audio_labels: List[str] = []
    if "source_audio" in roles:
        filters.append(
            f"[{roles['source_audio']}:a]aformat=channel_layouts=stereo,atrim=duration={dur},"
            f"asetpts=PTS-STARTPTS,volume={bg_vol}[abg]"
        )
        audio_labels.append("[abg]")
    if "sfx" in roles:
        filters.append(f"[{roles['sfx']}:a]aformat=channel_layouts=stereo,volume=0.9[asfx]")
        audio_labels.append("[asfx]")
    filters.append(
        f"[{roles['voice']}:a]aformat=channel_layouts=stereo,adelay=450|450,"
        f"volume={voice_vol}[avoice]"
    )
    audio_labels.append("[avoice]")

    if len(audio_labels) == 1:
        filters.append(f"{audio_labels[0]}acopy[aout]")
    else:
        filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=first:dropout_transition=0[aout]"
        )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-map", "[aout]",
        "-t", dur,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-movflags", "+faststart",
        str(output_video),
    ]

    print(f"Renderizando short vertical ({width}x{height}, layout {layout})...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Fallo al renderizar con FFmpeg: {result.stderr[-800:]}")

    print(f"Vídeo generado: {output_video} ({output_video.stat().st_size / (1024 * 1024):.2f} MB)")
    return output_video
