# API Reference

Interactive docs: `GET /api/docs` (Swagger UI), `GET /api/redoc`.

Base path: `/api/v1`. All protected endpoints require an access token in the
`Authorization: Bearer <token>` header. Role checks (admin/user) run via
FastAPI dependencies (`app/api/deps.py`).

## Authentication

### POST `/auth/login`

Body: `{ "username": string, "password": string }`

- Sets an HttpOnly `krypte_refresh` cookie on `/api/v1`.
- Returns `{ "access_token": string, "token_type": "bearer", "user": UserSummary }`.
- Rate-limited (Redis) with a per-username lockout (`LOGIN_MAX_ATTEMPTS`,
  `LOGIN_LOCKOUT_MINUTES`).

### POST `/auth/refresh`

- Reads the refresh cookie; issues a new access/refresh pair.
- Returns the same `TokenResponse`.

### POST `/auth/logout`

- Clears the refresh cookie. Requires auth.

### GET `/auth/me`

- Returns the current user's profile. Requires auth.

## Users (admin)

All routes below require an **admin** token.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/users` | List users |
| POST | `/users` | Create user `{ username, display_name, password, role }` |
| PATCH | `/users/{id}` | Update `{ display_name?, password?, role?, is_active? }` |
| DELETE | `/users/{id}` | Hard-delete user (204) |
| POST | `/users/{id}/disable` | Disable |
| POST | `/users/{id}/enable` | Enable |
| POST | `/users/{id}/reset-password` | Reset password (query `new_password`) |

`GET /users/me` returns the current user's own profile (any authenticated
user) — this is the endpoint the frontend `/chat` uses.

## Conversations

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/conversations` | List the current user's conversations (newest first) |
| POST | `/conversations` | Create/join a 1:1 chat `{ user_ids: [otherUserId] }` |
| GET | `/conversations/{id}` | Fetch a single conversation (member only) |

`Conversation` includes `members` (with `online` presence), `last_message`,
and `unread_count`.

## Messages

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/messages/{conversationId}?before=<id>&limit=<n>` | Paginated message list (member only) |
| POST | `/messages/{conversationId}` | Send a text message `{ content, message_type }` |
| DELETE | `/messages/{convId}/{messageId}` | Soft-delete a message (sender only) |

`GET` returns `{ items: Message[], next_cursor, has_more }` (oldest-first,
cursor-based). Media messages are created by `POST /media/{convId}`.

## Media

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/media/{conversationId}` | Upload an image/video/file (multipart `file`) — streamed, encrypted |
| GET | `/media/{attachmentId}` | Streamed encrypted download (member only) |

`GET /media/{attachmentId}` supports an access token in the `Authorization`
header or a `?token=` query param (for in-browser `<img>`/`<video>` tags).

## Admin

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/dashboard` | Stats: total/active/online users, conversations, messages, storage, recent activity |

Admin-only.

## Health

`GET /health` returns `{ status, database, redis }` (no auth). Used by Docker
health checks.

## Errors

Errors are returned as:

```json
{ "error": { "code": "not_found", "detail": "..." } }
```

with proper HTTP status codes (401/403/404/409/429/400/500).