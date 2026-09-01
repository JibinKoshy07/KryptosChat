# Architecture

Krypte is a self-hosted, real-time chat platform designed for **security,
reliability, and horizontal scalability**. It is a 2-tier web app (frontend +
backend) with Redis enabling real-time fan-out and presence, PostgreSQL as
the source of truth, and a pluggable encrypted media store.

## Services

| Service | Role |
|---------|------|
| Next.js | Browser UI; static + a thin `/api/*` reverse proxy |
| FastAPI | REST API + WebSockets; business logic; encryption |
| PostgreSQL | Persistent normalized data (users, conversations, messages, attachments) |
| Redis | Presence registry, rate limiting, Pub/Sub fan-out, temp caches |
| Nginx | Reverse proxy; TLS/WSS termination |
| Media storage | Encrypted local filesystem or S3/MinIO (pluggable) |

## Request Path

```
Browser → Next.js (same origin) → proxy /api/* → FastAPI → PostgreSQL/Redis
Browser → /ws/*  → nginx → FastAPI WebSocket → Redis (pub/sub fan-out)
```

Because the browser only talks to the Next.js origin, CORS is avoided and the
HttpOnly refresh cookie (scoped to `/api/v1`) works through the proxy.

## Real-Time Layer

- **WebSocket connections**: `WebSocketManager` (in-memory registry) per user
  (multi-tab). `Redis` tracks presence keys.
- **Fan-out**: on a message/event, the backend **publishes** to a Redis
  channel; **every** backend instance subscribes and relays to its own local
  connections for the target `user_ids`. This is what makes multi-instance
  horizontal scaling work: no shared in-memory state needed for delivery.
- **Durability**: messages are **persisted before fan-out**; on reconnect the
  server sends a snapshot and the client re-fetches the page.
- **Presence**: `presence:user:{id}` is a Redis set of connection ids with a
  TTL refreshed by heartbeat. Online ⇔ set non-empty.

## Data Model

- `users` — id, username (unique), display_name, password_hash (argon2id),
  role, is_active, timestamps, last_seen_at.
- `conversations` — 1:1 chat thread.
- `conversation_members` — M2M user↔conversation (unique pair).
- `messages` — conversation_id, sender_id, message_type,
  encrypted_content (AES-256-GCM), optional attachment_id, timestamps,
  soft-delete.
- `message_receipts` — per-user delivered_at/read_at.
- `attachments` — encrypted_storage_key, storage_backend,
  original_filename, mime_type, size, encryption_metadata.

Schema is managed with Alembic (`backend/migrations`).

## Storage Abstraction

`app/storage/` defines a `StorageBackend` interface with `local` (encrypted
filesystem) and `s3` (MinIO/S3) implementations, selected by
`MEDIA_STORAGE_BACKEND`. The app streams encrypted chunks through
`MediaEncryptor`/`MediaDecryptor`; backends never see plaintext. Switching
providers (local ⇄ S3) requires only a config change.

## Security Model

See `docs/ENCRYPTION.md`. In short: Argon2id passwords, short-lived JWT
access tokens + HttpOnly refresh cookie, AES-256-GCM at rest for messages and
media, TLS/WSS in production, Redis rate limiting, MIME/size validation, and
structured logging that never logs secrets.

## Scaling Notes

- Stateless backend → add replicas; Redis Pub/Sub fans out to all.
- Media under S3/MinIO → replicas share storage.
- Postgres/Redis → managed or operator-managed for HA.
- Nginx → replace with an Ingress/LB in Kubernetes (see `docs/DEPLOYMENT.md`).