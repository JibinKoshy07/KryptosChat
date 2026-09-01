"use client";

import type { Conversation } from "@/types";

function previewText(c: Conversation): string {
  const last = c.last_message;
  if (!last) {
    return "";
  }
  if (last.message_type === "text") {
    return last.content;
  }
  return { image: "📷 Photo", video: "🎥 Video", file: "📎 File" }[last.message_type] ?? "";
}

function timeLabel(c: Conversation): string {
  if (!c.last_message?.created_at) {
    return "";
  }
  const d = new Date(c.last_message.created_at);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function Sidebar({
  conversations,
  activeId,
  presence,
  onSelect,
  currentUser,
}: {
  conversations: Conversation[];
  activeId: number | null;
  presence: Record<number, boolean>;
  onSelect: (id: number) => void;
  currentUser: { display_name: string; role: string };
}) {
  return (
    <aside className="flex w-72 flex-col bg-bg-panel border-r border-surface-DEFAULT">
      <header className="flex items-center gap-2 px-4 py-3">
        <span className="text-lg font-bold text-text-DEFAULT">Krypte</span>
        <div className="flex-1" />
        <div className="text-xs text-text-muted">{currentUser.display_name}</div>
      </header>

      <input
        className="m-2 w-full rounded-md bg-bg-deeper px-3 py-1.5 text-sm text-text-muted placeholder:text-text-faint"
        placeholder="Search…"
      />

      <div className="overflow-y-auto flex-1">
        {conversations.map((c) => {
          const other = c.members[0];
          const active = other && (presence[other.id] ?? other.online);
          return (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`flex w-full items-center gap-3 px-4 py-2.5 text-left ${
                c.id === activeId ? "bg-surface-hover" : "bg-bg-panel hover:bg-surface-hover"
              }`}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-DEFAULT font-semibold text-text-DEFAULT">
                {other?.display_name?.[0]?.toUpperCase() ?? "?"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-text-DEFAULT">
                  {other?.display_name ?? "Unknown"}
                </span>
                <span className="block truncate text-xs text-text-muted">{previewText(c)}</span>
              </span>
              <span className="flex flex-col items-end">
                <span className="text-[11px] text-text-faint">{timeLabel(c)}</span>
                {active ? (
                  <span className="mt-1 inline-block h-2 w-2 rounded-full bg-ac-DEFAULT" />
                ) : null}
                {c.unread_count > 0 ? (
                  <span className="mt-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-ac-muted px-1.5 text-[10px] text-white">
                    {c.unread_count}
                  </span>
                ) : null}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}