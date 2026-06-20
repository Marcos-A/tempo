# Agent Workflow

## Default expectations

- Keep changes focused and reversible.
- Prefer preview or staging validation before production promotion.
- Treat deployment wiring, secrets, and infrastructure details as environment-specific rather than repository defaults.

## Repository notes

- Use `docker-compose.yml` for local development.
- Keep README documentation reusable for other deployments.
- Avoid committing live secrets, internal server paths, or operator-only runbooks unless they are intentionally generic.
