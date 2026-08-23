import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Task } from '../types';

export function usePaginatedTasks(params: URLSearchParams, pageSize: number, enabled = true) {
  const [items, setItems] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(enabled);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const itemCount = useRef(0);
  const requestVersion = useRef(0);
  const key = params.toString();

  useEffect(() => { itemCount.current = items.length; }, [items.length]);

  const requestPage = useCallback((offset: number, limit: number) => {
    const query = new URLSearchParams(key);
    query.set('offset', String(offset));
    query.set('limit', String(limit));
    return api.tasks(query);
  }, [key]);

  const refresh = useCallback(async (quiet = false) => {
    const version = ++requestVersion.current;
    setLoadingMore(false);
    if (!enabled) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError('');
      return;
    }
    if (!quiet) setLoading(true);
    try {
      const result = await requestPage(0, Math.max(itemCount.current, pageSize));
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
  }, [enabled, pageSize, requestPage]);

  const loadMore = useCallback(async () => {
    if (!enabled || loadingMore || itemCount.current >= total) return;
    const version = ++requestVersion.current;
    setLoadingMore(true);
    try {
      const result = await requestPage(itemCount.current, pageSize);
      if (version !== requestVersion.current) return;
      setItems((current) => {
        const existing = new Set(current.map((task) => task.id));
        return [...current, ...result.items.filter((task) => !existing.has(task.id))];
      });
      setTotal(result.total);
      setError('');
    } catch (reason) {
      if (version !== requestVersion.current) return;
      setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить задачи');
    } finally {
      if (version === requestVersion.current) setLoadingMore(false);
    }
  }, [enabled, loadingMore, pageSize, requestPage, total]);

  useEffect(() => {
    let cancelled = false;
    const version = ++requestVersion.current;
    setLoadingMore(false);
    if (!enabled) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError('');
      return;
    }
    setLoading(true);
    void requestPage(0, pageSize)
      .then((result) => {
        if (cancelled || version !== requestVersion.current) return;
        setItems(result.items);
        setTotal(result.total);
        setError('');
      })
      .catch((reason: unknown) => {
        if (!cancelled && version === requestVersion.current) setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить задачи');
      })
      .finally(() => {
        if (!cancelled && version === requestVersion.current) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [enabled, pageSize, requestPage]);
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh(true);
    }, 20_000);
    return () => window.clearInterval(timer);
  }, [enabled, refresh]);

  return { items, setItems, total, loading, loadingMore, error, refresh, loadMore };
}
