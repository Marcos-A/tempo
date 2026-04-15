# Curriculum Planner MVP

Docker-first MVP to schedule a subject across an academic year, exclude no-class dates, distribute Resultats d'Aprenentatge (RAs), and export an XLSX planning workbook.

This repository is intentionally small. Most of the important business rules
live in the `app/services/` modules, while `app/routes/` handles web requests
and `app/templates/` renders the interface.

## Stack

- FastAPI
- Jinja templates + small vanilla JavaScript
- SQLite
- SQLAlchemy
- openpyxl
- Docker Compose

## Run locally with Docker only

This repository is currently configured for development convenience in
`docker-compose.yml`:

- `./app` is bind-mounted into `/app/app`
- `./tests` is bind-mounted into `/app/tests`
- the container runs Uvicorn with `--reload`

That means template, CSS, and Python edits made on the host are reflected in the
running container without rebuilding the image every time.

Important: this is development-only. Before deploying to production, revert the
bind mounts and remove `--reload` so the container runs only the code baked into
the image.

Important for this server: do not use the repo-root `docker-compose.yml` to
manage the live `planner.marcos-a.com` service. Production is managed by the
server compose stack at `/srv/compose/curriculum-planner/compose.yml`, which
mounts the real production database from `/srv/data/curriculum-planner`.

1. Optionally copy `.env.example` values into your own shell or adapt `docker-compose.yml`.
2. Start the app:

```bash
docker compose up --build
```

3. Open `http://localhost:8000`
4. Teacher flow is available at `http://localhost:8000`
5. Admin area is only accessible by direct URL at `http://localhost:8000/admin`

If port `8000` is already in use, choose another host port:

```bash
HOST_PORT=10080 docker compose up --build
```

Then open `http://localhost:10080`.
The admin area remains available only by direct URL, for example `http://localhost:10080/admin`.

Default admin credentials come from environment variables:

- Username: `admin`
- Password: `admin123`

The SQLite database is stored in `./data/app.db` and persists through the bind mount in `docker-compose.yml`.

After the first `docker compose up --build`, most code-only changes do not need
another rebuild because the app source is bind-mounted for development. If you
change Python dependencies or the Docker image itself, rebuild again.

## Run tests with Docker

```bash
docker compose run --rm web pytest
```

## Remote preview deployment

`planner-preview.marcos-a.com` is the dedicated preview URL for testing
development branches from another computer without touching production at
`planner.marcos-a.com`.

Server checkouts:

- Stable main checkout: `/srv/apps/curriculum-planner`
- Dedicated preview checkout: `/srv/apps/curriculum-planner-preview`

Recommended server-side workflow:

1. Keep production work anchored to `/srv/apps/curriculum-planner`.
2. Do feature work only in `/srv/apps/curriculum-planner-preview`.
3. Deploy the preview stack from the preview checkout with
   `scripts/deploy_preview.sh`.
4. Reuse the same preview subdomain for the next branch by resetting the
   preview checkout back to `main`, creating a fresh branch, and redeploying.

Example commands on the server:

```bash
cd ../curriculum-planner-preview
./scripts/deploy_preview.sh
```

The preview stack listens on `127.0.0.1:8092` by default and, by design, uses
the same SQLite bind mount as production (`/srv/data/curriculum-planner`) so
changes made through the preview site read and write the same database as
`planner.marcos-a.com`.

Safeguards built into the preview workflow:

- `docker-compose.preview.yml` uses its own Compose project name,
  `curriculum-planner-preview`, so it does not replace the production service
  by default.
- The preview service has a fixed container name,
  `curriculum-planner-preview-web`, so it is easy to inspect.
- `scripts/deploy_preview.sh` defaults to the production env file and
  production data path used on this server.
- `scripts/show_planner_runtime.sh` prints the image, port mapping, database
  mount, and `DATABASE_URL` for both production and preview so mount mistakes
  are visible immediately.

Suggested Caddy site block:

```caddyfile
planner-preview.marcos-a.com {
	reverse_proxy 127.0.0.1:8092 {
		import reverse_proxy_headers
	}
}
```

If the preview checkout should use a different shared data directory somewhere
else on the server, set `PREVIEW_DATA_DIR=/absolute/path` before starting the
stack.

To inspect the current runtime wiring at any time:

```bash
./scripts/show_planner_runtime.sh
```

## Feature Workflow On This Server

Use this exact sequence for each new feature or bugfix.

### 1. Start from the stable main checkout

Do not develop in `/srv/apps/curriculum-planner-preview` until the stable
checkout has the latest `main`.

```bash
cd /srv/apps/curriculum-planner
git checkout main
git pull --ff-only origin main
```

### 2. Reset the preview checkout to the latest main

This keeps old branch work from leaking into the next feature.

```bash
cd /srv/apps/curriculum-planner-preview
git fetch origin
git checkout --detach origin/main
git branch -D feature/old-branch-name 2>/dev/null || true
```

If the preview checkout is currently on a branch you still need, do not delete
it until that work has been merged or saved elsewhere.

### 3. Create a fresh branch in the preview checkout

Every new task should get a new branch name. Do not keep reusing an old branch
like `bugfix/parallel-ra-row-highlighting` for unrelated work.

```bash
cd /srv/apps/curriculum-planner-preview
git switch -c feature/short-description
```

### 4. Develop and test in the preview checkout

Run code edits, local checks, and the service tests from the preview checkout.

```bash
cd /srv/apps/curriculum-planner-preview
docker compose run --rm web pytest /app/tests/test_services.py
```

### 5. Deploy that branch to planner-preview.marcos-a.com

This deploys the current preview checkout branch to the preview URL while
keeping production untouched.

```bash
cd /srv/apps/curriculum-planner-preview
./scripts/deploy_preview.sh
```

Then verify the runtime wiring:

```bash
cd /srv/apps/curriculum-planner-preview
./scripts/show_planner_runtime.sh
```

Expected result:

- production points to `127.0.0.1:8091`
- preview points to `127.0.0.1:8092`
- both mounts show `/srv/data/curriculum-planner`

### 6. Test from another computer

Use:

- Production: `https://planner.marcos-a.com/`
- Preview: `https://planner-preview.marcos-a.com/`

Important: preview uses the same database as production on this server. Any
admin edits or planning data changes made through preview are live data changes.

### 7. Merge finished work back into main

After the preview branch is validated:

```bash
cd /srv/apps/curriculum-planner-preview
git status
git add ...
git commit -m "Describe the change"

cd /srv/apps/curriculum-planner
git checkout main
git pull --ff-only origin main
git merge --ff-only /srv/apps/curriculum-planner-preview
git push origin main
```

If you prefer, you can also push the feature branch first and merge through the
normal branch name rather than the worktree path.

### 8. Prepare preview for the next feature

Once the feature is merged, put the preview checkout back on the new `main`
baseline before starting the next branch.

```bash
cd /srv/apps/curriculum-planner-preview
git fetch origin
git checkout --detach origin/main
git branch -D feature/short-description
./scripts/deploy_preview.sh
```

This makes `planner-preview.marcos-a.com` show the merged `main` state until
the next dedicated feature branch is created.

### 9. Never use these shortcuts on this server

- Do not use `/srv/apps/curriculum-planner/docker-compose.yml` to manage the
  live `planner.marcos-a.com` service.
- Do not run preview from `/srv/apps/curriculum-planner`; always use the
  dedicated preview checkout.
- Do not assume `planner-preview.marcos-a.com` has isolated data; it shares the
  production database intentionally.
- Do not keep reusing one long-lived branch for unrelated work.

## App flow

- `/admin`
  - login-protected
  - not linked from the public UI; access directly by URL
  - manage default academic year dates
  - add single-date exclusions by entering only the start date, or inclusive date ranges by filling both dates
  - delete exclusions
- `/`
  - teacher config step
  - computes teaching hours using real weekdays, no weekends, and admin exclusions
- `/plan`
  - RA distribution step
  - supports reorder by drag-and-drop
  - export only when assigned hours exactly match total available

## Architecture

```text
app/
  config.py
  database.py
  models.py
  auth.py
  dependencies.py
  main.py
  routes/
    admin.py
    teacher.py
  services/
    allocation.py
    bootstrap.py
    calendar.py
    export.py
  static/css/app.css
  templates/
    base.html
    admin/
    teacher/
tests/
Dockerfile
docker-compose.yml
README.md
```

## Production notes

- Replace `SECRET_KEY` and admin credentials with environment variables from the deployment platform.
- Revert the development-only bind mounts in `docker-compose.yml` (`./app:/app/app`, `./tests:/app/tests`) before production.
- Revert the development-only Uvicorn `--reload` flag before production.
- Put the app behind a reverse proxy for a subdomain such as `planner.marcos-a.com`.
- Set secure cookie settings and HTTPS termination at the proxy.
- Replace the SQLite bind mount with a managed persistent volume or move to PostgreSQL if concurrent writes grow.
- Add CSRF protection, structured logging, and backup/restore procedures before production use.
