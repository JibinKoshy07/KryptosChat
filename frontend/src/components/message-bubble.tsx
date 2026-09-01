"use client";

import type { Message } from "@/types";
import { getAccessToken } from "@/lib/api";

const MESSAGE_ICONS = {
  text: "",
  image: "📷",
  video: "🎥",
  file: "📎",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function mediaUrl(att: { id: number }): string {
  const token = getAccessToken();
  return `/api/v1/media/${att.id}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

export function MessageBubble({ message, mine }: { message: Message; mine: boolean }) {
  const content =
    message.content || `${MESSAGE_ICONS[message.message_type]} ${message.attachment?.original_filename ?? "attachment"}`;

  return (
    <div className={`flex justify-end gap-2 ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[70%] rounded-2xl px-3 py-2 break-words ${
        mine ? "bg-ac-DEFAULT text-white" : "bg-surface-DEFAULT text-text-DEFAULT"
      }`}>
        {message.message_type === "image" && message.attachment ? (
          <img
            className="mt-1 max-w-60 rounded-lg"
            src={`${mediaUrl(message.attachment)}?auth=${encodeURIComponent(JSON.stringify({"Authorization": authHeaders().authorization}))}`}
            alt={message.attachment.original_filename}
          />
        ) : null}
        {message.message_type === "video" && message.attachment ? (
          <video
            className="mt-1 max-w-72 rounded-lg"
            src={mediaUrl(message.attachment)}
            controls
          />
        ) : null}
        {message.message_type === "file" && message.attachment ? (
          <a
            className="mt-1 block text-sm underline"
            href={`${mediaUrl(message.attachment)}?download=1`}
            download={message.attachment.original_filename}
          >
            {MESSAGE_ICONS.file} {message.attachment.original_filename} · {humanSize(message.attachment.size)}
          </a>
        ) : null}
        {message.message_type === "text" || !message.attachment ? <div className="text-sm">{content}</div> : null}
        {mine ? (
          <div className="text-[10px] text-right opacity-70">
            {formatTime(message.created_at)} {message.read ? "✓✓" : message.delivered ? "✓✓" : "✓"}
          </div>
        ) : (
          <div className="text-[10px] text-right opacity-60">{formatTime(message.created_at)}</div>
        )}
      </div>
    </div>
  );
}