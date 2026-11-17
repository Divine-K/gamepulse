# Deploy on free tiers (Cloudflare Pages + Render + Neon)

Everything below has a permanent free plan. You create the accounts and paste the secrets yourself; nothing here needs a payment card on the providers' own pages, but **check each signup screen** and stop if one asks for a card. Free tiers change, so re-read each provider's pricing page first.

```
Browser --> Cloudflare Pages (static dashboard)
        --> Render web service (API, Docker)  --> Neon (PostgreSQL)
                                              \-> Render Key Value (Redis)
```

The dashboard and API are on different origins, so the API needs `CORS_ORIGINS` and the dashboard is built with an absolute `VITE_API_BASE_URL`. Files prepared for this: [`render.yaml`](../render.yaml) and [`deploy/cloudflare/`](../deploy/cloudflare/).

## 1. Neon (PostgreSQL)

1. Sign up at neon.com and create a project (any region close to your Render region).
2. Copy the connection string and change two things: the scheme must be `postgresql+psycopg://` and it must end with `?sslmode=require`.
   `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`
3. Keep it for step 2. Never commit it.

## 2. Render (API and Redis)

1. Sign up at render.com with GitHub and grant access to the `gamepulse` repository.
2. New, then **Blueprint**, pick the repository. Render reads `render.yaml` and proposes the `gamepulse-api` web service and `gamepulse-redis` Key Value store, both on the **Free** plan (confirm that no paid plan is selected).
3. When asked for the secret values enter:
   - `DATABASE_URL`: the Neon string from step 1.
   - `SECRET_KEY`: output of `openssl rand -hex 32`.
   - `CORS_ORIGINS`: `["https://YOUR-PROJECT.pages.dev"]` (JSON list; you can fix it after step 3 once the real address is known).
4. Deploy. The API applies the migrations on its first start. Check `https://YOUR-API.onrender.com/health` returns `{"status":"ok"}`.

The free service sleeps after 15 minutes without traffic and takes about a minute to wake. Redis data may be lost on restart, which is safe (the active-player index and caches rebuild).

## 3. Cloudflare Pages (dashboard)

1. Sign up at cloudflare.com, then Workers & Pages, create a Pages project from the GitHub repository.
2. Settings:
   - Root directory: `frontend`
   - Build command: `sh ../deploy/cloudflare/build.sh`
   - Build output directory: `dist`
   - Environment variable `VITE_API_BASE_URL`: `https://YOUR-API.onrender.com` (no trailing slash)
   - Environment variable `NODE_VERSION`: `22`
3. Deploy. The build script writes the security headers (a CSP that allows only your API origin and its WebSocket) and a single-page-app fallback into the output.
4. If the Pages address differs from what you put in `CORS_ORIGINS`, update that variable in Render and redeploy.

## 4. Verify

```bash
python backend/scripts/smoke.py https://YOUR-API.onrender.com --api-only
```

Then open the dashboard, register, create a game, and run the simulator to see the live feed. Allow a minute for the first request if the API was asleep. To run the browser suite instead, use a throwaway deployment (it registers accounts): `E2E_BASE_URL=https://YOUR-PROJECT.pages.dev npx playwright test`.

## Known limits

- First request after idle is slow (API sleep; Neon also scales to zero).
- Free Postgres on Neon has no scheduled backups here; export with `pg_dump` if the data matters.
