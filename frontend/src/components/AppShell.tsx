import { CheckSquare2, CirclePlus, Columns3, ListTodo, LogOut, ShieldCheck, UserRound } from 'lucide-react';
import type { ReactNode } from 'react';
import type { User } from '../types';
import { api } from '../api/client';
import { navigate } from '../hooks/useRoute';

interface Props {
  user: User;
  active: 'my' | 'all' | 'kanban' | 'access';
  embedded: boolean;
  onCreate: () => void;
  children: ReactNode;
}

const nav = [
  { key: 'my', label: 'Мои задачи', path: '/my', icon: UserRound },
  { key: 'all', label: 'Все задачи', path: '/tasks', icon: ListTodo },
  { key: 'kanban', label: 'Канбан', path: '/kanban', icon: Columns3 },
] as const;

export function AppShell({ user, active, embedded, onCreate, children }: Props) {
  return (
    <div className={`app-shell ${embedded ? 'is-embedded' : ''}`}>
      {!embedded && (
        <aside className="sidebar">
          <button className="brand" onClick={() => navigate('/kanban')} aria-label="OpsTracker: на канбан">
            <span className="brand-mark"><CheckSquare2 size={21} /></span>
            <span>OpsTracker</span>
          </button>
          <nav aria-label="Основная навигация">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <button key={item.key} className={`nav-item ${active === item.key ? 'active' : ''}`} onClick={() => navigate(item.path)}>
                  <Icon size={19} strokeWidth={1.8} />
                  <span>{item.label}</span>
                </button>
              );
            })}
            {user.is_admin ? <button className={`nav-item ${active === 'access' ? 'active' : ''}`} onClick={() => navigate('/access')}>
              <ShieldCheck size={19} strokeWidth={1.8} />
              <span>Доступ</span>
            </button> : null}
            <button className="nav-item create-nav" onClick={onCreate}>
              <CirclePlus size={20} strokeWidth={1.7} />
              <span>Создать задачу</span>
            </button>
          </nav>
          <div className="sidebar-user">
            <span className="avatar avatar-large">{initials(user.display_name)}</span>
            <div><strong>@{user.username}</strong><small>{user.is_admin ? 'Администратор' : 'Сотрудник'}</small></div>
            <button type="button" title="Выйти" onClick={() => { void api.logout().then(() => window.location.reload()); }}>
              <LogOut size={17} />
            </button>
          </div>
        </aside>
      )}
      <main className="main-content">{children}</main>
    </div>
  );
}

export function initials(value: string): string {
  return value.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]?.toUpperCase()).join('') || '?';
}
