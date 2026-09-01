"use client";

import { useEffect, useState } from "react";

import {
  fetchMessages,
  getAccessToken,
  listConversations,
  uploadMedia,
} from "@/lib/api";
import { WsClient } from "@/lib/ws";
import type { Conversation, Message } from "@/types";

export interface ChatState {
  conversations: Conversation[];
  active: Conversation | null;
  messages: Message[];
  presence: Record<number, boolean>;
}

/**
 * Owns the chat session: conversation list, active thread, message store,
 * and the WebSocket connections for messaging + presence.
 */
export function useChat() {
  const [state, setState] = useState<ChatState>({
    conversations: [],
    active: null,
    messages: [],
    presence: {},
  });
  const chatWs = useRef<WsClient | null>(null);
  const presenceWs = useRef<WsClient | null>(null);
  const activeIdRef = useRef<number | null>(null);

  useEffect(() => {
    activeIdRef.current = state.active?.id ?? null;
  }, [state.active]);

  async function refreshConversations(): Promise<void> {
    try {
      const conversations = await listConversations();
      setState((s) => ({ ...s, conversations }));
    } catch {
      /* the ws reconnect handler will retry */
    }
  }

  async function openConversation(id: number): Promise<void> {
    const page = await fetchMessages(id);
    setState((s) => {
      const active = s.conversations.find((c) => c.id === id);
      return { ...s, active: active ?? s.active, messages: page.items };
    });
  }

  function handleWsMessage(data: Record<string, unknown>): void {
    const type = data.type as string;
    if (type === "message_new") {
      const msg = data.message as Message;
      if (!msg) {
        return;
      }
      setState((s) => {
        const activeId = activeIdRef.current;
        const isActive = activeId === msg.conversation_id;
        const messages = isActive ? [...s.messages, msg] : s.messages;
        return { ...s, messages };
      });
      void refreshConversations();
    } else if (type === "message_delivered" || type === "message_read") {
      const ids = (data.message_ids as number[]) ?? [];
      setState((s) => ({ ...s }));
      void refreshConversations();
      void ids;
    } else if (type === "presence") {
      const userId = data.user_id as number;
      setState((s) => ({ ...s, presence: { ...s.presence, [userId]: data.online === true } }));
    } else if (type === "conversation") {
      const conv = data.conversation as Conversation;
      if (conv) {
        setState((s) => ({
          ...s,
          conversations: s.conversations.map((c) => (c.id === conv.id ? conv : c)),
        }));
      }
    }
  }

  function connect(): void {
    chatWs.current?.close();
    presenceWs.current?.close();
    const access = () => getAccessToken();
    chatWs.current = new WsClient(`/ws/chat/{0}`.replace("{0}", String(activeIdRef.current ?? 0)), access, handleWsMessage, refreshConversations);
    presenceWs.current = new WsClient("/ws/presence", access, handleWsMessage, () => {});
    chatWs.current.connect();
    presenceWs.current.connect();
  }

  async function send(content: string): Promise<void> {
    const activeId = activeIdRef.current;
    if (!activeId || !content.trim()) {
      return;
    }
    const tempId = `${Date.now()}-${Math.random()}`;
    chatWs.current?.send({
      type: "message",
      content,
      message_type: "text",
      temp_id: tempId,
    });
    void sendMessage(activeId, content).catch(() => {}); // ensure delivery on reconnect
  }

  async function attach(file: File): Promise<void> {
    const activeId = activeIdRef.current;
    if (!activeId) {
      return;
    }
    const msg = await uploadMedia(activeId, file);
    setState((s) => ({ ...s, messages: [...s.messages, msg] }));
    void refreshConversations();
  }

  function markActiveRead(): void {
    const activeId = activeIdRef.current;
    const ids = state.messages.filter((m) => !m.read && !m.delivered).map((m) => m.id);
    if (!activeId || ids.length === 0) {
      return;
    }
    chatWs.current?.send({ type: "read", message_ids: ids });
  }

  useEffect(() => {
    void refreshConversations();
    connect();
    return () => {
      chatWs.current?.close();
      presenceWs.current?.close();
    };
  }, []);

  useEffect(() => {
    if (state.active) {
      chatWs.current?.close();
      const access = () => getAccessToken();
      chatWs.current = new WsClient(`/ws/chat/${state.active.id}`, access, handleWsMessage, () => void openConversation(state.active!.id));
      chatWs.current.connect();
      void openConversation(state.active.id);
      markActiveRead();
    }
  }, [state.active?.id]);

  return {
    ...state,
    openConversation,
    send,
    attach,
    markActiveRead,
    reconnect: connect,
    authHeaders,
  };
}

import { useRef } from "react";