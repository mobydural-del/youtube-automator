#!/usr/bin/env python3
"""
Locución con Edge-TTS y subtítulos karaoke (.ASS) sincronizados palabra a palabra.
"""
import asyncio
from pathlib import Path
from typing import Dict, List

import edge_tts
import edge_tts.communicate as cm
from edge_tts.constants import TRUSTED_CLIENT_TOKEN

import config as _config

DEFAULT_WSS_URL = getattr(
    edge_tts.constants,
    "WSS_URL",
    f"wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken={TRUSTED_CLIENT_TOKEN}",
)
ALT_WSS_URL = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    f"?Ocp-Apim-Subscription-Key={TRUSTED_CLIENT_TOKEN}"
)
WSS_ENDPOINTS = [DEFAULT_WSS_URL, ALT_WSS_URL]


def format_timestamp(seconds: float) -> str:
    """Convierte segundos al formato de timestamp ASS (H:MM:SS.cc)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


async def generate_speech_and_timing(text: str, audio_path: Path, max_retries: int = 3) -> List[Dict]:
    """Genera el audio con Edge-TTS y devuelve los eventos de sincronización por palabra."""
    cfg = _config.load()
    voz = cfg.get("canal", {}).get("voz", "es-ES-ElviraNeural")
    tasa = cfg.get("canal", {}).get("tasa_voz", "+0%")
    last_exception = None

    for attempt in range(1, max_retries + 1):
        current_endpoint = WSS_ENDPOINTS[(attempt - 1) % len(WSS_ENDPOINTS)]
        try:
            cm.WSS_URL = current_endpoint
        except Exception:
            pass

        if audio_path.exists():
            try:
                audio_path.unlink()
            except OSError:
                pass

        events = []
        try:
            communicate = edge_tts.Communicate(text, voz, rate=tasa)
            with open(audio_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        events.append(chunk)

            if not audio_path.exists() or audio_path.stat().st_size == 0:
                raise ValueError("El archivo de audio generado está vacío.")

            words = []
            word_events = [e for e in events if e["type"] == "WordBoundary"]
            if word_events:
                for chunk in word_events:
                    start_sec = chunk["offset"] / 10_000_000
                    dur_sec = chunk["duration"] / 10_000_000
                    words.append(
                        {
                            "word": chunk["text"],
                            "start": start_sec,
                            "end": start_sec + dur_sec,
                            "duration": dur_sec,
                        }
                    )
            else:
                for chunk in events:
                    if chunk["type"] != "SentenceBoundary":
                        continue
                    sentence_start = chunk["offset"] / 10_000_000
                    sentence_dur = chunk["duration"] / 10_000_000
                    raw_words = chunk["text"].split()
                    if not raw_words:
                        continue
                    total_chars = max(1, sum(len(w) for w in raw_words))
                    curr_time = sentence_start
                    for w in raw_words:
                        w_dur = (len(w) / total_chars) * sentence_dur
                        words.append(
                            {"word": w, "start": curr_time, "end": curr_time + w_dur, "duration": w_dur}
                        )
                        curr_time += w_dur

            if not words:
                raise ValueError("No se pudieron extraer eventos de sincronización de texto.")

            try:
                cm.WSS_URL = DEFAULT_WSS_URL
            except Exception:
                pass
            return words

        except Exception as e:
            last_exception = e
            if audio_path.exists():
                try:
                    audio_path.unlink()
                except OSError:
                    pass
            if attempt < max_retries:
                backoff_sec = 2.0 * (2 ** (attempt - 1))
                print(
                    f"[Intento {attempt}/{max_retries}] Error en Edge-TTS ({type(e).__name__}: {e}). "
                    f"Reintentando en {backoff_sec:.1f}s con endpoint alternativo..."
                )
                await asyncio.sleep(backoff_sec)

    try:
        cm.WSS_URL = DEFAULT_WSS_URL
    except Exception:
        pass
    raise RuntimeError(
        f"Fallo crítico en Edge-TTS tras {max_retries} intentos. Último error: {last_exception}"
    ) from last_exception


def generate_ass_subtitles(words: List[Dict], ass_path: Path) -> None:
    """Escribe un archivo .ASS con resaltado karaoke de la palabra activa."""
    cfg = _config.load()
    v = cfg.get("video", {})
    st = v.get("subtitulos", {})
    width = v.get("ancho", 1080)
    height = v.get("alto", 1920)
    font_size = st.get("tamaño", 68)
    words_per_screen = st.get("palabras_por_pantalla", 4)
    primary = st.get("color_principal", "&H00FFFFFF")
    active = st.get("color_activo", "&H0000FFFF")
    outline = st.get("color_borde", "&H00000000")
    margin_v = st.get("margen_inferior", 250)

    ass_header = f"""[Script Info]
Title: Subtitulos dinamicos
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{font_size},{primary},{active},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,6,3,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks: List[List[Dict]] = []
    current_chunk: List[Dict] = []
    for w in words:
        current_chunk.append(w)
        if len(current_chunk) >= words_per_screen or w["word"].endswith((".", "?", "!", ",")):
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        chunks.append(current_chunk)

    events = []
    for chunk in chunks:
        if not chunk:
            continue
        for i, active_w in enumerate(chunk):
            w_start = format_timestamp(active_w["start"])
            w_end = format_timestamp(active_w["end"])
            text_parts = []
            for j, w in enumerate(chunk):
                cleaned_word = w["word"].strip()
                if j == i:
                    text_parts.append(r"{\c" + active + r"\b1\fscx108\fscy108}" + cleaned_word + r"{\r}")
                else:
                    text_parts.append(r"{\c" + primary + r"\b1}" + cleaned_word + r"{\r}")
            events.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,," + " ".join(text_parts))

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(events) + "\n")


def process_voice_and_subtitles(script_text: str, audio_path: Path, ass_path: Path) -> float:
    """Genera audio + subtítulos y devuelve la duración total estimada en segundos."""
    words = asyncio.run(generate_speech_and_timing(script_text, audio_path))
    if not words:
        raise ValueError("No se pudieron extraer palabras del sintetizador de voz.")
    generate_ass_subtitles(words, ass_path)
    return words[-1]["end"] + 0.8
