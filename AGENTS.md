# Agent Workflow

## Default expectations

- Keep changes focused and reversible.
- Prefer preview or staging validation before production promotion.
- Treat deployment wiring, secrets, and infrastructure details as environment-specific rather than repository defaults.

## Branches

- `main` and `preview` are both long-lived. `preview` is the branch used for preview deployments and may be checked out in its own worktree on the host.
- Never delete `preview`, its remote copy or its worktree, even when it is fully merged into `main` or a request asks to "remove useless branches". Leave both long-lived branches out of any cleanup.
- Before removing any other branch that has its own worktree or looks tied to a deployment, ask first.

## Repository notes

- Use `docker-compose.yml` for local development.
- Keep README documentation reusable for other deployments.
- Avoid committing live secrets, internal server paths, or operator-only runbooks unless they are intentionally generic.
- The internship calendar grid is rendered twice: `renderResult` in `app/templates/internship/index.html` (browser) and `build_month_views` plus `app/templates/internship/export.html` (read-only HTML and PDF exports; the PDF wraps the same `day_cell` macro in tables). Apply grid markup changes to both; see the maintenance note in the README.
