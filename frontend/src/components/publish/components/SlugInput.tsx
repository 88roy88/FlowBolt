import React from 'react';

interface SlugInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  disabled: boolean;
}

export function SlugInput({ value, onChange, placeholder, disabled }: SlugInputProps) {
  return (
    <div className="flex items-center gap-0 rounded-lg border border-border/60 bg-muted/30 overflow-hidden focus-within:ring-1 focus-within:ring-primary/40">
      <span className="px-3 py-2 text-sm text-muted-foreground border-r border-border/40 bg-muted/50 shrink-0 select-none">
        /shared/
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e)}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 px-3 py-2 text-sm bg-transparent outline-none placeholder:text-muted-foreground/50"
        autoFocus
      />
    </div>
  );
}
