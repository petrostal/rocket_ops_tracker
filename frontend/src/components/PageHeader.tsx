import { Plus } from 'lucide-react';
import type { ReactNode } from 'react';

export function PageHeader({ title, subtitle, onCreate, children }: { title: string; subtitle?: string; onCreate?: () => void; children?: ReactNode }) {
  return <><header className="page-header"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div><div className="header-actions">{children}{onCreate ? <button className="button primary" onClick={onCreate}><Plus size={19} />Задача</button> : null}</div></header></>;
}
