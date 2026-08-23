import { DndContext, PointerSensor, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { MoreVertical, Plus } from 'lucide-react';
import { useDeferredValue, useMemo, useState } from 'react';
import { api, ApiError } from '../api/client';
import { Filters, emptyFilters, parseFilterState, toParams } from '../components/Filters';
import { PageHeader } from '../components/PageHeader';
import { TaskCard } from '../components/TaskCard';
import { usePaginatedTasks } from '../hooks/usePaginatedTasks';
import { useTasks } from '../hooks/useTasks';
import { useStoredState } from '../hooks/useStoredState';
import type { Tag, Task, TaskStatus, User } from '../types';

const columns: { status: TaskStatus; label: string }[] = [
  { status: 'TODO', label: 'Нужно сделать' }, { status: 'IN_PROGRESS', label: 'В работе' },
  { status: 'WAITING', label: 'Ожидание' }, { status: 'REVIEW', label: 'Проверка' },
  { status: 'DONE', label: 'Готово' },
];
const activeStatuses: TaskStatus[] = ['TODO', 'IN_PROGRESS', 'WAITING', 'REVIEW'];
const donePageSize = 10;

export function KanbanPage({ users, tags, userId, onCreate, onOpen }: { users: User[]; tags: Tag[]; userId: number; onCreate: () => void; onOpen: (task: Task) => void }) {
  const [filters, setFilters] = useStoredState(`filters:kanban:${userId}`, emptyFilters, parseFilterState);
  const deferredSearch = useDeferredValue(filters.search);
  const baseParams = useMemo(() => {
    const next = toParams({ ...filters, search: deferredSearch });
    next.delete('status');
    next.delete('limit');
    return next;
  }, [filters, deferredSearch]);
  const activeEnabled = filters.status !== 'DONE';
  const doneEnabled = !filters.overdue && (filters.status === '' || filters.status === 'DONE');
  const activeParams = useMemo(() => {
    const next = new URLSearchParams(baseParams);
    const statuses = filters.status && filters.status !== 'DONE' ? [filters.status] : activeStatuses;
    statuses.forEach((status) => next.append('status', status));
    next.set('limit', '500');
    return next;
  }, [baseParams, filters.status]);
  const doneParams = useMemo(() => {
    const next = new URLSearchParams(baseParams);
    next.set('status', 'DONE');
    return next;
  }, [baseParams]);
  const active = useTasks(activeParams, activeEnabled);
  const done = usePaginatedTasks(doneParams, donePageSize, doneEnabled);
  const items = useMemo(() => [...active.items, ...done.items], [active.items, done.items]);
  const [moveError, setMoveError] = useState('');
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const move = async (event: DragEndEvent) => {
    if (!event.over) return;
    const task = event.active.data.current?.task as Task | undefined;
    const target = event.over.id as TaskStatus;
    if (!task || task.status === target) return;
    const beforeActive = active.items;
    const beforeDone = done.items;
    const optimistic = { ...task, status: target, completed_at: target === 'DONE' ? new Date().toISOString() : null };
    active.setItems((current) => current.filter((item) => item.id !== task.id).concat(target !== 'DONE' && activeEnabled ? optimistic : []));
    done.setItems((current) => target === 'DONE' && doneEnabled ? [optimistic, ...current.filter((item) => item.id !== task.id)].slice(0, Math.max(donePageSize, current.length)) : current.filter((item) => item.id !== task.id));
    try {
      await api.moveTask(task, target);
      setMoveError('');
      await Promise.all([active.refresh(true), done.refresh(true)]);
    } catch (reason) {
      active.setItems(beforeActive);
      done.setItems(beforeDone);
      setMoveError(reason instanceof ApiError ? reason.message : 'Не удалось переместить задачу');
    }
  };
  return (
    <div className="page kanban-page">
      <PageHeader title="Канбан" subtitle="Операционные задачи команды" onCreate={onCreate} />
      <Filters value={filters} users={users} tags={tags} onChange={setFilters} compact />
      {(active.error || done.error || moveError) && <div className="inline-error">{active.error || done.error || moveError}</div>}
      {(active.loading || done.loading) ? <Loading /> : <DndContext sensors={sensors} onDragEnd={(event) => void move(event)}><div className="kanban-board">{columns.map((column) => <KanbanColumn key={column.status} {...column} tasks={items.filter((task) => task.status === column.status)} total={column.status === 'DONE' ? done.total : undefined} loadingMore={column.status === 'DONE' && done.loadingMore} onLoadMore={column.status === 'DONE' ? done.loadMore : undefined} onOpen={onOpen} onCreate={onCreate} />)}</div></DndContext>}
    </div>
  );
}

function KanbanColumn({ status, label, tasks, total, loadingMore = false, onLoadMore, onOpen, onCreate }: { status: TaskStatus; label: string; tasks: Task[]; total?: number; loadingMore?: boolean; onLoadMore?: () => void; onOpen: (task: Task) => void; onCreate: () => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const taskTotal = total ?? tasks.length;
  const hasMore = tasks.length < taskTotal;
  return <section ref={setNodeRef} className={`kanban-column status-${status.toLowerCase()} ${isOver ? 'is-over' : ''}`}><header><div><i className="status-square" /><h2>{label}</h2><span>{taskTotal}</span></div><button className="icon-button" aria-label="Меню колонки"><MoreVertical size={18} /></button></header><div className="column-tasks">{tasks.map((task) => <TaskCard key={task.id} task={task} onOpen={onOpen} />)}{tasks.length === 0 && <div className="column-empty">Перетащите задачу сюда</div>}</div>{onLoadMore && hasMore ? <button className="show-more-tasks" disabled={loadingMore} onClick={onLoadMore}>{loadingMore ? 'Загрузка…' : 'Показать ещё'}</button> : null}<button className="add-column-task" onClick={onCreate}><Plus size={16} />Добавить задачу</button></section>;
}

function Loading() { return <div className="loading-grid">{[1,2,3,4,5].map((i) => <div key={i}><span /><span /><span /></div>)}</div>; }
