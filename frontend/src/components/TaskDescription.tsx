import { ListChecks } from 'lucide-react';
import { useRef } from 'react';

const checklistLine = /^(\s*[-*+]\s+\[)([ xX])(\]\s+)(.*)$/;
const checklistPlaceholder = 'Пункт чек-листа';

interface DescriptionEditorProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  disabled?: boolean;
  placeholder?: string;
}

export function DescriptionEditor({ value, onChange, rows = 6, disabled = false, placeholder }: DescriptionEditorProps) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const insertChecklistItem = () => {
    const element = textarea.current;
    const start = element?.selectionStart ?? value.length;
    const end = element?.selectionEnd ?? start;
    const prefix = start > 0 && value[start - 1] !== '\n' ? '\n' : '';
    const suffix = end < value.length && value[end] !== '\n' ? '\n' : '';
    const item = `- [ ] ${checklistPlaceholder}`;
    const next = `${value.slice(0, start)}${prefix}${item}${suffix}${value.slice(end)}`;
    if (next.length > 20000) return;
    const selectionStart = start + prefix.length + item.indexOf(checklistPlaceholder);
    onChange(next);
    requestAnimationFrame(() => {
      textarea.current?.focus();
      textarea.current?.setSelectionRange(selectionStart, selectionStart + checklistPlaceholder.length);
    });
  };

  return <div className="description-editor">
    <div className="description-toolbar">
      <button type="button" className="description-tool" disabled={disabled} onClick={insertChecklistItem}><ListChecks size={15} />Чек-лист</button>
      <span>Пункты можно отмечать после сохранения</span>
    </div>
    <textarea ref={textarea} aria-label="Описание" maxLength={20000} rows={rows} disabled={disabled} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
  </div>;
}

interface TaskDescriptionProps {
  value: string;
  disabled?: boolean;
  onToggle?: (lineIndex: number, checked: boolean) => void;
}

export function TaskDescription({ value, disabled = false, onToggle }: TaskDescriptionProps) {
  if (!value) return <p className="muted">Описание не добавлено</p>;
  return <div className="task-description">{value.split('\n').map((line, index) => {
    const match = checklistLine.exec(line);
    if (!match) return <div className="description-line" key={index}>{line || '\u00a0'}</div>;
    const checked = match[2].toLowerCase() === 'x';
    return <label className={`checklist-item ${checked ? 'completed' : ''}`} key={index}>
      <input type="checkbox" checked={checked} disabled={disabled || !onToggle} onChange={(event) => onToggle?.(index, event.target.checked)} />
      <span>{match[4] || 'Без названия'}</span>
    </label>;
  })}</div>;
}

export function toggleChecklistItem(value: string, lineIndex: number, checked: boolean): string {
  return value.split('\n').map((line, index) => {
    if (index !== lineIndex) return line;
    const match = checklistLine.exec(line);
    return match ? `${match[1]}${checked ? 'x' : ' '}${match[3]}${match[4]}` : line;
  }).join('\n');
}
