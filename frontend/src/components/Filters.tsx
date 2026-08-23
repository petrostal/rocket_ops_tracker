import { CalendarRange, Search, SlidersHorizontal, X } from 'lucide-react';
import type { Priority, Tag, TaskStatus, User } from '../types';
import { TagFilter } from './Tags';

export interface FilterState {
  search: string;
  status: TaskStatus | '';
  priority: Priority | '';
  assignee: string;
  overdue: boolean;
  tags: string[];
}

export const emptyFilters: FilterState = { search: '', status: '', priority: '', assignee: '', overdue: false, tags: [] };

const taskStatuses = new Set<TaskStatus>(['TODO', 'IN_PROGRESS', 'WAITING', 'REVIEW', 'DONE']);
const priorities = new Set<Priority>(['LOW', 'NORMAL', 'HIGH', 'CRITICAL']);

export function parseFilterState(value: unknown): FilterState | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  const status = typeof item.status === 'string' && taskStatuses.has(item.status as TaskStatus) ? item.status as TaskStatus : '';
  const priority = typeof item.priority === 'string' && priorities.has(item.priority as Priority) ? item.priority as Priority : '';
  return {
    search: typeof item.search === 'string' ? item.search.slice(0, 500) : '',
    status,
    priority,
    assignee: typeof item.assignee === 'string' ? item.assignee.slice(0, 64) : '',
    overdue: item.overdue === true,
    tags: Array.isArray(item.tags) ? item.tags.filter((tag): tag is string => typeof tag === 'string').slice(0, 50) : [],
  };
}

export function Filters({ value, users, tags, onChange, compact = false }: { value: FilterState; users: User[]; tags: Tag[]; onChange: (value: FilterState) => void; compact?: boolean }) {
  const set = <K extends keyof FilterState>(key: K, next: FilterState[K]) => onChange({ ...value, [key]: next });
  return (
    <div className={`filters ${compact ? 'compact' : ''}`}>
      <label className="search-field"><Search size={18} /><input value={value.search} onChange={(e) => set('search', e.target.value)} placeholder="Поиск задач…" /></label>
      <label><SlidersHorizontal size={16} /><select value={value.assignee} onChange={(e) => set('assignee', e.target.value)}><option value="">Исполнитель: все</option><option value="unassigned">Без исполнителя</option>{users.map((user) => <option key={user.id} value={String(user.id)}>@{user.username}</option>)}</select></label>
      <label><select value={value.priority} onChange={(e) => set('priority', e.target.value as Priority | '')}><option value="">Приоритет: все</option><option value="LOW">Низкий</option><option value="NORMAL">Обычный</option><option value="HIGH">Высокий</option><option value="CRITICAL">Критичный</option></select></label>
      <label><select value={value.status} onChange={(e) => set('status', e.target.value as TaskStatus | '')}><option value="">Статус: все</option><option value="TODO">Нужно сделать</option><option value="IN_PROGRESS">В работе</option><option value="WAITING">Ожидание</option><option value="REVIEW">Проверка</option><option value="DONE">Готово</option></select></label>
      <label className={`toggle-filter ${value.overdue ? 'selected' : ''}`}><CalendarRange size={16} /><input type="checkbox" checked={value.overdue} onChange={(e) => set('overdue', e.target.checked)} />Просроченные</label>
      <TagFilter tags={tags} selected={value.tags} onChange={(selected) => set('tags', selected)} />
      {JSON.stringify(value) !== JSON.stringify(emptyFilters) && <button className="reset-filter" onClick={() => onChange(emptyFilters)}><X size={15} />Сбросить</button>}
    </div>
  );
}

export function toParams(filters: FilterState, extra?: Record<string, string>): URLSearchParams {
  const params = new URLSearchParams(extra);
  if (filters.search.trim()) params.set('search', filters.search.trim());
  if (filters.status) params.set('status', filters.status);
  if (filters.priority) params.set('priority', filters.priority);
  if (filters.assignee) params.set('assignee', filters.assignee);
  if (filters.overdue) params.set('overdue', 'true');
  filters.tags.forEach((tag) => params.append('tag', tag));
  params.set('limit', '500');
  return params;
}
