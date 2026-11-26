import { cn } from '@/lib/utils';
import type { AppType } from '../../../types';

interface AppTypePickerProps {
  appTypes: AppType[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  disabled: boolean;
}

export function AppTypePicker({ appTypes, value, onChange, label, disabled }: AppTypePickerProps) {
  return (
    <fieldset disabled={disabled} className="space-y-1.5 disabled:opacity-50">
      <legend className="mb-1.5 text-sm font-medium text-foreground">
        {label} <span aria-hidden className="text-destructive">*</span>
      </legend>
      <div className="grid grid-cols-3 gap-2">
        {appTypes.map((appType) => {
          const selected = appType.id === value;
          const examples = appType.examples.join(', ');
          return (
            <label
              key={appType.id}
              title={examples || undefined}
              className={cn(
                'relative flex aspect-square min-w-0 flex-col items-center justify-center gap-1.5 overflow-hidden rounded-lg border p-2 text-center cursor-pointer transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
                selected
                  ? 'border-primary bg-primary/10 ring-1 ring-inset ring-primary'
                  : 'border-border/60 bg-muted/30 hover:bg-muted/60',
              )}
            >
              <input
                type="radio"
                name="app-type"
                value={appType.id}
                checked={selected}
                onChange={() => onChange(appType.id)}
                required
                className="sr-only"
              />
              {/* Trusted markup: from the operator's config file, never from users. */}
              <span
                aria-hidden
                className={cn('h-8 w-8 shrink-0 [&>svg]:h-full [&>svg]:w-full', selected ? 'text-primary' : 'text-muted-foreground')}
                dangerouslySetInnerHTML={{ __html: appType.icon }}
              />
              <span className="w-full truncate text-sm font-medium text-foreground">{appType.name}</span>
              {examples && (
                <span className="line-clamp-2 text-[11px] leading-tight text-muted-foreground">{examples}</span>
              )}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
