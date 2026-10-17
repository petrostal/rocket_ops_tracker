import { useDraggable } from '@dnd-kit/core';
import { CalendarDays, GripVertical, MessageSquare } from 'lucide-react';
import type { CSSProperties } from 'react';
import type { TaskSummary } from '../types';
import { initials } from './AppShell';
import { TagList } from './Tags';

const priorityLabels = { LOW: 'Низкий', NORMAL: 'Обычный', HIGH: 'Высокий', CRITICAL: 'Критичный' } as const;

export function TaskCard({ task, onOpen, draggable = false }: { task: TaskSummary; onOpen: (task: TaskSummary) => void; draggable?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id, data: { task }, disabled: !draggable });
  const style: CSSProperties = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : {};
  const overdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'DONE';
  return (
    <article ref={setNodeRef} style={style} className={`task-card priority-${task.priority.toLowerCase()} ${isDragging ? 'dragging' : ''}`}>
      <div className="card-head">
        {draggable ? <button className="drag-handle" aria-label={`Переместить задачу ${task.id}`} {...listeners} {...attributes}>
          <GripVertical size={16} />
        </button> : null}
        <span className="task-id">#{task.id}</span>
        <span className={`priority-label ${task.priority.toLowerCase()}`}><i />{priorityLabels[task.priority]}</span>
      </div>
      <button className="card-title" onClick={() => onOpen(task)}>{task.title}</button>
      <TagList tags={task.tags} />
      <div className="card-meta">
        {task.assignee ? (
          <span className="assignee"><span className="avatar">{initials(task.assignee.display_name)}</span>@{task.assignee.username}</span>
        ) : <span className="muted">Не назначена</span>}
        {task.due_date && <span className={overdue ? 'overdue' : ''}><CalendarDays size={15} />{formatDate(task.due_date)}</span>}
        {task.rocket_chat_room_name && <span><MessageSquare size={14} />#{task.rocket_chat_room_name}</span>}
      </div>
    </article>
  );
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(new Date(value));
}
