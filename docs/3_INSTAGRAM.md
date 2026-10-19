# 3. Instagram (Reels y Stories)

La subida usa la **Graph API de Meta** con subida resumible: el mp4 viaja en
binario directo a Meta (sin buckets ni servidores intermedios).

## Requisitos previos

- Una cuenta de Instagram **profesional** (Creador o Empresa).
- Vinculada a una **página de Facebook**.
- Una **app de Meta** con Instagram Graph API activada.

## Paso 1 — App en Meta for Developers

1. Entra en <https://developers.facebook.com/> y crea una app (tipo **Empresa**).
2. Añade el producto **Instagram Graph API**.

## Paso 2 — Token de usuario de larga duración

1. Abre el **Graph API Explorer**
   (<https://developers.facebook.com/tools/explorer/>).
2. Selecciona tu app y marca estos permisos:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
3. Genera el token de usuario.

### Convertirlo en token permanente

```
GET /oauth/access_token?
    grant_type=fb_exchange_token&
    client_id=<APP_ID>&
    client_secret=<APP_SECRET>&
    fb_exchange_token=<USUARIO_TOKEN>
```

### Obtener el token de la página y el ID de Instagram

```
GET /me/accounts?fields=access_token,instagram_business_account
```

- `access_token` de la página → es el que usarás (`INSTAGRAM_ACCESS_TOKEN`).
- `instagram_business_account.id` → tu `INSTAGRAM_ACCOUNT_ID`.

## Paso 3 — Credenciales locales (opcional)

Para pruebas en local crea `instagram_credentials.json` en la raíz:

```json
{
  "access_token": "TU_TOKEN_DE_PAGINA",
  "instagram_account_id": "17841400000000000"
}
```

En `.gitignore`, nunca lo subas.

## Paso 4 — Secrets de GitHub

Sube `INSTAGRAM_ACCESS_TOKEN` e `INSTAGRAM_ACCOUNT_ID` siguiendo
[4_GITHUB_SECRETS.md](4_GITHUB_SECRETS.md).

## Notas

- Los Reels llevan el caption con hashtags de `config.yaml`
  (`publicacion.instagram.hashtags`).
- Las Stories se publican sin caption.
- Los tokens de Facebook caducan; los de página de larga duración duran ~60 días.
  Renueva y actualiza el secret cuando venza.
