import { useEffect, useState } from 'react';

export function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function useRoute(): string {
  const [path, setPath] = useState(`${window.location.pathname}${window.location.search}`);
  useEffect(() => {
    const update = () => setPath(`${window.location.pathname}${window.location.search}`);
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);
  return path;
}
