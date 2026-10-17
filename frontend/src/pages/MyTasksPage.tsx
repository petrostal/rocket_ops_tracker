import { CalendarClock, CalendarDays, CircleAlert, Inbox } from 'lucide-react';
import { useMemo } from 'react';
import { PageHeader } from '../components/PageHeader';
import { TaskCard } from '../components/TaskCard';
import { TagFilter } from '../components/Tags';
import { useTasks } from '../hooks/useTasks';
import { useStoredState } from '../hooks/useStoredState';
import type { Tag, TaskStatus, TaskSummary } from '../types';

const tabs: { value: TaskStatus | ''; label: string }[] = [{ value: '', label: 'Активные' }, { value: 'TODO', label: 'Нужно сделать' }, { value: 'IN_PROGRESS', label: 'В работе' }, { value: 'WAITING', label: 'Ожидание' }, { value: 'REVIEW', label: 'Проверка' }, { value: 'DONE', label: 'Готово' }];

type Participation = 'assigned' | 'created' | 'watching';
interface StoredMyTaskFilters { tab: TaskStatus | ''; tags: string[]; participation: Participation }

const emptyMyTaskFilters: StoredMyTaskFilters = { tab: '', tags: [], participation: 'assigned' };
const myTaskStatuses = new Set<TaskStatus>(['TODO', 'IN_PROGRESS', 'WAITING', 'REVIEW', 'DONE']);

function parseMyTaskFilters(value: unknown): StoredMyTaskFilters | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  return {
    participation: item.participation === 'created' || item.participation === 'watching' ? item.participation : 'assigned',
    tab: typeof item.tab === 'string' && myTaskStatuses.has(item.tab as TaskStatus) ? item.tab as TaskStatus : '',
    tags: Array.isArray(item.tags) ? item.tags.filter((tag): tag is string => typeof tag === 'string').slice(0, 50) : [],
  };
}

export function MyTasksPage({ tags, userId, onCreate, onOpen }: { tags: Tag[]; userId: number; onCreate: () => void; onOpen: (task: TaskSummary) => void }) {
  const [filters, setFilters] = useStoredState(`filters:my:${userId}`, emptyMyTaskFilters, parseMyTaskFilters);
  const { tab, tags: selectedTags, participation } = filters;
  const setTab = (next: TaskStatus | '') => setFilters((current) => ({ ...current, tab: next }));
  const setSelectedTags = (next: string[]) => setFilters((current) => ({ ...current, tags: next }));
  const params = useMemo(() => { const p = new URLSearchParams({ participation, limit: '500' }); if (tab) p.set('status', tab); else ['TODO','IN_PROGRESS','WAITING','REVIEW'].forEach((s) => p.append('status', s)); selectedTags.forEach((tag) => p.append('tag', tag)); return p; }, [tab, selectedTags, participation]);
  const { items, loading, error } = useTasks(params);
  const groups = groupTasks(items);
  return <div className="page my-page"><PageHeader title="Мои задачи" subtitle="То, что требует вашего внимания" onCreate={onCreate} /><div className="participation-tabs" aria-label="Моё участие">{([{ value: 'assigned', label: 'Назначены мне' }, { value: 'created', label: 'Созданы мной' }, { value: 'watching', label: 'Наблюдаю' }] as const).map((item) => <button key={item.value} type="button" aria-pressed={participation === item.value} onClick={() => setFilters((current) => ({ ...current, participation: item.value }))}>{item.label}</button>)}</div><div className="tabs">{tabs.map((item) => <button className={tab === item.value ? 'active' : ''} key={item.value} onClick={() => setTab(item.value)}>{item.label}</button>)}</div><TagFilter tags={tags} selected={selectedTags} onChange={setSelectedTags} />{error && <div className="inline-error">{error}</div>}{loading ? <div className="empty-state">Загрузка…</div> : <div className="my-groups">{groups.map((group) => <section key={group.label} className="task-group"><header><group.icon size={18} /><h2>{group.label}</h2><span>{group.tasks.length}</span></header><div className="my-task-grid">{group.tasks.map((task) => <TaskCard key={task.id} task={task} onOpen={onOpen} />)}</div></section>)}{items.length === 0 && <div className="empty-state"><h3>Всё спокойно</h3><p>У вас нет задач по выбранному фильтру.</p></div>}</div>}</div>;
}

function groupTasks(tasks: TaskSummary[]) {
  const now = new Date(); const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1); const week = new Date(today); week.setDate(today.getDate() + 7);
  const definitions = [
    { label: 'Просроченные', icon: CircleAlert, test: (task: TaskSummary) => !!task.due_date && new Date(task.due_date) < today },
    { label: 'Сегодня', icon: CalendarClock, test: (task: TaskSummary) => !!task.due_date && new Date(task.due_date) >= today && new Date(task.due_date) < tomorrow },
    { label: 'Предстоящие', icon: CalendarDays, test: (task: TaskSummary) => !!task.due_date && new Date(task.due_date) >= tomorrow && new Date(task.due_date) < week },
    { label: 'Позже', icon: CalendarDays, test: (task: TaskSummary) => !!task.due_date && new Date(task.due_date) >= week },
    { label: 'Без срока', icon: Inbox, test: (task: TaskSummary) => !task.due_date },
  ];
  return definitions.map((group) => ({ ...group, tasks: tasks.filter(group.test) })).filter((group) => group.tasks.length);
}
