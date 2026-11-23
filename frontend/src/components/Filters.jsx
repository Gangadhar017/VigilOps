import React from 'react';
import { Search, X } from 'lucide-react';

export function SearchInput({ value, onChange, placeholder = 'Search…', label = 'Search' }) {
  return (
    <div className="relative min-w-[12rem] flex-1 sm:max-w-xs">
      <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
      <input
        type="search"
        aria-label={label}
        className="input pl-9 pr-8"
        placeholder={placeholder}
        value={value}
        maxLength={120}
        onChange={(event) => onChange(event.target.value)}
      />
      {value ? (
        <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-content" onClick={() => onChange('')} aria-label="Clear search">
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}

export function SelectFilter({ label, value, onChange, options, allLabel = 'All' }) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="whitespace-nowrap">{label}</span>
      <select className="input w-auto py-1.5 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((option) => {
          const item = typeof option === 'string' ? { value: option, label: option.replace(/_/g, ' ') } : option;
          return (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          );
        })}
      </select>
    </label>
  );
}

export function FilterBar({ children }) {
  return <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">{children}</div>;
}
