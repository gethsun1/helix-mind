# HelixMind infrastructure boundary

HelixMind is an isolated tenant on a shared VPS. Its current private services
are intentionally not exposed through Nginx yet.

| Resource | Identity | Binding / ownership |
| --- | --- | --- |
| API | `helixmind-api.service` | `127.0.0.1:8401`, user `helixmind` |
| Worker | `helixmind-worker.service` | RQ queue `helixmind-research`, user `helixmind` |
| Redis | `helixmind-redis.service` | `127.0.0.1:6381`, separate persistence at `/var/lib/helixmind-redis` |
| PostgreSQL | database and role `helixmind` | Unix-socket peer authentication; no other database is used |
| Reasoning runtime | `/opt/HelixMind/.runtime` | owner `helixmind`; no public listener |

The service templates live in `deploy/systemd/` and the isolated Redis
configuration lives in `deploy/redis/`. Runtime configuration is held in
`/etc/helixmind/helixmind.env`, outside Git. It contains no provider key by
default.

No HelixMind Nginx virtual host or TLS certificate has been created. This is
deliberate: expose `helix-mind.duckdns.org` only after the first complete
investigation vertical slice is verified locally.
