# 4. Secretos de GitHub (ejecución automática)

El workflow (`.github/workflows/autopilot.yml`) necesita tus credenciales como
**secrets** del repositorio.

## Subir los secretos

Con la [CLI de GitHub (`gh`)](https://cli.github.com/):

```bash
# YouTube (obligatorios para subir a YouTube)
gh secret set CLIENT_SECRETS_JSON < client_secrets.json
gh secret set YOUTUBE_TOKEN_JSON < token.json

# Instagram (solo si activaste Instagram en config.yaml)
gh secret set INSTAGRAM_ACCESS_TOKEN
gh secret set INSTAGRAM_ACCOUNT_ID

# LLM (solo si el motor de guion es "llm")
gh secret set GEMINI_API_KEY      # o OPENAI_API_KEY
```

O por la web: **Settings → Secrets and variables → Actions → New repository secret**,
pegando el contenido completo de cada archivo.

## Lista de secretos

| Secreto | Origen | Necesario |
|---------|--------|-----------|
| `CLIENT_SECRETS_JSON` | `client_secrets.json` de Google Cloud | Sí (YouTube) |
| `YOUTUBE_TOKEN_JSON` | `token.json` generado por `auth_youtube.py` | Sí (YouTube) |
| `INSTAGRAM_ACCESS_TOKEN` | Token de página (Meta) | Si usas Instagram |
| `INSTAGRAM_ACCOUNT_ID` | ID de la cuenta IG profesional | Si usas Instagram |
| `GEMINI_API_KEY` | Google AI Studio | Solo motor LLM con Gemini |
| `OPENAI_API_KEY` | platform.openai.com | Solo motor LLM con OpenAI |

## Probar el workflow

1. Pestaña **Actions** del repo → **Shorts Autopilot** → **Run workflow**.
2. Marca `dry_run: true` para la primera prueba (no publica nada).
3. Revisa los logs; si todo va bien, ejecútalo sin `dry_run`.

## Commits automáticos

Tras cada ejecución el workflow commitea `queue.json` y `published_log.json`
para que el estado de la cola sobreviva entre corridas. No borres esos commits.
