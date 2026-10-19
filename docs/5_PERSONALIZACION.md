# 5. Personalización

## Tu nicho y tus temas

Todo empieza en `content_bank/`. Un tema = un vídeo. Copia `ejemplo.json`,
renómbralo a tu nicho (ej: `ciencia.json`, `cocina.json`) y rellena tus temas
siguiendo [`content_bank/_schema.json`](../content_bank/_schema.json).

Puedes repartirlos en varios archivos JSON; el autopilot los carga todos.

Si el motor de guion es `llm`, puedes dejar vacíos `hook`/`desarrollo`/`datos`/`cta`
y el modelo los generará a partir de `titulo` y `categoria`.

## Layout del vídeo

En `config.yaml → video.layout`:

- **`completo`** (recomendado): el clip de entrada cubre todo el lienzo vertical;
  los subtítulos se superponen abajo.
- **`franjas`**: fondo desenfocado + imagen de cabecera arriba (`cabecera_imagen`)
  + clip centrado + subtítulos abajo. Útil si quieres una marca visual constante.

Los subtítulos son karaoke (la palabra activa se resalta). Ajusta tamaño, colores
y margen en `video.subtitulos`.

## Voces

```bash
edge-tts --list-voices | grep es-
```

Copia el `ShortName` a `config.yaml → canal.voz`. Ajusta `tasa_voz` si tuena lenta.

## Horario

Las horas viven en `.github/workflows/autopilot.yml` (bloque `schedule`). Son en
**UTC**. Ejemplo: 12:15 y 18:15 UTC. El asistente las escribe por ti; también
puedes editarlas a mano. GitHub puede retrasar unos minutos los cron muy
redondos, por eso se usa el minuto 15.

## Categoría de YouTube

`publicacion.youtube.categoria_id` (texto): por ejemplo

- `24` People & Blogs
- `27` Education
- `28` Science & Technology
- `22` Travel & Events
- `26` Howto & Style
- `20` Gaming

## Idempotencia y control

- Cambia `publicacion.youtube.privacidad` a `private` mientras pruebas.
- `python3 autopilot.py <id> --force` reproduce un tema concreto aunque ya
  esté publicado (uso manual).
- Si un tema falla 3 veces seguidas se marca `fallido` y no bloquea la cola.
- `autopilot.notificar_issue: true` crea un Issue de GitHub con cada publicación
  (útil como notificación gratuita por email si tienes activas las notificaciones
  de Issues).

## Ampliar el pipeline

El código está separado por fases, puedes sustituir cualquiera:

- `script_generator.py` — guion y metadatos.
- `tts_and_subtitles.py` — voz y subtítulos.
- `visual_source.py` — de dónde sale el clip de entrada.
- `video_composer.py` — render final con FFmpeg.
- `youtube_uploader.py` / `instagram_uploader.py` — destinos.
- `autopilot.py` — orquestación y cola.

Mantén la interfaz de cada función y el resto del pipeline sigue funcionando.
