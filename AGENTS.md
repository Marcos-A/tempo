# Agent Workflow

## Default expectations

- Keep changes focused and reversible.
- Prefer preview or staging validation before production promotion.
- Treat deployment wiring, secrets, and infrastructure details as environment-specific rather than repository defaults.

## Repository notes

- Use `docker-compose.yml` for local development.
- Keep README documentation reusable for other deployments.
- Avoid committing live secrets, internal server paths, or operator-only runbooks unless they are intentionally generic.
- The internship calendar grid is rendered twice: `renderResult` in `app/templates/internship/index.html` (browser) and `build_month_views` plus `app/templates/internship/export.html` (read-only HTML and PDF exports; the PDF wraps the same `day_cell` macro in tables). Apply grid markup changes to both; see the maintenance note in the README.
