# youtube-automator

Pipeline **100% automatizado** para fabricar y publicar vídeos verticales cortos
(YouTube Shorts, Instagram Reels e Instagram Stories) sin servidores ni costes de
infraestructura.

```
Tema (content_bank)
      │
      ▼
Guion  ──►  Locución Edge-TTS  ──►  Subtítulos karaoke (.ASS)
      │
      ▼
Clip de entrada (archivo local / URL / búsqueda)
      │
      ▼
Render FFmpeg (9:16 + subtítulos + mezcla de audio)
      │
      ▼
YouTube Data API v3   +   Instagram Graph API (Reels y Stories)
      │
      ▼
Cola y registro anti-duplicados en git (queue.json / published_log.json)
```

## Requisitos

- Python 3.10+
- FFmpeg (`sudo apt install ffmpeg` en Linux, `brew install ffmpeg` en macOS)
- Una cuenta de Google con canal de YouTube (para el paso de subida)
- (Opcional) Una cuenta de Instagram profesional vinculada a una página de Facebook
- (Opcional) Una API key de Gemini u OpenAI si quieres guiones con IA

## Puesta en marcha (5 pasos)

```bash
# 1. Clona el repositorio
git clone <tu-url-del-repo> youtube-automator
cd youtube-automator

# 2. Instala dependencias
pip install -r requirements.txt

# 3. Ejecuta el asistente (te hace las preguntas clave y deja todo configurado)
python3 setup_wizard.py

# 4. Prueba el pipeline completo SIN publicar nada
python3 autopilot.py --dry-run
# → genera output/<id>/<id>_short.mp4 que puedes revisar

# 5. Cuando esté listo, configura credenciales (docs/) y publica
python3 autopilot.py
```

## Documentación

| Guía | Contenido |
|------|-----------|
| [docs/1_CONFIGURACION.md](docs/1_CONFIGURACION.md) | Asistente y `config.yaml` campo a campo |
| [docs/2_GOOGLE_CLOUD.md](docs/2_GOOGLE_CLOUD.md) | App OAuth + YouTube Data API v3 (subida a YouTube) |
| [docs/3_INSTAGRAM.md](docs/3_INSTAGRAM.md) | Reels y Stories con la Graph API de Meta |
| [docs/4_GITHUB_SECRETS.md](docs/4_GITHUB_SECRETS.md) | Secretos para ejecución automática en GitHub Actions |
| [docs/5_PERSONALIZACION.md](docs/5_PERSONALIZACION.md) | Tu nicho, tus temas, tu layout, tu horario |

## Añade tus temas

Crea un JSON dentro de `content_bank/` (cada elemento es un vídeo). Ejemplo mínimo:

```json
[
  {
    "id": "mi-tema-01",
    "titulo": "Título del vídeo",
    "categoria": "Mi nicho",
    "source": { "tipo": "local", "valor": "assets/mi_clip.mp4" },
    "hook": "Frase de enganche.",
    "desarrollo": "Desarrollo del tema.",
    "datos": "Dato o curiosidad final.",
    "cta": "Pregunta para los comentarios."
  }
]
```

Tipos de `source`:

- `"local"`: ruta a un archivo de vídeo que ya tengas.
- `"url"`: enlace directo a un vídeo (se descarga con yt-dlp).
- `"busqueda"`: término de búsqueda; yt-dlp elige el primer resultado
  (ej: `"busqueda": "timelapse de nubes sin copyright"`).

El esquema completo está en [`content_bank/_schema.json`](content_bank/_schema.json).

## Comandos útiles

```bash
python3 autopilot.py                  # publica el siguiente tema pendiente
python3 autopilot.py --dry-run        # simula todo sin subir nada
python3 autopilot.py --count 3        # procesa hasta 3 temas seguidos
python3 autopilot.py <id> --force     # fuerza un tema concreto
python3 autopilot.py --list           # muestra el estado de la cola
```

## Anti-duplicados

- `queue.json`: cola de trabajo; cada tema está en estado `pendiente`,
  `publicado` o `fallido`.
- `published_log.json`: registro **append-only** de todo lo publicado.
  Es la fuente de verdad: un tema que aparece ahí jamás se vuelve a subir,
  aunque borres o reescribas la cola.
- El workflow de GitHub Actions commitea ambos archivos en cada ejecución.

## Notas importantes

- **Derechos de contenido**: usa material propio o con licencia adecuada para
  YouTube e Instagram. El repo no incluye ningún clip ni audio de terceros.
- **Cuotas de API**: YouTube y Meta tienen cuotas diarias; el autopilot está
  pensado para pocas publicaciones por día.
- **Privacidad**: la primera subida puedes hacerla `"private"` y revisarla
  antes de cambiar a `"public"` en `config.yaml`.
- Los archivos `token.json`, `client_secrets.json` e
  `instagram_credentials.json` están en `.gitignore`: nunca los subas.

## Licencia

MIT
