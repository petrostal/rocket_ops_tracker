import { CalendarDays, Check, Download, ExternalLink, FileText, MessageSquare, Paperclip, Pencil, Play, Send, Trash2, UploadCloud, UserPlus, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Priority, Tag, Task, TaskStatus, User } from '../types';
import { initials } from './AppShell';
import { CommentBody } from './CommentBody';
import { DescriptionEditor, TaskDescription, toggleChecklistItem } from './TaskDescription';
import { TagEditor, TagList } from './Tags';

const statusLabels: Record<TaskStatus, string> = { TODO: 'Нужно сделать', IN_PROGRESS: 'В работе', WAITING: 'Ожидание', REVIEW: 'Проверка', DONE: 'Готово' };
const eventLabels: Record<string, string> = {
  task_created: 'создал(а) задачу', task_updated: 'обновил(а) задачу', assigned: 'назначил(а) исполнителя',
  unassigned: 'снял(а) исполнителя', status_changed: 'изменил(а) статус', priority_changed: 'изменил(а) приоритет',
  due_date_changed: 'изменил(а) срок', completed: 'завершил(а) задачу', reopened: 'вернул(а) задачу в работу', deleted: 'удалил(а) задачу',
  comment_added: 'добавил(а) комментарий',
  tags_changed: 'изменил(а) теги',
  attachment_added: 'добавил(а) вложение',
  attachment_deleted: 'удалил(а) вложение',
};

export function TaskDrawer({ task: initial, user, users, availableTags, onClose, onChanged, onDeleted }: { task: Task; user: User; users: User[]; availableTags: Tag[]; onClose: () => void; onChanged: (task: Task) => void; onDeleted: (id: number) => void }) {
  const [task, setTask] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [tags, setTags] = useState(initial.tags.map((tag) => tag.name));
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [draggingFile, setDraggingFile] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => { setTask(initial); setTitle(initial.title); setDescription(initial.description); setTags(initial.tags.map((tag) => tag.name)); }, [initial]);
  const canEdit = user.is_admin || task.creator.id === user.id || task.assignee?.id === user.id;
  const canAssign = user.is_admin || task.creator.id === user.id;
  const apply = async (operation: () => Promise<Task>) => {
    setBusy(true); setError('');
    try { const next = await operation(); setTask(next); onChanged(next); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Операция не выполнена'); }
    finally { setBusy(false); }
  };
  const saveText = async () => {
    await apply(() => api.updateTask(task.id, { title, description, tags }));
    setEditing(false);
  };
  const remove = async () => {
    if (!window.confirm(`Удалить задачу #${task.id}?`)) return;
    setBusy(true);
    try { await api.deleteTask(task.id); onDeleted(task.id); onClose(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Не удалось удалить задачу'); setBusy(false); }
  };
  const addComment = async () => {
    const body = comment.trim();
    if (!body) return;
    setBusy(true); setError('');
    try {
      const next = await api.addComment(task.id, body);
      setTask(next); onChanged(next); setComment('');
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Не удалось добавить комментарий');
    } finally {
      setBusy(false);
    }
  };
  const uploadFiles = async (files: File[]) => {
    if (!files.length || busy) return;
    setBusy(true); setUploading(true); setError('');
    try {
      let next = task;
      for (const file of files) {
        next = await api.uploadAttachment(task.id, file);
        setTask(next); onChanged(next);
      }
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить файл');
    } finally {
      setBusy(false); setUploading(false); setDraggingFile(false);
    }
  };
  const removeAttachment = async (id: number, name: string) => {
    if (!window.confirm(`Удалить вложение «${name}»?`)) return;
    await apply(() => api.deleteAttachment(task.id, id));
  };
  const toggleChecklist = async (lineIndex: number, checked: boolean) => {
    const nextDescription = toggleChecklistItem(task.description, lineIndex, checked);
    await apply(() => api.updateTask(task.id, { description: nextDescription }));
  };
  return (
    <div className="drawer-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="task-drawer" aria-label={`Задача ${task.id}`}>
        <header className="drawer-header">
          <div><span className="drawer-id">#{task.id}</span>{editing ? <input className="drawer-title-input" value={title} onChange={(e) => setTitle(e.target.value)} /> : <h2>{task.title}</h2>}</div>
          <div className="drawer-head-actions">
            {canEdit && <button className="button secondary small" onClick={() => editing ? void saveText() : setEditing(true)} disabled={busy}>{editing ? <Check size={16} /> : <Pencil size={16} />}{editing ? 'Сохранить' : 'Редактировать'}</button>}
            {user.is_admin && <button className="icon-button danger-icon" onClick={() => void remove()} title="Удалить"><Trash2 size={18} /></button>}
            <button className="icon-button" onClick={onClose} aria-label="Закрыть"><X /></button>
          </div>
        </header>
        <div className="drawer-scroll">
          <section className="properties-grid">
            <label><span>Статус</span><select value={task.status} disabled={!canEdit || busy} onChange={(e) => void apply(() => api.moveTask(task, e.target.value as TaskStatus))}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label><span>Приоритет</span><select value={task.priority} disabled={!user.is_admin || busy} onChange={(e) => void apply(() => api.updateTask(task.id, { priority: e.target.value as Priority }))}><option value="LOW">Низкий</option><option value="NORMAL">Обычный</option><option value="HIGH">Высокий</option><option value="CRITICAL">Критичный</option></select></label>
            <label><span>Исполнитель</span><select value={task.assignee?.id ?? ''} disabled={!canAssign || busy} onChange={(e) => void apply(() => api.updateTask(task.id, { assignee_id: e.target.value ? Number(e.target.value) : null }))}><option value="">Не назначен</option>{users.map((item) => <option key={item.id} value={item.id}>@{item.username}</option>)}</select></label>
            <label className="date-property"><span>Срок</span><CalendarDays size={17} /><input type="date" disabled={!user.is_admin || busy} value={task.due_date?.slice(0, 10) ?? ''} onChange={(e) => void apply(() => api.updateTask(task.id, { due_date: e.target.value ? new Date(`${e.target.value}T23:59:00`).toISOString() : null }))} /></label>
            <label><span>Создатель</span><div className="creator-property"><span className="avatar">{initials(task.creator.display_name)}</span><strong>{task.creator.display_name}</strong><small>@{task.creator.username}</small></div></label>
          </section>

          <section className="drawer-section tags-section"><h3>Теги</h3>{editing ? <TagEditor value={tags} suggestions={availableTags} onChange={setTags} disabled={busy} /> : <TagList tags={task.tags} empty />}</section>

          <section className="drawer-section"><h3>Описание</h3>{editing ? <DescriptionEditor value={description} onChange={setDescription} rows={6} disabled={busy} /> : <TaskDescription value={task.description} disabled={!canEdit || busy} onToggle={(lineIndex, checked) => void toggleChecklist(lineIndex, checked)} />}</section>

          {task.rocket_chat_room_id && <section className="drawer-section source-section"><h3><MessageSquare size={18} />Источник: Rocket.Chat</h3><div className="source-card"><div className="source-meta"><span>Комната<strong>#{task.rocket_chat_room_name || task.rocket_chat_room_id}</strong></span><span>Автор<strong>@{task.rocket_chat_message_author_username || 'неизвестен'}</strong></span>{task.rocket_chat_message_timestamp && <span>Сообщение<strong>{formatDateTime(task.rocket_chat_message_timestamp)}</strong></span>}</div>{task.rocket_chat_message_snippet && <blockquote>{task.rocket_chat_message_snippet}</blockquote>}{task.rocket_chat_message_url && <a href={task.rocket_chat_message_url} target="_blank" rel="noreferrer">Открыть сообщение <ExternalLink size={14} /></a>}</div></section>}

          <section className="drawer-section attachments-section">
            <h3><Paperclip size={17} />Вложения <span className="section-count">{task.attachments.length}</span></h3>
            <input ref={fileInput} className="attachment-input" type="file" multiple onChange={(e) => { void uploadFiles([...(e.target.files ?? [])]); e.target.value = ''; }} />
            <div
              className={`attachment-dropzone ${draggingFile ? 'dragging' : ''} ${busy ? 'disabled' : ''}`}
              role="button"
              tabIndex={busy ? -1 : 0}
              aria-label="Добавить вложение"
              onClick={() => { if (!busy) fileInput.current?.click(); }}
              onKeyDown={(e) => { if (!busy && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); fileInput.current?.click(); } }}
              onDragEnter={(e) => { e.preventDefault(); if (!busy) setDraggingFile(true); }}
              onDragOver={(e) => { e.preventDefault(); }}
              onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDraggingFile(false); }}
              onDrop={(e) => { e.preventDefault(); void uploadFiles([...e.dataTransfer.files]); }}
            >
              <UploadCloud size={25} />
              <div><strong>{uploading ? 'Загрузка…' : 'Перетащите файлы сюда'}</strong><span>или нажмите, чтобы выбрать · до 25 МБ</span></div>
            </div>
            {task.attachments.length ? <div className="attachments-list">{task.attachments.map((attachment) => {
              const downloadUrl = `/api/tasks/${task.id}/attachments/${attachment.id}/download`;
              const isImage = attachment.content_type.startsWith('image/');
              return <article className={`attachment-row ${isImage ? 'has-image' : ''}`} key={attachment.id}>
                <span className="attachment-file-icon">{isImage ? <img src={downloadUrl} alt="" loading="lazy" /> : <FileText size={18} />}</span>
                <div><strong title={attachment.original_name}>{attachment.original_name}</strong><span>{formatFileSize(attachment.size_bytes)} · @{attachment.uploaded_by.username} · {formatDateTime(attachment.created_at)}</span></div>
                <a className="icon-button" href={downloadUrl} title="Скачать" aria-label={`Скачать ${attachment.original_name}`}><Download size={16} /></a>
                {(user.is_admin || task.creator.id === user.id || attachment.uploaded_by.id === user.id) ? <button className="icon-button danger-icon" onClick={() => void removeAttachment(attachment.id, attachment.original_name)} disabled={busy} title="Удалить" aria-label={`Удалить ${attachment.original_name}`}><Trash2 size={15} /></button> : null}
                {isImage ? <a className="attachment-image-preview" href={downloadUrl} target="_blank" rel="noreferrer" aria-label={`Открыть ${attachment.original_name}`}><img src={downloadUrl} alt={attachment.original_name} loading="lazy" decoding="async" /></a> : null}
              </article>;
            })}</div> : null}
          </section>

          <section className="drawer-section comments-section">
            <h3><MessageSquare size={17} />Комментарии <span className="section-count">{task.comments.length}</span></h3>
            <div className="comment-form">
              <textarea
                rows={3}
                value={comment}
                maxLength={10000}
                placeholder="Напишите комментарий…"
                onChange={(e) => setComment(e.target.value)}
                onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') void addComment(); }}
              />
              <div><small>Ctrl/⌘ + Enter — отправить</small><button className="button primary small" disabled={busy || !comment.trim()} onClick={() => void addComment()}><Send size={15} />Добавить</button></div>
            </div>
            <div className="comments-list">
              {task.comments.length ? [...task.comments].reverse().map((item) => (
                <article className="comment-row" key={item.id}>
                  <span className="avatar">{initials(item.author.display_name)}</span>
                  <div className="comment-content">
                    <header><strong>{item.author.display_name}</strong><span>@{item.author.username}</span><time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time></header>
                    <CommentBody body={item.body} />
                  </div>
                </article>
              )) : <p className="muted comments-empty">Комментариев пока нет</p>}
            </div>
          </section>

          <section className="drawer-section"><h3>История активности</h3><div className="activity-list">{task.events.length ? [...task.events].reverse().map((event) => <div className="activity-row" key={event.id}><span className="avatar">{initials(event.actor?.display_name || '?')}</span><div><p><strong>@{event.actor?.username || 'system'}</strong> {eventLabels[event.event_type] || event.event_type}</p><small>{formatDateTime(event.created_at)}</small></div></div>) : <p className="muted">Событий пока нет</p>}</div></section>
          {error && <p className="form-error" role="alert">{error}</p>}
        </div>
        <footer className="drawer-footer">
          {!task.assignee && <button className="button secondary" disabled={busy} onClick={() => void apply(() => api.action(task.id, 'take'))}><UserPlus size={17} />Взять</button>}
          {task.status !== 'IN_PROGRESS' && task.status !== 'DONE' && <button className="button primary" disabled={busy} onClick={() => void apply(() => api.action(task.id, 'start'))}><Play size={17} />Начать</button>}
          {task.status !== 'DONE' && <button className="button success" disabled={busy} onClick={() => void apply(() => api.action(task.id, 'complete'))}><Check size={18} />Завершить</button>}
          {task.status === 'DONE' && user.is_admin && <button className="button primary" disabled={busy} onClick={() => void apply(() => api.action(task.id, 'reopen'))}>Вернуть в работу</button>}
        </footer>
      </aside>
    </div>
  );
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
