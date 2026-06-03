# Immich Dynamic Albums — Web UI

A self-hosted web application for creating and managing **dynamic** and **static** albums in
[Immich](https://immich.app/), with a Bootstrap 5 UI, scheduled syncing, and flexible authentication.

> **Forked from** [kvalev/immich-dynamic-albums](https://github.com/kvalev/immich-dynamic-albums)
> and extended into a full web application.

---

## Features

| Feature | Detail |
|---|---|
| **Dynamic albums** | Automatically synced on a configurable schedule |
| **Static albums** | Synced once (or manually) against a saved query |
| **Query builder** | Visual UI: people, tags, countries, date ranges, favorites, path filters |
| **Authentication** | Immich email/password **and/or** OIDC / SSO |
| **Admin user picker** | Admins visually select whose photos to include |
| **Settings UI** | All environment variables configurable via the web UI |
| **Sync history** | Per-album audit log of every sync run |
| **Scheduler** | APScheduler—no cron daemon needed |
| **Docker-ready** | Multi-stage image published to GHCR; pull without building |
| **i18n** | Fully localizable UI (English + French included) |

---

## Quick Start (Docker Compose)

```bash
# 1. Clone
git clone https://github.com/viranit/immich-dynamic-albums.git
cd immich-dynamic-albums

# 2. Configure
cp .env.example .env
# Edit .env — set SECRET_KEY and IMMICH_URL at minimum

# 3. Launch
docker compose up -d

# 4. Open http://localhost:5000 and log in with your Immich credentials
```

---

## Unraid / Docker-Pull Deployment

The image is automatically published to the **GitHub Container Registry** on every push to `main`.
You do **not** need to clone this repository or build anything locally.

### Pulling the image

```bash
docker pull ghcr.io/viranit/immich-dynamic-albums:main
```

### Adding to your existing Immich stack

Add the following services to your existing `docker-compose.yml` (alongside the Immich services):

```yaml
  immich-dynamic-albums:
    container_name: immich_dynamic_albums
    image: ghcr.io/viranit/immich-dynamic-albums:main
    restart: unless-stopped
    ports:
      - "5050:5000"          # change 5050 to any free host port
    env_file:
      - .env.albums          # separate env file — see below
    depends_on:
      - immich-dynamic-albums-db
    networks:
      - frontend
      - backend
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  immich-dynamic-albums-db:
    container_name: immich_dynamic_albums_db
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: immich_albums
      POSTGRES_USER: immich_albums
      POSTGRES_PASSWORD: ${ALBUMS_DB_PASSWORD:-immich_albums}    # change in production
    volumes:
      - /mnt/user/appdata/immich-albums/pgdata:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U immich_albums -d immich_albums"]
      interval: 10s
      timeout: 5s
      retries: 5
```

#### `.env.albums`

```dotenv
SECRET_KEY=<run: openssl rand -hex 32>
DATABASE_URL=postgresql://immich_albums:immich_albums@immich_dynamic_albums_db:5432/immich_albums
IMMICH_URL=http://immich_server:2283
IMMICH_API_KEY=<your Immich admin API key>

# Authentication (choose one)
AUTH_METHOD=immich          # or: oidc / both

# OIDC only (leave blank if using AUTH_METHOD=immich)
OIDC_ISSUER_URL=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=

# Scheduler
GLOBAL_SYNC_INTERVAL=60    # minutes
SYNC_ENABLED=true
```

> **Tip:** `IMMICH_URL` should use the internal Docker service name (`immich_server`) so
> traffic stays on the `backend` network and never leaves the host.

### Upgrading

```bash
docker compose pull immich-dynamic-albums
docker compose up -d immich-dynamic-albums
```

The container automatically runs `flask db upgrade` on startup, so schema migrations are
applied without manual intervention.

---

## Environment Variables

All variables can also be set from **Settings** inside the web UI.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Flask session secret (generate with `openssl rand -hex 32`) |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `IMMICH_URL` | ✔ | — | Base URL of your Immich instance |
| `IMMICH_API_KEY` | ✔ | — | Immich admin API key |
| `AUTH_METHOD` | | `immich` | `immich`, `oidc`, or `both` |
| `OIDC_ISSUER_URL` | OIDC only | — | OIDC discovery endpoint |
| `OIDC_CLIENT_ID` | OIDC only | — | OIDC client ID |
| `OIDC_CLIENT_SECRET` | OIDC only | — | OIDC client secret |
| `GLOBAL_SYNC_INTERVAL` | | `60` | Default sync interval in minutes |
| `SYNC_ENABLED` | | `true` | Enable/disable the background scheduler |
| `WEB_PORT` | | `5000` | Host port exposed by docker-compose |
| `LOG_LEVEL` | | `INFO` | Python log level |

---

## Album Types

### Dynamic Albums
Criteria are saved to the database. APScheduler re-runs the sync every
`GLOBAL_SYNC_INTERVAL` minutes (or per-album override). Assets are **added** and
**removed** automatically to keep the album in sync with the query.

### Static Albums
Synced **once** at creation. A manual *Sync Now* button is available. The album in
Immich is created if it doesn't exist; otherwise it is updated by adding / removing
assets that match or no longer match the query.

---

## Query Builder Reference

| Field | Type | Notes |
|---|---|---|
| `people` | list | All people must appear (AND). Names or Immich UUIDs. |
| `any_people` | list | At least one person must appear (OR). |
| `people_strict_mode` | bool | Exact match—no other people allowed. |
| `tags` | list | Tag names or UUIDs. |
| `country` | string / list | Single country or list → one sub-query per country. |
| `state` | string | |
| `city` | string | |
| `path` | string | Substring match against original file path. |
| `favorite` | bool | Limit to favourited assets. |
| `timespan` | object / list | `{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}`. Multiple → union. |

---

## Development Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY=dev DATABASE_URL=sqlite:///dev.db AUTH_METHOD=immich

flask db upgrade
flask run
```

### Running Tests

```bash
pip install pytest pytest-env
pytest
```

Test coverage includes:
- **Unit**: models, `ImmichClient`, `AlbumSyncService`, validators
- **Integration**: auth routes, album CRUD routes, REST API endpoints

---

## Migrating from the CLI Version

1. Export your existing JSON config (e.g. `albums.json`).
2. Start the web app and log in.
3. Use **Settings → Import CLI Config** *(or the API endpoint `POST /api/import`)* and
   upload your JSON file.
4. Each entry becomes a **dynamic album** in the database.
   Existing Immich albums are detected by name and linked automatically.

> **Breaking change:** The original `ALBUMS_CONFIG` env var and JSON file are no longer
> used. All configuration now lives in the PostgreSQL database.

---

## Architecture

```
app/
├── __init__.py          Flask app factory
├── config.py            Dev / Prod / Test config classes
├── models.py            SQLAlchemy models (Album, Setting, SyncLog, User)
├── immich_client.py     Immich REST API client
├── album_service.py     Sync orchestration logic
├── auth.py              OIDC + Immich authentication helpers
├── scheduler.py         APScheduler integration
├── routes/
│   ├── auth.py            /login, /logout
│   ├── albums.py          Album CRUD + manual sync
│   ├── settings.py        Settings page
│   └── api.py             REST API
├── templates/           Jinja2 / Bootstrap 5 templates
└── static/              CSS + JS
migrations/              Alembic migration scripts
tests/                   pytest test suite
```

---

## Requirements

- Immich ≥ v1.127.0
- Python 3.11+
- PostgreSQL 14+ (SQLite supported for development)

---

## License

MIT — see [LICENSE](LICENSE).
