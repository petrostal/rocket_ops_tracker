import { useEffect, useState } from 'react';
import { api, ApiError } from './api/client';
import { AppShell } from './components/AppShell';
import { TaskDrawer } from './components/TaskDrawer';
import { TaskForm } from './components/TaskForm';
import { useRoute, navigate } from './hooks/useRoute';
import { AllTasksPage } from './pages/AllTasksPage';
import { KanbanPage } from './pages/KanbanPage';
import { MyTasksPage } from './pages/MyTasksPage';
import { AccessPage } from './pages/AccessPage';
import type { Tag, Task, TaskSummary, User } from './types';

function mergeTags(catalog: Tag[], incoming: Tag[]): Tag[] {
  const tags = new Map(catalog.map((tag) => [tag.id, tag]));
  incoming.forEach((tag) => tags.set(tag.id, tag));
  return [...tags.values()].sort((a, b) => a.name.localeCompare(b.name, 'ru'));
}

export function App() {
  const path = useRoute();
  const [routePath, routeSearch = ''] = path.split('?');
  const directMatch = routePath.match(/^\/tasks\/(\d+)$/);
  const queryTask = new URLSearchParams(routeSearch).get('task');
  const taskId = directMatch?.[1] ?? (queryTask && /^\d+$/.test(queryTask) ? queryTask : null);
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [authState, setAuthState] = useState<'loading' | 'ready' | 'unauthenticated' | 'error'>('loading');
  const [selected, setSelected] = useState<Task | null>(null);
  const [creating, setCreating] = useState(routePath === '/create');
  const embedded = new URLSearchParams(window.location.search).get('embedded') === '1' || window.self !== window.top;

  useEffect(() => {
    Promise.all([api.me(), api.users(), api.tags()]).then(([me, allUsers, allTags]) => { setUser(me); setUsers(allUsers); setTags(allTags); setAuthState('ready'); }).catch((error) => setAuthState(error instanceof ApiError && error.status === 401 ? 'unauthenticated' : 'error'));
  }, []);
  useEffect(() => {
    let cancelled = false;
    if (taskId && authState === 'ready') {
      void api.task(Number(taskId)).then((task) => {
        if (!cancelled) setSelected(task);
      }).catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          setSelected(null);
          setAuthState('unauthenticated');
          return;
        }
        const params = new URLSearchParams(routeSearch);
        params.delete('task');
        const fallback = /^\/tasks\/\d+$/.test(routePath) ? '/tasks' : routePath;
        navigate(`${fallback}${params.size ? `?${params}` : ''}`);
      });
    } else if (!taskId) {
      setSelected(null);
    }
    if (routePath === '/create') setCreating(true);
    return () => { cancelled = true; };
  }, [taskId, routePath, routeSearch, authState]);
  useEffect(() => {
    if (authState === 'ready' && user && routePath.startsWith('/access') && !user.is_admin) navigate('/kanban');
  }, [authState, routePath, user]);

  if (authState === 'loading') return <div className="auth-screen"><div className="brand-loader" /><p>Загружаем OpsTracker…</p></div>;
  if (authState === 'unauthenticated') return <div className="auth-screen"><div className="auth-panel"><div className="auth-mark">✓</div><h1>OpsTracker</h1><p>Войдите через рабочий аккаунт Rocket.Chat — отдельный пароль не нужен.</p><a className="button primary large" href={`/api/auth/login?next=${encodeURIComponent(`${path}${window.location.hash}`)}`}>Войти через Rocket.Chat</a></div></div>;
  if (authState === 'error' || !user) return <div className="auth-screen"><div className="auth-panel"><h1>Сервис временно недоступен</h1><p>Проверьте соединение и повторите попытку.</p><button className="button primary" onClick={() => window.location.reload()}>Повторить</button></div></div>;

  const active = routePath.startsWith('/access') ? 'access' : routePath.startsWith('/my') ? 'my' : routePath.startsWith('/tasks') ? 'all' : 'kanban';
  const open = (task: TaskSummary) => {
    if (Number(taskId) === task.id) return;
    const targetPath = /^\/tasks\/\d+$/.test(routePath) ? '/tasks' : routePath === '/create' ? '/kanban' : routePath;
    const params = new URLSearchParams(routeSearch);
    params.set('task', String(task.id));
    if (embedded) params.set('embedded', '1');
    navigate(`${targetPath}?${params}`);
  };
  const closeDrawer = () => {
    const targetPath = /^\/tasks\/\d+$/.test(routePath) ? '/tasks' : routePath;
    const params = new URLSearchParams(routeSearch);
    params.delete('task');
    setSelected(null);
    navigate(`${targetPath}${params.size ? `?${params}` : ''}`);
  };
  const syncTask = (task: Task) => {
    setSelected((current) => current?.id === task.id ? task : current);
    setTags((current) => mergeTags(current, task.tags));
  };
  const currentTask = selected?.id === Number(taskId) ? selected : null;
  const taskDetail = currentTask ? <TaskDrawer key={currentTask.id} task={currentTask} user={user} users={users} availableTags={tags} variant={active === 'all' ? 'panel' : 'drawer'} onClose={closeDrawer} onChanged={syncTask} onDeleted={() => setSelected(null)} /> : null;
  return <AppShell user={user} active={active} embedded={embedded} onCreate={() => setCreating(true)}>
    {active === 'access' && user.is_admin ? <AccessPage tags={tags} onUsersSynced={setUsers} /> : active === 'my' ? <MyTasksPage tags={tags} userId={user.id} onCreate={() => setCreating(true)} onOpen={open} /> : active === 'all' ? <AllTasksPage users={users} tags={tags} userId={user.id} selectedId={taskId ? Number(taskId) : null} selectedTask={currentTask} detail={taskDetail} onCloseTask={closeDrawer} onCreate={() => setCreating(true)} onOpen={open} /> : <KanbanPage users={users} tags={tags} userId={user.id} isAdmin={user.is_admin} onCreate={() => setCreating(true)} onOpen={open} />}
    {creating && <TaskForm users={users} tags={tags} onClose={() => { setCreating(false); if (routePath === '/create') navigate('/kanban'); }} onCreated={(task) => { setCreating(false); syncTask(task); open(task); }} />}
    {active !== 'all' ? taskDetail : null}
  </AppShell>;
}
