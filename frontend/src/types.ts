export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'WAITING' | 'REVIEW' | 'DONE';
export type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';
export type AccessMode = 'NONE' | 'ASSIGNED' | 'TAGS' | 'ASSIGNED_OR_TAGS' | 'ALL';

export interface User {
  id: number;
  rocket_chat_user_id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: number;
  event_type: string;
  actor: User | null;
  created_at: string;
  event_metadata: Record<string, unknown>;
}

export interface TaskComment {
  id: number;
  body: string;
  author: User;
  created_at: string;
}

export interface TaskAttachment {
  id: number;
  original_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: User;
  created_at: string;
}

export interface Tag {
  id: number;
  name: string;
}

export interface AccessUser extends User {
  access_mode: AccessMode;
  access_tags: Tag[];
}

export interface TaskSummary {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority;
  creator: User;
  assignee: User | null;
  created_at: string;
  updated_at: string;
  due_date: string | null;
  completed_at: string | null;
  rocket_chat_room_id: string | null;
  rocket_chat_room_name: string | null;
  rocket_chat_room_type: string | null;
  rocket_chat_message_id: string | null;
  rocket_chat_thread_id: string | null;
  rocket_chat_message_url: string | null;
  rocket_chat_message_author_id: string | null;
  rocket_chat_message_author_username: string | null;
  rocket_chat_message_timestamp: string | null;
  rocket_chat_message_snippet: string | null;
  tags: Tag[];
}

export interface Task extends TaskSummary {
  events: TaskEvent[];
  comments: TaskComment[];
  attachments: TaskAttachment[];
}

export interface TaskList {
  items: TaskSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface TaskDraft {
  title: string;
  description: string;
  priority: Priority;
  assignee_id: number | null;
  due_date: string | null;
  tags: string[];
  rocket_chat_room_id?: string | null;
  rocket_chat_room_name?: string | null;
}
