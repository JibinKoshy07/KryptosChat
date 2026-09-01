export type Role = "admin" | "user";

export interface UserSummary {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
}

export interface UserOut extends UserSummary {
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserSummary;
}

export interface ConversationUser {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
  last_seen_at: string | null;
  online: boolean;
}

export interface Conversation {
  id: number;
  created_at: string;
  updated_at: string;
  members: ConversationUser[];
  last_message: LastMessage | null;
  unread_count: number;
}

export interface LastMessage {
  id: number;
  sender_id: number;
  message_type: MessageType;
  content: string;
  created_at: string;
}

export type MessageType = "text" | "image" | "video" | "file";

export interface Attachment {
  id: number;
  message_id: number;
  original_filename: string;
  mime_type: string;
  size: number;
  created_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender_id: number;
  message_type: MessageType;
  content: string;
  attachment: Attachment | null;
  created_at: string;
  edited_at: string | null;
  deleted_at: string | null;
  delivered: boolean;
  read: boolean;
}

export interface MessagePage {
  items: Message[];
  next_cursor: number | null;
  has_more: boolean;
}