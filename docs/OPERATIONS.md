# Operations

## Backup / Restore

**Backups must include the encryption keys.** Without the keys, the encrypted
database and media blobs are unrecoverable ciphertext.

```bash
# 1. Dump PostgreSQL inside the container
docker compose exec postgres pg_dump -U postgres krypte > krypte.sql

# 2. Copy the media storage volume
docker compose run --rm backend cp -a /data/media /backup/media

# 3. Back up the secrets that were in use (keep them out of the repository)
cp .env /backup/.env            # or export from the secret manager
```

Store the SQL dump, media volume, and `.env`/secret-manager entries **together**,
ideally wrapped in your own disk/transport encryption, in an access-controlled
location.

**Restore:**

```bash
# 1. Bring the stack to the same key version that created the backup.
# 2. Restore PostgreSQL
docker compose exec postgres psql -U postgres krypte < krypte.sql

# 3. Restore the media volume
docker compose run --rm backend cp -a /backup/media /data/media
```

## Admin Operations

- **Create user** (dev): `docker compose exec backend python -m scripts.seed`
  seeds the initial admin. For additional users, use the `/admin` panel or
  `POST /api/v1/users`.
- **Reset a user's password**: admin panel or `POST /api/v1/users/{id}/reset-password`.
- **Disable/delete a user**: admin panel (with confirmation) or the API.

## Migrations

```bash
docker compose exec backend alembic upgrade head
# After model changes:
cd backend && alembic revision --autogenerate -m "message"
docker compose exec backend alembic upgrade head
```

## Monitoring

- **Logs**: `docker compose logs -f backend` (structured JSON).
- **Health**: `GET /api/v1/health`.
- **Prometheus/Grafana**: see `docs/DEPLOYMENT.md` (OpenTelemetry).

## Common Issues

### Backend fails to start ("Encryption key is not configured")

The `MESSAGE_*_KEY_BASE64` / `MEDIA_*_KEY_BASE64` values are placeholders in
`.env.example`. Generate real 32-byte keys (see `docs/ENCRYPTION.md`).

### Media not visible in the chat

`GET /media/{id}` requires membership and an access token. If the browser
can't pass the `Authorization` header, ensure the frontend sends the `?token=`
query param (the provided UI does).

### Wrong presence

Presence TTL is refreshed by heartbeat. Multiple tabs share one registry
entry, so presence stays online until the last live connection disappears.