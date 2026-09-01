"use client";

import { useEffect, useRef } from "react";

import { Composer } from "@/components/composer";
import { MessageBubble } from "@/components/message-bubble";
import type { Conversation, Message } from "@/types";

export function ChatWindow({
  conversation,
  messages,
  presence,
  currentUser,
  onSend,
  onAttach,
}: {
  conversation: Conversation | null;
  messages: Message[];
  presence: Record<number, boolean>;
  currentUser: { id: number; display_name: string };
  onSend: (content: string) => void;
  onAttach: (file: File) => void;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length, conversation?.id]);

  if (!conversation) {
    return (
      <section className="flex flex-1 items-center justify-center bg-bg-deeper text-text-muted">
        Select a conversation to start chatting.
      </section>
    );
  }

  const other = conversation.members[0];
  const online = other && (presence[other.id] ?? other.online);

  return (
    <section className="flex flex-1 flex-col bg-bg-deeper">
      <header className="flex items-center gap-2 border-b border-surface-DEFAULT px-4 py-2.5 bg-bg-deeper">
        <div className="text-base font-medium text-text-DEFAULT">{other?.display_name ?? "User"}</div>
        <span className="text-xs text-text-muted">
          {online ? "Online" : "Offline"}
        </span>
        {online ? <span className="inline-block h-2 w-2 rounded-full bg-ac-DEFAULT" /> : null}
        <div className="flex-1" />
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((m) => (
          <div key={m.id} className="mb-2">
            <MessageBubble message={m} mine={m.sender_id === currentUser.id} />
          </div>
        ))}
      </div>

      <Composer onSend={onSend} onAttach={onAttach} />
    </section>
  );
}