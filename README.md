# Mise

Find a cooking video, pull the recipe out of it. Mise searches YouTube, extracts
the transcript/captions, and uses an LLM to turn it into structured recipe data
you can save. Audio uploads are transcribed with Whisper.

- **Web app** — Django 5 + HTMX + Alpine, served by gunicorn (port `8000`)
- **Worker** — Celery for async extraction jobs
- **Audio service** — FastAPI + Whisper + ffmpeg (port `8001`)
- **LLM** — local llama.cpp server (port `8080`) or any OpenAI-compatible API
- **Infra** — PostgreSQL 16 (port `5432`), Redis 7

The whole stack runs in Docker Compose.

## Prerequisites

- **Docker** + the Compose plugin (`docker compose`, v2)
- A **YouTube Data API key** (for search) — https://console.cloud.google.com/apis/library/youtube.googleapis.com
- For the **default local LLM backend**: an **NVIDIA GPU** + the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
  No GPU? See [LLM backend](#llm-backend) to switch to a hosted API instead.

## Quick start

```bash
# 1. Configure environment
cp .env.example .env
#    then edit .env and set YOUTUBE_API_KEY (and DJANGO_SECRET_KEY)

# 2. Build images and start everything
docker compose up --build
```

Open http://localhost:8000.

> First run downloads base images, the Whisper model, and (on the default
> backend) the ~15GB llama.cpp GGUF — give it time. Subsequent starts are fast.

`npm run docker:start` is a shortcut for `docker compose up --build` (see
[`package.json`](package.json) for the other `docker:*` scripts).

## Do I need to build the assets? No.

**You do not run any separate asset/build step.** There is no webpack/vite/esbuild
and no `npm run build`. The frontend is plain CSS in `apps/web/static/` plus HTMX
and Alpine loaded from a CDN.

Static assets are "built" automatically **inside the web container**. Its startup
command ([`apps/web/Dockerfile`](apps/web/Dockerfile)) runs, on every
`docker compose up`:

```sh
python manage.py collectstatic --noinput   # WhiteNoise collects, hashes & gzips CSS
&& python manage.py migrate                 # applies DB migrations
&& gunicorn config.wsgi:application ...      # serves the app
```

So `docker compose up --build` is all you need — collectstatic and migrations run
for you. Things to know:

- **Changed a CSS file?** Restart the web service to re-run collectstatic:
  `docker compose restart web` (or `docker compose up` again). A plain page
  refresh won't pick it up, because WhiteNoise serves content-hashed filenames.
- **Changed Python deps or the Dockerfile?** Rebuild: `docker compose up --build`.
- **Editing templates/Python only?** No build needed — restart `web` to reload.

## Environment variables

Copy `.env.example` to `.env`. The values you'll likely touch:

| Variable            | Default            | Notes                                              |
| ------------------- | ------------------ | -------------------------------------------------- |
| `YOUTUBE_API_KEY`   | —                  | **Required** for recipe search                     |
| `DJANGO_SECRET_KEY` | dev placeholder    | Set a long random string                           |
| `DJANGO_DEBUG`      | `true`             | Set `false` in production                          |
| `WEB_PORT`          | `8000`             | Host port for the web app                          |
| `EXTRACTOR_BACKEND` | `llamacpp`         | `llamacpp` (GPU), `hosted` (API), or `local`       |
| `WHISPER_MODEL_SIZE`| `base`             | Whisper model for audio transcription              |

See `.env.example` for the full list (llama.cpp tuning, hosted-LLM URL/key, email).

## LLM backend

Set `EXTRACTOR_BACKEND` in `.env`:

- **`llamacpp`** (default) — bundled llama.cpp server runs the gemma-4-26B-A4B MoE
  with expert offload. Needs an NVIDIA GPU + Container Toolkit; ~16GB VRAM and
  ~32GB RAM with the default `LLAMACPP_NCMOE=99`. Tunables in `.env.example`.
- **`hosted`** — point at any OpenAI-compatible API (vLLM, a cloud LLM, etc.).
  Set `HOSTED_LLM_URL`, `HOSTED_LLM_API_KEY`, `HOSTED_LLM_MODEL`. **Use this if
  you have no GPU.**
- **`local`** — an external Ollama-compatible server (not bundled in compose).

## Common commands

```bash
docker compose up --build            # start (rebuild images)
docker compose up -d                 # start detached
docker compose logs -f web           # tail web logs (or: worker, ml, llamacpp, db)
docker compose restart web           # re-run collectstatic/migrate, reload web
docker compose down                  # stop
docker compose down -v               # stop and wipe volumes (DB, uploads, model cache)
```

`npm run docker:start` / `docker:stop` / `docker:logs` / `docker:reset` wrap the
above.

### Migrations & database

Migrations apply automatically when the `web` container starts. To run Django
commands manually:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

To reset the database, stop with `docker compose down -v` (drops the `db-data`
volume), then start again.

## Troubleshooting

- **CSS changes not showing** — restart `web` (collectstatic only runs on start);
  hard-refresh the browser to bypass cached hashed assets.
- **llama.cpp won't start / no GPU** — switch `EXTRACTOR_BACKEND=hosted` and
  configure `HOSTED_LLM_*`, or install the NVIDIA Container Toolkit.
- **`web` can't reach the DB** — it waits on the Postgres healthcheck; check
  `docker compose logs db`.
- **Slow first start** — model/image downloads; watch `docker compose logs -f`.
