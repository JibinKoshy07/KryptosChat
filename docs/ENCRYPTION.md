# Encryption Model

Krypte encrypts sensitive chat data **at rest** with **AES-256-GCM**, a
modern authenticated-encryption mode. It does **not** rely on base64 or
client-side visual obfuscation. This document explains what is encrypted,
where encryption happens, where keys live, how they are rotated, and what
happens if a key is lost.

## Layers

The system separates:

| Layer | Mechanism | Notes |
|-------|-----------|-------|
| Authentication | Argon2id password hashing + JWT (HS256) | Passwords never stored in plaintext |
| Transport | HTTPS / WSS (TLS 1.2+) at nginx | All production traffic encrypted |
| Database encryption | AES-256-GCM per message | `messages.encrypted_content` |
| Media encryption | AES-256-GCM per chunk + HMAC-SHA256 | Encrypted blobs on storage |
| Message encryption | Same as database encryption (server-side) | Re-encrypted on write |
| Key management | Env-vars / secret manager | See below |

The system is a **server-side, at-rest** encryption design: the server holds
the encryption keys and encrypts/decrypts messages. It does **not** provide
true end-to-end encryption (E2EE). This is a deliberate, documented trade-off:
it allows search, delivery/read receipts, and multi-device sync without a
separate key-management protocol. If E2EE is later required, the primitives
used here (HKDF, AES-256-GCM, HMAC-SHA256) are the building blocks of
established protocols like the Signal double-ratchet, and the storage/API
layer is already key-agnostic.

## What Is Encrypted

- **Message content**: `messages.encrypted_content` holds only ciphertext (+
  nonce/salt). The `messages` table has no plaintext content column.
- **Uploaded media**: files (images/videos/documents) are encrypted before
  they touch the storage backend. The storage layer (filesystem, S3, MinIO)
  only ever sees opaque encrypted blobs; `original_filename`, `mime_type`,
  and `size` are metadata (non-secret) columns.
- **Not encrypted** (metadata, deliberately): conversation ids, member lists,
  timestamps, delivery/read state, display names, usernames. This metadata is
  required for listing, presence, and receipts.

## Where Encryption Happens

- **Message write path**: `app/services/messages.py` → `encrypt_message()`
  before the ORM insert.
- **Message read path**: `app/services/messages.py::to_out()` →
  `decrypt_message()` before returning to the client.
- **Media write path**: `app/services/media.py::store_upload()` wraps the
  incoming stream with `MediaEncryptor`, chunk by chunk.
- **Media read path**: `app/services/media.py::stream_download_response()`
  wraps the storage read with `MediaDecryptor`, chunk by chunk.
- **Crypto primitives**: `app/services/crypto.py`.

All crypto is implemented with the `cryptography` library (AESGCM, HKDF,
HMAC) — no bespoke crypto is invented.

## Key Management

| Key | Env var | Length | Purpose |
|-----|---------|--------|---------|
| Station AAD key | `MESSAGE_ENCRYPTION_KEY_BASE64` | 32 bytes | AAD bound into every message |
| Message master key | `MESSAGE_MASTER_KEY_BASE64` | 32 bytes | Derives per-message data keys (HKDF) |
| Media KDF master key | `MEDIA_KDF_MASTER_KEY_BASE64` | 32 bytes | Derives per-file keys (HKDF) |
| Media HMAC key | `MEDIA_KDF_AUTH_KEY_BASE64` | 32 bytes | Authenticates the whole media blob |
| JWT secret | `JWT_SECRET` | 32+ bytes | Signs access/refresh tokens |
| Session secret | `SESSION_SECRET` | 32+ bytes | Signing refresh cookie implicitly |

- Keys are **never hardcoded**; they are read from the environment (`.env` or
  a secret manager such as HashiCorp Vault / Docker secrets / AWS Secrets
  Manager / Kubernetes Secrets).
- For production, prefer a **secret manager** and inject values as env vars at
  container start. Never mount `.env` into images.

**Generate keys:**

```bash
python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
# repeat for each *KEY_BASE64*
python -c "import secrets; print(secrets.token_urlsafe(48))"
# for JWT_SECRET / SESSION_SECRET
```

## Key Rotation

Key rotation relies on **key separation + per-message salts**, so rotating
a master key is **not** a full re-encryption emergency:

1. Each message uses a random salt to derive a per-message key. Old messages
   stay decryptable with the old master key.
2. To rotate, introduce a **new** master key and keep the **old** one for
   decryption for an overlap window (dual keys). New writes use the new key;
   old reads fall back to the old key.
3. After the overlap expires, you may re-encrypt old records with the new key
   (a migration job) and then remove the old key.

Recommended rotation schedule: **JWT/session secrets** on a shorter cadence
(immediately on compromise); **message/media master keys** on a longer
cadence or after a suspected compromise.

**On a key rotation (dual-key procedure):**

- Store both the new and old key (e.g. `..._NEW`, `..._OLD`) in the secret
  manager.
- Update `app/services/crypto.py` to prefer the new key for encryption and to
  fall back to the old key on decrypt failure.
- Run a re-encryption job to migrate records, then remove the old key.

## What Happens If a Key Is Lost

- **Message master key lost**: message bodies become **permanently
  undecryptable** (GCM integrity check fails). There is no recovery.
- **Media KDF master key lost**: media blobs become undecryptable.
- **JWT secret lost**: all access/refresh tokens are invalid — users must log
  in again. This is non-destructive.

> **Backups must be protected with the keys.** Backing up the encrypted
> database/media without the encryption keys yields ciphertext you cannot
> read.

## Backups

- Back up PostgreSQL (`pg_dump`), the media storage volume, `.env`, and any
  secret-manager entries **together**.
- Restore requires the **same** encryption keys that were in use when the
  backup was taken.
- Consider wrapping the backup with its own transport/disk encryption and
  storing keys in a separate, access-controlled location.

## Threat Model / Limitations

- **Server can read messages**: the backend holds the keys. Admins/operators
  with key access can decrypt. This is standard for at-rest encryption but is
  **not** E2EE.
- **Metadata is not encrypted**: timestamps, member lists, presence, and
  receipts are visible to the server.
- **Trust the host**: keys live in the environment of the process. A
  compromised host with access to the keys and the DB can decrypt at rest.

See `docs/ARCHITECTURE.md` for the broader system design.