import { RefreshCw, Save, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { initials } from '../components/AppShell';
import type { AccessMode, AccessUser, Tag, User } from '../types';

const modes: Array<{ value: AccessMode; label: string; description: string }> = [
  { value: 'NONE', label: 'Нет доступа', description: 'Не видит ни одной задачи' },
  { value: 'ASSIGNED', label: 'Только назначенные', description: 'Видит задачи, где выбран исполнителем' },
  { value: 'TAGS', label: 'По тегам', description: 'Видит задачи с разрешёнными тегами' },
  { value: 'ASSIGNED_OR_TAGS', label: 'Назначенные или по тегам', description: 'Объединяет оба правила' },
  { value: 'ALL', label: 'Все задачи', description: 'Полный просмотр без административных прав' },
];

function message(reason: unknown): string {
  if (reason instanceof ApiError && typeof reason.detail === 'string') return reason.detail;
  return 'Не удалось выполнить операцию';
}

function AccessRow({ user, tags, onSaved }: { user: AccessUser; tags: Tag[]; onSaved: (user: AccessUser) => void }) {
  const [mode, setMode] = useState<AccessMode>(user.access_mode);
  const [tagIds, setTagIds] = useState<number[]>(user.access_tags.map((tag) => tag.id));
  const [viewCreated, setViewCreated] = useState(user.view_created_tasks);
  const [viewWatched, setViewWatched] = useState(user.view_watched_tasks);
  const [canComplete, setCanComplete] = useState(user.can_complete_tasks);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');
  useEffect(() => { setMode(user.access_mode); setTagIds(user.access_tags.map((tag) => tag.id)); setViewCreated(user.view_created_tasks); setViewWatched(user.view_watched_tasks); setCanComplete(user.can_complete_tasks); }, [user]);
  const tagsEnabled = mode === 'TAGS' || mode === 'ASSIGNED_OR_TAGS';
  const toggleTag = (id: number) => setTagIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const save = async () => {
    setSaving(true); setStatus('');
    try {
      const updated = await api.updateAccess(user.id, mode, tagsEnabled ? tagIds : [], viewCreated, viewWatched, canComplete);
      onSaved(updated); setStatus('Сохранено');
    } catch (reason) { setStatus(message(reason)); }
    finally { setSaving(false); }
  };
  return <article className="access-card">
    <header>
      <span className="avatar avatar-large">{initials(user.display_name)}</span>
      <div><strong>{user.display_name}</strong><span>@{user.username}</span></div>
      {!user.is_active ? <span className="access-badge muted-badge">Отключён</span> : null}
      {user.is_admin ? <span className="access-badge admin-badge"><ShieldCheck size={13} />Rocket.Chat admin</span> : null}
    </header>
    {user.is_admin ? <div className="access-admin-note">Полный доступ, включая перевод задач в «Готово», назначается автоматически ролью администратора Rocket.Chat.</div> : <>
      <label className="field"><span>Видимость задач</span><select value={mode} onChange={(event) => { setMode(event.target.value as AccessMode); setStatus(''); }}>{modes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <p className="access-mode-description">{modes.find((item) => item.value === mode)?.description}</p>
      <div className="access-participation">
        <label><input type="checkbox" checked={viewCreated} disabled={saving || mode === 'NONE' || mode === 'ALL'} onChange={(event) => { setViewCreated(event.target.checked); setStatus(''); }} />Видеть созданные мной задачи</label>
        <label><input type="checkbox" checked={viewWatched} disabled={saving || mode === 'NONE' || mode === 'ALL'} onChange={(event) => { setViewWatched(event.target.checked); setStatus(''); }} />Видеть задачи, где я наблюдатель</label>
        <small>{mode === 'NONE' ? 'Нет доступа запрещает просмотр любых задач и уведомления.' : mode === 'ALL' ? 'Все задачи уже доступны.' : 'Дополняет выбранное правило. Права исполнителя не добавляются.'}</small>
      </div>
      <div className="access-participation access-completion">
        <label><input type="checkbox" checked={canComplete} disabled={saving || mode === 'NONE'} onChange={(event) => { setCanComplete(event.target.checked); setStatus(''); }} />Может переводить задачи в «Готово»</label>
        <small>Разрешает закрывать доступные задачи, в том числе назначенные другим. Без этого права кнопка «Завершить» отправляет задачу на проверку.</small>
      </div>
      {tagsEnabled ? <div className="access-tags"><span>Разрешённые теги</span><div>{tags.length ? tags.map((tag) => <button type="button" key={tag.id} aria-pressed={tagIds.includes(tag.id)} className={tagIds.includes(tag.id) ? 'selected' : ''} onClick={() => toggleTag(tag.id)}>{tag.name}</button>) : <small>Сначала создайте хотя бы один тег задачи</small>}</div></div> : null}
      <footer><span className={status === 'Сохранено' ? 'save-ok' : 'save-error'}>{status}</span><button type="button" className="button primary small" disabled={saving || (tagsEnabled && tagIds.length === 0)} onClick={() => void save()}><Save size={15} />{saving ? 'Сохраняем…' : 'Сохранить'}</button></footer>
    </>}
  </article>;
}

export function AccessPage({ tags, onUsersSynced }: { tags: Tag[]; onUsersSynced: (users: User[]) => void }) {
  const [users, setUsers] = useState<AccessUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setUsers(await api.accessUsers()); setError(''); }
    catch (reason) { setError(message(reason)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const sync = async () => {
    setSyncing(true); setError('');
    try {
      await api.syncUsers();
      const [accessUsers, allUsers] = await Promise.all([api.accessUsers(), api.users()]);
      setUsers(accessUsers); onUsersSynced(allUsers);
    } catch (reason) { setError(message(reason)); }
    finally { setSyncing(false); }
  };
  const saved = (updated: AccessUser) => setUsers((current) => current.map((user) => user.id === updated.id ? updated : user));
  return <div className="page access-page">
    <PageHeader title="Доступ к задачам" subtitle="Индивидуальные правила видимости для пользователей Rocket.Chat">
      <button type="button" className="button secondary" disabled={syncing} onClick={() => void sync()}><RefreshCw size={16} className={syncing ? 'spin' : ''} />{syncing ? 'Синхронизация…' : 'Обновить пользователей'}</button>
    </PageHeader>
    <div className="access-callout"><ShieldCheck size={19} /><div><strong>Запрещено по умолчанию</strong><p>Новые пользователи не видят задачи, пока вы не назначите им правило. Администраторы Rocket.Chat всегда имеют полный доступ.</p></div></div>
    {error ? <div className="inline-error">{error}</div> : null}
    {loading ? <div className="empty-state">Загрузка пользователей…</div> : <div className="access-grid">{users.map((user) => <AccessRow key={user.id} user={user} tags={tags} onSaved={saved} />)}</div>}
  </div>;
}
