# 1. Configuración

## El asistente

```bash
python3 setup_wizard.py
```

Te pregunta (y guarda en `config.yaml`):

1. **Identidad**: nombre del canal e idioma del contenido.
2. **Voz**: lista las voces Edge-TTS disponibles para tu idioma y te deja elegir
   (`es-ES-ElviraNeural`, `en-US-AriaNeural`, ...). También la velocidad (`+10%`, ...).
3. **Formato**: resolución (1080x1920 por defecto), FPS, duración objetivo y layout.
4. **Audio**: volumen del audio del clip original y SFX inicial opcional.
5. **Guion**: motor `plantilla` (tú escribes los textos) o `llm` (Gemini u OpenAI).
6. **Publicación**: si subes a YouTube (y con qué privacidad) e Instagram (Reels/Stories).
7. **Autopilot**: vídeos por ejecución, notificación por Issue y horas UTC de publicación.

El asistente también actualiza los `cron` del workflow de GitHub Actions con las
horas que elijas.

## `config.yaml` campo a campo

| Ruta | Qué controla |
|------|--------------|
| `canal.voz` | Voz Edge-TTS (ShortName de `edge-tts --list-voices`) |
| `canal.tasa_voz` | Velocidad de habla (`+0%`, `+15%`...) |
| `video.layout` | `completo` (clip a sangre) o `franjas` (cabecera + clip + subtítulos) |
| `video.duracion_objetivo` | Límite de segundos del clip de entrada |
| `video.subtitulos.*` | Tamaño, colores y posición de los subtítulos karaoke |
| `audio.fondo_volumen` | Volumen del audio original del clip (0.0–1.0) |
| `audio.sfx_intro` | Efecto de sonido al principio (ruta a un archivo) |
| `guion.motor` | `plantilla` o `llm` |
| `guion.llm.proveedor` | `gemini` u `openai` (la API key va por variable de entorno) |
| `publicacion.youtube.privacidad` | `public`, `unlisted` o `private` |
| `publicacion.youtube.categoria_id` | ID de categoría de YouTube (`24` People & Blogs, `27` Educación, `28` Ciencia, `22` Viajes...) |
| `publicacion.instagram.*` | Activar Reels y Stories y sus hashtags por defecto |
| `autopilot.notificar_issue` | Crea un Issue de GitHub con cada publicación |

## Archivos de estado

- `queue.json` — cola de trabajo con el estado de cada tema.
- `published_log.json` — registro append-only de lo publicado (anti-duplicados).
- `output/` — artefactos intermedios y el mp4 final de cada tema.

Todos se versionan (el workflow los commitea tras cada ejecución); `output/` no.
