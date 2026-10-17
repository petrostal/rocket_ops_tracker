import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { User } from '../types';

export function WatcherEditor({ value, users, onChange, disabled = false }: {
  value: number[]; users: User[]; onChange: (ids: number[]) => void; disabled?: boolean;
}) {
  const [candidates, setCandidates] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const candidateCache = useRef(new Map<number, User>());
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      void api.watcherCandidates(search).then((items) => {
        if (!cancelled) { items.forEach((user) => candidateCache.current.set(user.id, user)); setCandidates(items); setError(''); }
      }).catch((reason) => {
        if (!cancelled) setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить пользователей');
      }).finally(() => { if (!cancelled) setLoading(false); });
    }, search ? 200 : 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [search]);
  const known = new Map([...users, ...candidateCache.current.values()].map((user) => [user.id, user]));
  return <div className="watcher-editor">
    <div className="watcher-list">{value.map((id) => <span className="watcher-chip" key={id}>
      <span>{known.get(id)?.display_name || `Пользователь #${id}`} <small>{known.has(id) ? `@${known.get(id)!.username}` : ''}</small></span>
      <button type="button" disabled={disabled} aria-label={`Убрать наблюдателя ${known.get(id)?.username || id}`} onClick={() => onChange(value.filter((item) => item !== id))}><X size={14} /></button>
    </span>)}</div>
    <input type="search" aria-label="Поиск наблюдателя" placeholder="Найти пользователя…" value={search} disabled={disabled} onChange={(event) => setSearch(event.target.value)} />
    <select aria-label="Добавить наблюдателя" value="" disabled={disabled || loading || value.length >= 50} onChange={(event) => { if (event.target.value) { onChange([...value, Number(event.target.value)]); setSearch(''); } }}>
      <option value="">{loading ? 'Загрузка пользователей…' : 'Выберите наблюдателя'}</option>
      {candidates.filter((user) => !value.includes(user.id)).map((user) => <option key={user.id} value={user.id}>{user.display_name} — @{user.username}</option>)}
    </select>
    <small>Наблюдатели видят задачу и получают личные уведомления. Доступно до 50 участников.</small>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </div>;
}
