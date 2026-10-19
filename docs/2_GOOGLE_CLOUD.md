# 2. Google Cloud y YouTube (subida automática)

Para subir vídeos a YouTube necesitas una **app de automatización** (cliente OAuth)
en Google Cloud y un token de tu cuenta. Se hace **una sola vez**.

## Paso 1 — Proyecto en Google Cloud

1. Entra en <https://console.cloud.google.com/>.
2. Crea un proyecto nuevo (ej: `mi-shorts-automator`).

## Paso 2 — Activar la YouTube Data API v3

1. En el menú, ve a **APIs y servicios → Biblioteca**.
2. Busca **YouTube Data API v3** y pulsa **Activar**.

## Paso 3 — Pantalla de consentimiento OAuth

1. **APIs y servicios → Pantalla de consentimiento OAuth**.
2. Tipo de usuario: **Externo** (aunque solo lo uses tú).
3. Rellena nombre de app, email de soporte y dominio (puede ser el del repo).
4. En **Usuarios de prueba** añade el email de la cuenta Google que tiene el canal.
   (Si publicas como app "producción", Google limita el acceso a esos usuarios.)

## Paso 4 — Crear el cliente OAuth (app de escritorio)

1. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**.
2. Tipo de aplicación: **Aplicación de escritorio**.
3. Descarga el JSON y guárdalo en la raíz del repo como:

   ```
   client_secrets.json
   ```

   Ese archivo está en `.gitignore`; nunca lo subas al repo.

## Paso 5 — Generar tu token

```bash
python3 auth_youtube.py
```

1. Se abre el navegador: elige la cuenta de Google de tu canal.
2. **Importante**: si te pregunta por cuenta o *canal de marca*, elige tu canal,
   no tu cuenta personal.
3. Al terminar se crea `token.json` (también en `.gitignore`).

Comprueba en pantalla que el canal vinculado es el correcto.

## Paso 6 — Lleva el token a GitHub Actions

Sigue [4_GITHUB_SECRETS.md](4_GITHUB_SECRETS.md) para subir:

- `CLIENT_SECRETS_JSON` → contenido del `client_secrets.json`
- `YOUTUBE_TOKEN_JSON` → contenido del `token.json`

## Notas

- El token incluye *refresh token*: se renueva solo en cada ejecución.
- Si Google revoca el permiso o cambias de cuenta, repite el paso 5.
- Para cambiar la privacidad de las subidas edita
  `publicacion.youtube.privacidad` en `config.yaml`.
