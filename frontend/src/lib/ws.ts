import { getAccessToken } from "@/lib/api";

/**
 * A resilient WebSocket client.
 *
 * - Reconnects with exponential backoff when the network drops.
 * - Sends a heartbeat until the server responds.
 * - Supplies a callback ``onOpen`` so the caller can re-fetch conversation
 *   snapshots after a reconnect (fresh message state).
 */
export type WsHandler = (message: Record<string, unknown>) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private shouldRun = true;
  private retries = 0;
  private heartbeatHandle: ReturnType<typeof setInterval> | null = null;
  private heartbeatAlive = false;

  constructor(
    private url: string,
    private token: string | (() => string | null),
    private onMessage: WsHandler,
    private onOpen?: () => void,
  ) {}

  connect(): void {
    this.shouldRun = true;
    this.open();
  }

  private resolveToken(): string | null {
    const t = typeof this.token === "function" ? this.token() : this.token;
    return t || getAccessToken();
  }

  private open(): void {
    const token = this.resolveToken();
    if (!token) {
      if (this.shouldRun) {
        setTimeout(() => this.open(), 1000);
      }
      return;
    }
    const url = `${this.url}${this.url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);
    this.ws.onmessage = (ev) => {
      try {
        this.onMessage(JSON.parse(ev.data as string));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onopen = () => {
      this.retries = 0;
      this.heartbeatAlive = false;
      this.startHeartbeat();
      this.onOpen?.();
    };
    this.ws.onclose = () => this.handleClose();
    this.ws.onerror = () => this.handleClose();
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatHandle = setInterval(async () => {
      if (!this.heartbeatAlive && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30_000);
    this.alivePinger();
  }

  private async alivePinger(): Promise<void> {
    // Mark the connection alive whenever the server replies (any frame).
    const orig = this.onMessage;
    this.onMessage = (m) => {
      this.heartbeatAlive = true;
      orig(m);
    };
  }

  private stopHeartbeat(): void {
    if (this.heartbeatHandle) {
      clearInterval(this.heartbeatHandle);
      this.heartbeatHandle = null;
    }
  }

  private handleClose(): void {
    this.stopHeartbeat();
    this.ws = null;
    if (!this.shouldRun) {
      return;
    }
    const delay = Math.min(1000 * 2 ** this.retries, 30_000);
    this.retries += 1;
    setTimeout(() => this.open(), delay);
  }

  send(payload: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  close(): void {
    this.shouldRun = false;
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
  }
}