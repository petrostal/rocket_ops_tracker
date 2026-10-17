import { ChevronDown } from 'lucide-react';
import { useState, type ReactNode } from 'react';

export function WatcherSection({ count, children }: { count: number; children: ReactNode }) {
  const [hasOpened, setHasOpened] = useState(false);
  return <details className="watchers-section" onToggle={(event) => { if (event.currentTarget.open) setHasOpened(true); }}>
    <summary className="watchers-summary" aria-label={`Наблюдатели: ${count}`}>
      <span>Наблюдатели</span><span className="section-count">{count}</span><ChevronDown size={16} aria-hidden="true" />
    </summary>
    {hasOpened ? <div className="watchers-content">{children}</div> : null}
  </details>;
}
