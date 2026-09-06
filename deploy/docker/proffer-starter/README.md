# Proffer starter

Authenticated HTTP bridge between the live n8n human-review workflows and
Temporal. It starts `engine/proffer.ProfferWorkflow`, sends preview
approval/rejection Signals, and queries the durable preview state. It contains
no parser, Activity, persistence, or in-memory hold logic.

Coolify application contract:

- Dockerfile: `/docker/proffer-starter/Dockerfile`
- Tailnet-only port: `100.91.190.107:8091`
- Health: `GET /healthz`
- Task queue: the same dedicated queue as the all-23 Go worker; never
  `evidence-pipeline`
- Persistent storage: none
- External network: `coolify`
- Watch paths: `engine/**`, `docker/proffer-starter/**`, and
  `deploy/proffer-starter.yaml`

Required secrets and environment are declared in
`deploy/proffer-starter.yaml`. No secret value belongs in this image,
repository, logs, or deployment receipt.
