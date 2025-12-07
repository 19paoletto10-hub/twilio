# Release v1.1.0

**Summary**

Release v1.1.0 prepares the project for client demos: production-ready Dockerfile, development Codespaces devcontainer, docker-compose configs (dev & production with nginx), demo scripts and a Makefile with convenient targets.

**Highlights**

- Dockerfile: non-root user, healthcheck, Gunicorn entrypoint.
- Devcontainer: `.devcontainer/` for Codespaces and local Dev Containers.
- `docker-compose.yml` for quick local/demo runs.
- `docker-compose.production.yml` + `deploy/nginx/default.conf` for a simple production proxy setup.
- `Makefile` with `build`, `run`, `compose-demo`, `compose-prod`, `demo-send` targets.
- `scripts/demo_send.sh` to post test messages to `/api/send-message`.
- Auto-reply worker and database persistence for demo flows.

## Changelog (commits included)

