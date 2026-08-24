# HelixMind infrastructure boundary

HelixMind is an isolated tenant on a shared VPS. Its API and Redis remain
loopback-bound services; the HelixMind-specific Nginx/TLS route currently
forwards the public API hostname to the API service.

| Resource | Identity | Binding / ownership |
| --- | --- | --- |
| API | `helixmind-api.service` | `127.0.0.1:8401`, user `helixmind` |
| Worker | `helixmind-worker.service` | RQ queue `helixmind-research`, user `helixmind` |
| Redis | `helixmind-redis.service` | `127.0.0.1:6381`, separate persistence at `/var/lib/helixmind-redis` |
| PostgreSQL | database and role `helixmind` | Unix-socket peer authentication; no other database is used |
| Reasoning runtime | `/opt/HelixMind/.runtime` | owner `helixmind`; private PeTTa/OmegaClaw plus a separate `omegaclaw-venv`; no public listener |

The service templates live in `deploy/systemd/` and the isolated Redis
configuration lives in `deploy/redis/`. Runtime configuration is held in
`/etc/helixmind/helixmind.env`, outside Git. It contains the HelixMind-only
provider credentials when configured and is never read into application logs.

The versioned HelixMind Nginx template is `deploy/nginx/helix-mind.duckdns.org`.
The public health route was checked separately from the local health route and
returned HTTP 200 on 2026-08-24. This confirms routing for the health probe, not
complete production readiness for every authenticated workflow.

The worker now calls only the official PubMed and Europe PMC public APIs for
its literature stage. It has no public listener and no change to the shared
VPS routing configuration.
