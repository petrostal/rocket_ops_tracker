import { ChevronDown, Plus, Tag as TagIcon, X } from 'lucide-react';
import { useId, useMemo, useState } from 'react';
import type { Tag } from '../types';

function cleanTag(value: string): string {
  return value.trim().replace(/^#+/, '').replace(/\s+/g, ' ');
}

export function TagList({ tags, empty = false }: { tags: Tag[]; empty?: boolean }) {
  if (!tags.length) return empty ? <span className="muted">Без тегов</span> : null;
  return <div className="tag-list">{tags.map((tag) => <span className="tag-chip" key={tag.id}><TagIcon size={11} />{tag.name}</span>)}</div>;
}

export function TagEditor({ value, suggestions, onChange, disabled = false }: { value: string[]; suggestions: Tag[]; onChange: (tags: string[]) => void; disabled?: boolean }) {
  const [input, setInput] = useState('');
  const [open, setOpen] = useState(false);
  const listId = useId();
  const selectedNames = useMemo(() => new Set(value.map((tag) => tag.toLocaleLowerCase('ru'))), [value]);
  const normalizedInput = cleanTag(input).toLocaleLowerCase('ru');
  const available = useMemo(() => suggestions.filter((tag) => {
    const normalized = tag.name.toLocaleLowerCase('ru');
    return !selectedNames.has(normalized) && (!normalizedInput || normalized.includes(normalizedInput));
  }), [normalizedInput, selectedNames, suggestions]);
  const canCreate = Boolean(normalizedInput)
    && !suggestions.some((tag) => tag.name.toLocaleLowerCase('ru') === normalizedInput)
    && !selectedNames.has(normalizedInput);
  const add = (raw: string) => {
    const next = [...value];
    const seen = new Set(value.map((tag) => tag.toLocaleLowerCase('ru')));
    for (const part of raw.split(',')) {
      const tag = cleanTag(part);
      const normalized = tag.toLocaleLowerCase('ru');
      if (tag && tag.length <= 64 && !seen.has(normalized) && next.length < 20) {
        seen.add(normalized);
        next.push(tag);
      }
    }
    onChange(next);
    setInput('');
    setOpen(true);
  };
  const remove = (index: number) => onChange(value.filter((_, itemIndex) => itemIndex !== index));
  return (
    <div
      className={`tag-editor ${disabled ? 'disabled' : ''}`}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <div className="tag-editor-values">
        {value.map((tag, index) => <span className="tag-chip editable" key={`${tag}-${index}`}>{tag}<button type="button" aria-label={`Удалить тег ${tag}`} onClick={() => remove(index)} disabled={disabled}><X size={12} /></button></span>)}
        <div className="tag-editor-input-wrap">
          <input
            value={input}
            role="combobox"
            aria-label="Теги"
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls={listId}
            maxLength={64}
            disabled={disabled || value.length >= 20}
            placeholder={value.length ? 'Ещё тег…' : 'Выберите или создайте тег'}
            onChange={(event) => { setInput(event.target.value); setOpen(true); }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); add(input); }
              if (event.key === 'Backspace' && !input && value.length) remove(value.length - 1);
              if (event.key === 'Escape') setOpen(false);
            }}
          />
          <button
            type="button"
            className="tag-editor-toggle"
            aria-label="Показать существующие теги"
            aria-expanded={open}
            disabled={disabled || value.length >= 20}
            onClick={() => setOpen(true)}
          ><ChevronDown size={16} /></button>
        </div>
      </div>
      {open && !disabled && value.length < 20 ? <div className="tag-editor-menu" id={listId} role="listbox" aria-label="Существующие теги">
        {available.length > 0 ? <div className="tag-editor-menu-label">Существующие теги</div> : null}
        {available.map((tag) => <button type="button" role="option" aria-selected="false" key={tag.id} onClick={() => add(tag.name)}><TagIcon size={14} /><span>{tag.name}</span></button>)}
        {canCreate ? <button type="button" role="option" aria-selected="false" className="tag-editor-create" onClick={() => add(input)}><Plus size={15} /><span>Создать тег <strong>«{cleanTag(input)}»</strong></span></button> : null}
        {available.length === 0 && !canCreate ? <div className="tag-editor-empty">{suggestions.length ? 'Подходящих тегов нет' : 'Тегов пока нет — введите название нового'}</div> : null}
      </div> : null}
      <small>Выберите существующий тег или введите новый и нажмите Enter · максимум 20</small>
    </div>
  );
}

export function TagFilter({ tags, selected, onChange }: { tags: Tag[]; selected: string[]; onChange: (tags: string[]) => void }) {
  if (!tags.length) return null;
  const toggle = (tag: string) => onChange(selected.includes(tag) ? selected.filter((item) => item !== tag) : [...selected, tag]);
  return (
    <div className="tag-filter" aria-label="Фильтр по тегам">
      <span><TagIcon size={15} />Теги</span>
      <div>{tags.map((tag) => <button type="button" key={tag.id} aria-pressed={selected.includes(tag.name)} className={selected.includes(tag.name) ? 'selected' : ''} onClick={() => toggle(tag.name)}>{tag.name}</button>)}</div>
      {selected.length > 0 ? <button type="button" className="tag-filter-clear" onClick={() => onChange([])}><X size={13} />Очистить</button> : null}
    </div>
  );
}
