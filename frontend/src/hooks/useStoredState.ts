import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';

const STORAGE_VERSION = 'v1';

export function useStoredState<T>(
  scope: string,
  fallback: T,
  validate: (value: unknown) => T | null,
): [T, Dispatch<SetStateAction<T>>] {
  const key = `opstracker:${scope}:${STORAGE_VERSION}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? validate(JSON.parse(raw)) ?? fallback : fallback;
    } catch {
      return fallback;
    }
  });
  const valueRef = useRef(value);

  const setStoredValue = useCallback<Dispatch<SetStateAction<T>>>((next) => {
    const resolved = typeof next === 'function'
      ? (next as (current: T) => T)(valueRef.current)
      : next;
    valueRef.current = resolved;
    try {
      window.localStorage.setItem(key, JSON.stringify(resolved));
    } catch {
      // Storage can be disabled or unavailable in private browsing.
    }
    setValue(resolved);
  }, [key]);

  useEffect(() => {
    valueRef.current = value;
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage can be disabled or unavailable in private browsing.
    }
  }, [key, value]);

  return [value, setStoredValue];
}
