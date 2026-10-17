import { ChevronRight, MessageSquare } from 'lucide-react';
import { useDeferredValue, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { Filters, emptyFilters, parseFilterState, toParams } from '../components/Filters';
import { PageHeader } from '../components/PageHeader';
import { formatDate } from '../components/TaskCard';
import { TagList } from '../components/Tags';
import { useTasks } from '../hooks/useTasks';
import { useStoredState } from '../hooks/useStoredState';
import type { Tag, Task, TaskSummary, User } from '../types';

const status = { TODO: 'Нужно сделать', IN_PROGRESS: 'В работе', WAITING: 'Ожидание', REVIEW: 'Проверка', DONE: 'Готово' } as const;
const priority = { LOW: 'Низкий', NORMAL: 'Обычный', HIGH: 'Высокий', CRITICAL: 'Критичный' } as const;

interface Props {
  users: User[];
  tags: Tag[];
  userId: number;
  selectedId: number | null;
  selectedTask: Task | null;
  detail: ReactNode;
  onCloseTask: () => void;
  onCreate: () => void;
  onOpen: (task: TaskSummary) => void;
}

export function AllTasksPage({ users, tags, userId, selectedId, selectedTask, detail, onCloseTask, onCreate, onOpen }: Props) {
  const [filters, setFilters] = useStoredState(`filters:all:${userId}`, emptyFilters, parseFilterState);
  const search = useDeferredValue(filters.search);
  const params = useMemo(() => toParams({ ...filters, search }), [filters, search]);
  const { items, setItems, total, loading, error } = useTasks(params);
  const activeItem = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (selectedTask) setItems((current) => current.map((task) => task.id === selectedTask.id ? selectedTask : task));
  }, [selectedTask, setItems]);
  useEffect(() => {
    if (!loading) activeItem.current?.scrollIntoView({ block: 'nearest' });
  }, [selectedId, loading]);
  const split = selectedId !== null;
  return <div className={`page list-page${split ? ' has-task-panel' : ''}`}>
    <PageHeader title="Все задачи" subtitle={`${total} задач в системе`} onCreate={onCreate} />
    <Filters value={filters} users={users} tags={tags} onChange={setFilters} />
    {error ? <div className="inline-error" role="alert">{error}</div> : null}
    {split ? <div className="tasks-workspace">
      <nav className="task-switcher" aria-label="Список задач">
        <header><strong>Задачи</strong><span className="section-count">{total}</span></header>
        <div className="task-switcher-scroll" aria-busy={loading}>
          {loading ? <p className="task-switcher-message" role="status">Загрузка списка…</p> : items.length ? items.map((item) => {
            const task = selectedTask?.id === item.id ? selectedTask : item;
            return <button key={task.id} ref={task.id === selectedId ? activeItem : undefined} type="button" className="task-switcher-item" aria-current={task.id === selectedId ? 'true' : undefined} onClick={() => onOpen(task)}>
              <span className="task-switcher-meta"><span>#{task.id}</span><span className={`priority-text ${task.priority.toLowerCase()}`}>{priority[task.priority]}</span></span>
              <strong>{task.title}</strong>
              <span className="task-switcher-meta"><span className={`status-text ${task.status.toLowerCase()}`}><i />{status[task.status]}</span><span className="task-switcher-assignee">{task.assignee ? `@${task.assignee.username}` : 'Не назначен'}</span></span>
              <TagList tags={task.tags} />
            </button>;
          }) : <p className="task-switcher-message">Задачи не найдены. Измените фильтры.</p>}
          {!loading && items.length > 0 && !items.some((task) => task.id === selectedId) ? <p className="task-switcher-message">Открытая задача не входит в текущий список.</p> : null}
        </div>
      </nav>
      {detail ?? <section className="task-panel-loading" aria-label="Загрузка задачи"><p role="status">Загрузка задачи #{selectedId}…</p><button className="button secondary small" onClick={onCloseTask}>Вернуться к списку</button></section>}
    </div> : <div className="task-table-wrap"><table className="task-table"><thead><tr><th>Задача</th><th>Статус</th><th>Исполнитель</th><th>Приоритет</th><th>Срок</th><th>Источник</th><th /></tr></thead><tbody>{loading ? <tr><td colSpan={7} className="empty-cell">Загрузка…</td></tr> : items.map((task) => <tr key={task.id} onClick={() => onOpen(task)}><td><span className="table-id">#{task.id}</span><button className="table-task-title" type="button">{task.title}</button><TagList tags={task.tags} /></td><td><span className={`status-text ${task.status.toLowerCase()}`}><i />{status[task.status]}</span></td><td>{task.assignee ? `@${task.assignee.username}` : <span className="muted">Не назначен</span>}</td><td><span className={`priority-text ${task.priority.toLowerCase()}`}>{task.priority}</span></td><td>{task.due_date ? formatDate(task.due_date) : '—'}</td><td>{task.rocket_chat_room_name ? <span className="room-source"><MessageSquare size={14} />#{task.rocket_chat_room_name}</span> : '—'}</td><td><ChevronRight size={17} /></td></tr>)}</tbody></table>{!loading && items.length === 0 && <div className="empty-state"><h3>Задачи не найдены</h3><p>Измените фильтры или создайте новую задачу.</p></div>}</div>}
  </div>;
}
