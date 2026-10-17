import type { AccessMode, AccessUser, Tag, Task, TaskDraft, TaskList, TaskStatus, TaskSummary, User } from '../types';

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : 'Ошибка запроса');
  }
}

function cookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`));
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (init.method && init.method !== 'GET') headers.set('X-CSRF-Token', cookie('opstracker_csrf'));
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' });
  if (!response.ok) {
    let payload: { detail?: unknown } = {};
    try { payload = await response.json() as { detail?: unknown }; } catch { /* empty response */ }
    throw new ApiError(response.status, payload.detail ?? response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<User>('/api/users/me'),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  users: (search = '') => request<User[]>(`/api/users${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  watcherCandidates: (search = '') => request<User[]>(`/api/users?watcher_candidates=true&search=${encodeURIComponent(search)}`),
  accessUsers: () => request<AccessUser[]>('/api/access/users'),
  updateAccess: (id: number, access_mode: AccessMode, tag_ids: number[], view_created_tasks: boolean, view_watched_tasks: boolean) => request<AccessUser>(`/api/access/users/${id}`, { method: 'PATCH', body: JSON.stringify({ access_mode, tag_ids, view_created_tasks, view_watched_tasks }) }),
  syncUsers: () => request<{ synchronized: number }>('/api/users/sync', { method: 'POST' }),
  tags: () => request<Tag[]>('/api/tags'),
  tasks: (params: URLSearchParams) => request<TaskList>(`/api/tasks?${params.toString()}`),
  task: (id: number) => request<Task>(`/api/tasks/${id}`),
  createTask: (draft: TaskDraft) => request<Task>('/api/tasks', { method: 'POST', body: JSON.stringify(draft) }),
  updateTask: (id: number, patch: Record<string, unknown>) => request<Task>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  addComment: (id: number, body: string) => request<Task>(`/api/tasks/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) }),
  uploadAttachment: (id: number, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Task>(`/api/tasks/${id}/attachments`, { method: 'POST', body });
  },
  deleteAttachment: (taskId: number, attachmentId: number) => request<Task>(`/api/tasks/${taskId}/attachments/${attachmentId}`, { method: 'DELETE' }),
  action: (id: number, action: 'take' | 'start' | 'wait' | 'review' | 'complete' | 'reopen') => request<Task>(`/api/tasks/${id}/${action}`, { method: 'POST' }),
  deleteTask: (id: number) => request<void>(`/api/tasks/${id}`, { method: 'DELETE' }),
  moveTask: (task: TaskSummary, status: TaskStatus) => {
    const action: Record<TaskStatus, 'start' | 'wait' | 'review' | 'complete' | 'reopen'> = {
      TODO: 'reopen', IN_PROGRESS: 'start', WAITING: 'wait', REVIEW: 'review', DONE: 'complete',
    };
    return api.action(task.id, action[status]);
  },
};
