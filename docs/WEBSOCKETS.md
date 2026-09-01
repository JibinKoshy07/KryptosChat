# WebSocket API

WebSocket endpoints require an **access token** in the `?token=` query param
or an `Authorization: Bearer` header.

## Endpoints

### `/ws/chat/{conversation_id}`

Real-time messaging and read receipts for one conversation.

### `/ws/presence`

Real-time online/offline notifications for the user's contacts.

## Client → Server Messages

| `type` | Fields | Notes |
|--------|--------|-------|
| `message` | `content`, `message_type` ("text"), `temp_id` | Send a text message |
| `read` | `message_ids` | Mark messages read |
| `typing` | `conversation_id` | Typing indicator |
| `ping` | — | Heartbeat (refreshes presence TTL) |

## Server → Client Messages

| `type` | Fields |
|--------|--------|
| `message_new` | `message` (decrypted), `temp_id` |
| `message_delivered` | `message_ids` |
| `message_read` | `message_ids`, `user_id` |
| `typing` | `user_id`, `conversation_id` |
| `presence` | `user_id`, `online` |
| `conversation` | `conversation` (snapshot on connect/reconnect) |
| `pong` | — |
| `error` | `error` |

`message_new` events fan out to **all** conversation members (including the
sender, who gets the ack). `presence` events are sent to the user's contacts.

## Multi-Instance Fan-Out

Events are published to Redis channels (`events:chat`, `events:presence`).
Each backend instance subscribes and relays to its own local connections for
the targeted `user_ids`, so a message sent on one instance reaches recipients
on any instance. Each WebSocket connection receives each event exactly once.

## Reconnect & Delivery Guarantees

- The client reconnects with **exponential backoff** (1s → 30s cap).
- On reconnect, the server sends a fresh `conversation` snapshot and the
  client re-fetches the message page, so no messages are lost.
- `message_new` events carry `message.id` and the sender's `temp_id`; the
  client deduplicates by id/temp_id.
- **Messages are persisted before fan-out.** The REST `POST /messages/{id}`
  path is also available as a fallback.

## Heartbeat / Presence

- The client sends a JSON `ping` every ~30s while idle; this refreshes the
  Redis presence TTL and returns `pong`.
- Presence is keyed per user with a Redis set of connection ids. A user is
  online while the set is non-empty. Multiple tabs/devices share one entry;
  presence only flips offline when the last live connection goes away or its
  TTL expires (connection loss without a clean close).