#!/usr/bin/env python3
"""
Genera el guion hablado y los metadatos de publicación a partir de un tema.

Dos modos (config.guion.motor):
  - "plantilla": usa los campos hook/desarrollo/datos/cta del tema tal cual.
  - "llm": si faltan campos, los genera con un modelo (Gemini u OpenAI).
      Requiere GEMINI_API_KEY u OPENAI_API_KEY en el entorno.
"""
import json
import os
from typing import Dict, Optional

import requests

import config as _config

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _cfg() -> dict:
    return _config.load()


def build_spoken_script(tema: Dict) -> str:
    """Concatena hook + desarrollo + datos + cta en un único texto para el TTS."""
    partes = [
        tema.get("hook", "").strip(),
        tema.get("desarrollo", "").strip(),
        tema.get("datos", "").strip(),
        tema.get("cta", "").strip(),
    ]
    texto = " ".join(p for p in partes if p)
    if not texto:
        raise ValueError(
            f"El tema '{tema.get('id')}' no tiene ningún texto de guion. "
            "Rellena hook/desarrollo/datos/cta o usa el motor LLM."
        )
    return texto


def _prompt_llm(tema: Dict, cfg: dict) -> str:
    idioma = cfg.get("canal", {}).get("idioma", "es")
    categoria = tema.get("categoria", "")
    return (
        f"Escribe el guion de un vídeo vertical corto (30-40 segundos) en español ({idioma}). "
        f"Tema: {tema.get('titulo', '')}. Categoría: {categoria}. "
        "Devuelve SOLO un JSON con las claves hook, desarrollo, datos y cta. "
        "hook: frase de enganche en máximo 12 palabras. "
        "desarrollo: 2-3 frases claras. "
        "datos: una curiosidad sorprendente en 1-2 frases. "
        "cta: pregunta corta que invite a comentar. "
        "Sin emojis, sin comillas escapadas, tono cercano y directo."
    )


def _call_llm(prompt: str, cfg: dict) -> Dict:
    guion_cfg = cfg.get("guion", {}).get("llm", {})
    proveedor = guion_cfg.get("proveedor", "gemini")
    modelo = guion_cfg.get("modelo", "")

    if proveedor == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY para el motor LLM.")
        if not modelo:
            modelo = "gemini-2.0-flash"
        url = _GEMINI_URL.format(model=modelo)
        r = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=90,
        )
        r.raise_for_status()
        texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY para el motor LLM.")
        if not modelo:
            modelo = "gpt-4o-mini"
        r = requests.post(
            _OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=90,
        )
        r.raise_for_status()
        texto = r.json()["choices"][0]["message"]["content"]

    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {"hook": texto, "desarrollo": "", "datos": "", "cta": ""}


def ensure_script(tema: Dict) -> Dict:
    """Si el motor es LLM y faltan campos del guion, los rellena. Devuelve el tema (posiblemente enriquecido)."""
    cfg = _cfg()
    if cfg.get("guion", {}).get("motor") != "llm":
        return tema
    if tema.get("hook") and tema.get("desarrollo"):
        return tema
    campos = _call_llm(_prompt_llm(tema, cfg), cfg)
    for k in ("hook", "desarrollo", "datos", "cta"):
        if not tema.get(k) and campos.get(k):
            tema[k] = campos[k].strip()
    return tema


def build_metadata(tema: Dict) -> Dict:
    """Devuelve title, description y tags optimizados para YouTube e Instagram."""
    cfg = _cfg()
    yt = cfg.get("publicacion", {}).get("youtube", {})
    ig = cfg.get("publicacion", {}).get("instagram", {})
    titulo = tema.get("titulo", tema.get("id", "Short"))
    categoria = tema.get("categoria", "")

    title = tema.get("titulo_youtube") or f"{titulo} #Shorts"
    if categoria and len(title) < 90:
        title = f"{titulo} | {categoria} #Shorts"

    hashtags = " ".join(f"#{h}" for h in tema.get("hashtags", []))
    ig_hashtags = " ".join(f"#{h}" for h in ig.get("hashtags", []))
    base_tags = yt.get("etiquetas_base", ["Shorts"])

    body_parts = [
        tema.get("hook", ""),
        tema.get("desarrollo", ""),
        tema.get("datos", ""),
        tema.get("cta", ""),
    ]
    body = "\n\n".join(p for p in body_parts if p).strip()

    description = tema.get("descripcion_youtube") or body
    if hashtags:
        description = f"{description}\n\n{hashtags}"
    if ig_hashtags:
        description = f"{description} {ig_hashtags}"
    description = description.strip()[:5000]

    tags = list({titulo, categoria, *base_tags, *tema.get("hashtags", [])})
    tags = [t for t in tags if t][:50]

    caption_ig = f"{titulo}\n\n{body}\n\n{ig_hashtags}".strip()[:2100]

    return {
        "title": title[:100],
        "description": description,
        "tags": tags,
        "caption_instagram": caption_ig,
    }
