# Agent Workflow

## Default Deployment Rule

Unless the user explicitly says otherwise, treat new feature branches and bugfix
branches as preview deployments, not production deployments.

Use this default workflow:

1. Keep `/srv/apps/curriculum-planner` on stable `main` for `planner.marcos-a.com`.
2. Use `/srv/apps/curriculum-planner-preview` as the preview Git worktree.
3. Create or switch the preview worktree to the branch being developed.
4. Deploy that branch to `https://planner-preview.marcos-a.com/` with
   `./scripts/deploy_preview.sh` from the preview worktree.
5. Only update the production deployment when the user explicitly wants the
   validated work merged or promoted.

## Operational Notes

- Do not use repo-root `docker-compose.yml` to manage the live server.
- Production is served through `/srv/compose/curriculum-planner/compose.yml`.
- Preview is served through the preview worktree's `docker-compose.preview.yml`.
- Preview and production currently share `/srv/data/curriculum-planner`, so
  preview changes affect live data.
