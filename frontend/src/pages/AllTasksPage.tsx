import { ChevronRight, MessageSquare } from 'lucide-react';
import { useDeferredValue, useMemo } from 'react';
import { Filters, emptyFilters, parseFilterState, toParams } from '../components/Filters';
import { PageHeader } from '../components/PageHeader';
import { formatDate } from '../components/TaskCard';
import { TagList } from '../components/Tags';
import { useTasks } from '../hooks/useTasks';
import { useStoredState } from '../hooks/useStoredState';
import type { Tag, TaskSummary, User } from '../types';

const status = { TODO: 'Нужно сделать', IN_PROGRESS: 'В работе', WAITING: 'Ожидание', REVIEW: 'Проверка', DONE: 'Готово' } as const;

export function AllTasksPage({ users, tags, userId, onCreate, onOpen }: { users: User[]; tags: Tag[]; userId: number; onCreate: () => void; onOpen: (task: TaskSummary) => void }) {
  const [filters, setFilters] = useStoredState(`filters:all:${userId}`, emptyFilters, parseFilterState);
  const search = useDeferredValue(filters.search);
  const params = useMemo(() => toParams({ ...filters, search }), [filters, search]);
  const { items, total, loading, error } = useTasks(params);
  return <div className="page list-page"><PageHeader title="Все задачи" subtitle={`${total} задач в системе`} onCreate={onCreate} /><Filters value={filters} users={users} tags={tags} onChange={setFilters} />{error && <div className="inline-error">{error}</div>}<div className="task-table-wrap"><table className="task-table"><thead><tr><th>Задача</th><th>Статус</th><th>Исполнитель</th><th>Приоритет</th><th>Срок</th><th>Источник</th><th /></tr></thead><tbody>{loading ? <tr><td colSpan={7} className="empty-cell">Загрузка…</td></tr> : items.map((task) => <tr key={task.id} onClick={() => onOpen(task)}><td><span className="table-id">#{task.id}</span><strong>{task.title}</strong><TagList tags={task.tags} /></td><td><span className={`status-text ${task.status.toLowerCase()}`}><i />{status[task.status]}</span></td><td>{task.assignee ? `@${task.assignee.username}` : <span className="muted">Не назначен</span>}</td><td><span className={`priority-text ${task.priority.toLowerCase()}`}>{task.priority}</span></td><td>{task.due_date ? formatDate(task.due_date) : '—'}</td><td>{task.rocket_chat_room_name ? <span className="room-source"><MessageSquare size={14} />#{task.rocket_chat_room_name}</span> : '—'}</td><td><ChevronRight size={17} /></td></tr>)}</tbody></table>{!loading && items.length === 0 && <div className="empty-state"><h3>Задачи не найдены</h3><p>Измените фильтры или создайте новую задачу.</p></div>}</div></div>;
}
