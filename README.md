# Tempo

Tempo (formerly "Curriculum Planner") is a small FastAPI app to schedule a module across an academic year, exclude no-class dates, distribute Resultats d'Aprenentatge (RAs), and export an XLSX planning workbook.

The project is intentionally compact. Most business rules live in `app/services/`, while `app/routes/` handles HTTP requests and `app/templates/` renders the interface.

## Development note

This project was developed with human direction and review, with assistance from OpenAI Codex and Anthropic Claude for parts of the implementation, refactoring, and deployment workflow documentation.

## Stack

- FastAPI
- Jinja templates + small vanilla JavaScript
- SQLite
- SQLAlchemy
- openpyxl
- Docker Compose

## What the app does

- lets an admin maintain excluded academic dates
- lets teachers define a teaching calendar for one module
- supports sequential planning and parallel-block planning
- exports the final planning as an XLSX workbook ready for manual review

## Run locally with Docker

`docker-compose.yml` is set up for development convenience:

- `./app` is bind-mounted into the container
- `./tests` is bind-mounted into the container
- Uvicorn runs with `--reload`

That means template, CSS, and Python edits on the host are reflected without rebuilding the image every time.

1. Copy `.env.example` into your own `.env` file if you want custom values.
2. Start the app:

```bash
docker compose up --build
```

3. Open `http://localhost:8000`
4. The teacher flow is available at `/`
5. The admin area is available only by direct URL at `/admin`

If port `8000` is already in use, choose another host port:

```bash
HOST_PORT=10080 docker compose up --build
```

Then open `http://localhost:10080`.

The SQLite database is stored in `./data/app.db` and persists through the bind mount.

## Run a production-style container from the repo

Use `docker-compose.production.yml` when you want a reproducible deployment without
development bind mounts or `--reload`.

1. Copy `.env.example` to a real env file and set strong credentials and a real `SECRET_KEY`.
2. Choose where your persistent SQLite data should live.
3. Start the production-style stack:

```bash
ENV_FILE=/absolute/path/to/.env.prod \
DATA_DIR=/absolute/path/to/data \
HOST_PORT=8091 \
docker compose -f docker-compose.production.yml up -d --build
```

This matches the container shape used by the live deployment:

- baked image build
- `python -m app.server`
- persistent `/app/data` bind mount
- health check enabled
- no source bind mounts

You can also use the repo-native helper script:

```bash
ENV_FILE=/absolute/path/to/.env.prod \
DATA_DIR=/absolute/path/to/data \
HOST_PORT=8091 \
bash scripts/deploy_production.sh
```

Default production-oriented variables:

- `ENV_FILE=/srv/config/tempo/.env.prod`
- `DATA_DIR=/srv/data/tempo`
- `HOST_PORT=8091`
- `CONTAINER_NAME=tempo-web`
- `IMAGE_NAME=tempo-web:local`

These defaults are convenient on this server, but every value can be overridden so another
admin can deploy the same app elsewhere without editing the compose file.

## Preview deployment

`docker-compose.preview.yml` is the same production-style container shape, but intended for
branch testing on a separate host port and container name.

Deploy it with:

```bash
bash scripts/deploy_preview.sh
```

## Design assets

- `design/tempo-design-system.md`: canonical brand and design system reference (logo construction, color, typography, spacing, components).
- `design/brand/`: full production asset package (all SVG/PNG/ICO color variants and sizes) the app's assets are exported from — see `design/brand/README.md`.
- `app/static/img/`: the curated subset of logo SVGs actually served by the app (symbol, wordmark, lockup, app icon, favicon — pine/white/black/ink variants only).
- `app/static/fonts/`: self-hosted Inter (latin subset), matching the wordmark's typeface, used for headings and body text.

## Environment variables

- `APP_NAME`: main app name shown in the UI
- `SCHOOL_NAME`: optional suffix shown in the header and page title
- `SECRET_KEY`: session signing secret
- `ADMIN_USERNAME`: admin login username
- `ADMIN_PASSWORD`: admin login password
- `DATABASE_URL`: SQLAlchemy database URL

`.env.example` includes safe placeholders. Change the admin credentials and secret key before exposing the app outside local development.

## Run tests

```bash
docker compose run --rm web pytest
```

You can also run the focused service tests directly in a Python environment with the project dependencies installed:

```bash
pytest tests/test_services.py
```

## State handling and concurrency

The teacher flow is intentionally lightweight and mostly stateless.

### Where step data lives

- Step 1 validates the submitted dates, weekday hours, planning mode, and excluded periods, then renders step 2 with a compact JSON payload embedded in the HTML.
- Step 2 runs in the browser. RA order, names, hours, and block assignment are edited client-side and are posted back to `/export` only when the user requests the final XLSX.
- In-progress teacher planning data is not stored in the server-side session and is not persisted to the database between steps 1 and 2.
- If the user refreshes or closes the tab before exporting, that in-progress step-2 state is lost unless the browser still preserves the page.

### Practical concurrency expectations

- Teacher usage is mostly read-heavy plus in-memory calculations, because the step-2 editing experience lives in the browser.
- XLSX generation is server-side work, so the main pressure point is a burst of simultaneous exports.
- Admin writes are expected to be rare, which keeps SQLite reasonable for small-school usage.
- The production-style entrypoint uses a modest multi-worker default and can be tuned with `WEB_CONCURRENCY`.

In practical terms, the current design should be fine for ordinary school usage with a few dozen teachers using the app at the same time, especially if exports are naturally staggered.

### Consistency note

Excluded dates are resolved during step 1 and included in the payload sent to step 2. If an admin changes excluded dates while a teacher is already on step 2, that teacher will still export using the earlier step-1 snapshot.

### Lightweight load checking

A small concurrent smoke test is available:

```bash
python scripts/load_test_teacher_flow.py --base-url http://127.0.0.1:8000
```

Useful flags:

- `--requests` to control total request count
- `--concurrency` to control parallelism
- `--timeout` to adjust the per-request timeout

This script exercises the public teacher flow and prints latency plus throughput figures. It is meant as a lightweight regression check, not a full benchmark suite.

## App flow

- `/admin`
  - login-protected
  - not linked from the public UI; access directly by URL
  - manage academic year defaults and excluded dates
- `/`
  - teacher configuration step
  - computes teaching hours using real weekdays, no weekends, and excluded dates
- `/plan`
  - RA distribution step
  - supports reorder and block assignment before export
  - export is available only when validation rules are satisfied

## Project structure

```text
app/
  config.py
  database.py
  models.py
  auth.py
  dependencies.py
  main.py
  routes/
  services/
  static/
    css/
    fonts/
    img/
  templates/
design/
scripts/
tests/
Dockerfile
docker-compose.yml
README.md
```

## Deployment notes

- `docker-compose.yml` is for local development.
- `docker-compose.production.yml` is the repo-native production deployment file.
- `docker-compose.preview.yml` is for branch preview deployments.
- Replace `SECRET_KEY` and admin credentials with real environment variables.
- Run the app behind HTTPS through a reverse proxy.
- Back up the database file regularly if you keep using SQLite.
- If admin writes or export traffic grow substantially, consider moving from SQLite to PostgreSQL and placing XLSX exports behind a small queue.

## License

This project is licensed under the GNU Affero General Public License v3.0 (`AGPL-3.0-only`). See [LICENSE](LICENSE).
