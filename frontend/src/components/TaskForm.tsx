import { CalendarDays, Trash2, UploadCloud, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Priority, Tag, Task, TaskDraft, User } from '../types';
import { DescriptionEditor } from './TaskDescription';
import { TagEditor } from './Tags';
import { WatcherEditor } from './WatcherEditor';

interface Props {
  users: User[];
  tags: Tag[];
  onClose: () => void;
  onCreated: (task: Task) => void;
  roomId?: string | null;
  roomName?: string | null;
}

export function TaskForm({ users, tags, onClose, onCreated, roomId, roomName }: Props) {
  const [draft, setDraft] = useState<TaskDraft>({ title: '', description: '', priority: 'NORMAL', assignee_id: null, due_date: null, tags: [], watcher_ids: [] });
  const [photos, setPhotos] = useState<File[]>([]);
  const [createdTask, setCreatedTask] = useState<Task | null>(null);
  const [draggingPhotos, setDraggingPhotos] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const photoInput = useRef<HTMLInputElement>(null);
  const close = () => createdTask ? onCreated(createdTask) : onClose();
  const set = <K extends keyof TaskDraft>(key: K, value: TaskDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const addPhotos = (incoming: File[]) => {
    setDraggingPhotos(false);
    const valid = incoming.filter((file) => file.type.startsWith('image/') && file.size <= 25 * 1024 * 1024);
    if (valid.length !== incoming.length) setError('Можно добавить только изображения размером до 25 МБ');
    else setError('');
    setPhotos((current) => {
      const keys = new Set(current.map(fileKey));
      return [...current, ...valid.filter((file) => !keys.has(fileKey(file)))];
    });
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    let task = createdTask;
    try {
      if (!task) {
        task = await api.createTask({ ...draft, due_date: draft.due_date ? new Date(`${draft.due_date}T23:59:00`).toISOString() : null });
        setCreatedTask(task);
      }
      for (const photo of photos) {
        task = await api.uploadAttachment(task.id, photo);
        setCreatedTask(task);
        setPhotos((current) => current.filter((item) => fileKey(item) !== fileKey(photo)));
      }
      onCreated(task);
    } catch (reason) {
      const message = reason instanceof ApiError ? readableError(reason) : 'Операция не выполнена';
      setError(task ? `Задача #${task.id} создана, но фото не загрузилось: ${message}` : `Не удалось создать задачу: ${message}`);
    } finally { setSaving(false); }
  };
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <form className="task-modal" onSubmit={(event) => void submit(event)}>
        <header><div><h2>Создать задачу</h2></div><button type="button" className="icon-button" onClick={close} aria-label="Закрыть"><X /></button></header>
        <div className="form-body">
          <label className="field"><span>Название</span><input autoFocus required maxLength={500} value={draft.title} onChange={(e) => set('title', e.target.value)} placeholder="Что нужно сделать?" /></label>
          <div className="field"><span>Описание</span><DescriptionEditor value={draft.description} onChange={(value) => set('description', value)} rows={5} disabled={saving} placeholder="Добавьте важные детали" /></div>
          <div className="field"><span>Теги</span><TagEditor value={draft.tags} suggestions={tags} onChange={(value) => set('tags', value)} disabled={saving} /></div>
          <div className="field photo-field">
            <span>Фотографии</span>
            <input ref={photoInput} className="attachment-input" type="file" accept="image/*" multiple onChange={(e) => { addPhotos([...(e.target.files ?? [])]); e.target.value = ''; }} />
            <div
              className={`photo-dropzone ${draggingPhotos ? 'dragging' : ''} ${saving ? 'disabled' : ''}`}
              role="button"
              tabIndex={saving ? -1 : 0}
              aria-label="Добавить фотографии"
              onClick={() => { if (!saving) photoInput.current?.click(); }}
              onKeyDown={(e) => { if (!saving && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); photoInput.current?.click(); } }}
              onDragEnter={(e) => { e.preventDefault(); if (!saving) setDraggingPhotos(true); }}
              onDragOver={(e) => e.preventDefault()}
              onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDraggingPhotos(false); }}
              onDrop={(e) => { e.preventDefault(); if (!saving) addPhotos([...e.dataTransfer.files]); }}
            >
              <UploadCloud size={24} />
              <div><strong>Перетащите фотографии сюда</strong><span>или нажмите, чтобы выбрать · до 25 МБ</span></div>
            </div>
            {photos.length ? <div className="photo-preview-list" aria-label={`Выбрано фотографий: ${photos.length}`}>{photos.map((photo) => <SelectedPhoto key={fileKey(photo)} file={photo} disabled={saving} onRemove={() => setPhotos((current) => current.filter((item) => fileKey(item) !== fileKey(photo)))} />)}</div> : null}
          </div>
          <div className="form-grid">
            <label className="field"><span>Исполнитель</span><select value={draft.assignee_id ?? ''} onChange={(e) => set('assignee_id', e.target.value ? Number(e.target.value) : null)}><option value="">Не назначен</option>{users.map((user) => <option key={user.id} value={user.id}>@{user.username} — {user.display_name}</option>)}</select></label>
            <label className="field"><span>Приоритет</span><select value={draft.priority} onChange={(e) => set('priority', e.target.value as Priority)}><option value="LOW">Низкий</option><option value="NORMAL">Обычный</option><option value="HIGH">Высокий</option><option value="CRITICAL">Критичный</option></select></label>
            <label className="field date-field"><span>Срок</span><CalendarDays size={17} /><input type="date" value={draft.due_date ?? ''} onChange={(e) => set('due_date', e.target.value || null)} /></label>
          </div>
          {(roomName || roomId) && <div className="source-hint">Источник: Rocket.Chat #{roomName || roomId}</div>}
          <section className="field"><span>Наблюдатели</span><WatcherEditor value={draft.watcher_ids} users={users} onChange={(ids) => set('watcher_ids', ids)} disabled={saving || !!createdTask} /></section>
          {error && <p className="form-error" role="alert">{error}</p>}
        </div>
        <footer><button type="button" className="button secondary" onClick={close}>{createdTask ? 'Открыть задачу' : 'Отмена'}</button><button className="button primary" disabled={saving || !draft.title.trim()}>{saving ? (createdTask ? 'Загружаем фото…' : 'Создаём…') : createdTask ? 'Повторить загрузку' : photos.length ? `Создать и загрузить фото (${photos.length})` : 'Создать задачу'}</button></footer>
      </form>
    </div>
  );
}

function SelectedPhoto({ file, disabled, onRemove }: { file: File; disabled: boolean; onRemove: () => void }) {
  const [preview] = useState(() => URL.createObjectURL(file));
  useEffect(() => () => URL.revokeObjectURL(preview), [preview]);
  return <article className="photo-preview"><img src={preview} alt="" /><div><strong title={file.name}>{file.name}</strong><span>{formatFileSize(file.size)}</span></div><button type="button" className="icon-button danger-icon" onClick={onRemove} disabled={disabled} aria-label={`Удалить ${file.name}`}><Trash2 size={15} /></button></article>;
}

function fileKey(file: File): string { return `${file.name}:${file.size}:${file.lastModified}`; }

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function readableError(error: ApiError): string {
  if (typeof error.detail === 'object' && error.detail && 'message' in error.detail) return String((error.detail as { message: unknown }).message);
  return error.message;
}
