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
