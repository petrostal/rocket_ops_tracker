import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { TaskSummary } from '../types';

export function useTasks(params: URLSearchParams, enabled = true) {
  const [items, setItems] = useState<TaskSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const requestVersion = useRef(0);
  const key = params.toString();

  const refresh = useCallback(async (quiet = false) => {
    const version = ++requestVersion.current;
    if (!enabled) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError('');
      return;
    }
    if (!quiet) setLoading(true);
    try {
      const result = await api.tasks(new URLSearchParams(key));
      if (version !== requestVersion.current) return;
      setItems(result.items);
      setTotal(result.total);
      setError('');
    } catch (reason) {
      if (version !== requestVersion.current) return;
      setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить задачи');
    } finally {
      if (!quiet && version === requestVersion.current) setLoading(false);
    }
  }, [enabled, key]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh(true);
    }, 20_000);
    return () => window.clearInterval(timer);
  }, [enabled, refresh]);

  return { items, setItems, total, loading, error, refresh };
}
