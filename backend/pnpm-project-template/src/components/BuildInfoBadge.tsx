import { formatAuthUserLabel, getAuthUserDisplay } from '../auth/user';
import { APP_VERSION, BUILD_DATE, BUILD_ENVIRONMENT, getBuildInfo } from '../constants/buildInfo';

function formatBuildDate(iso: string): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const DETAIL_ROWS: { label: string; key: keyof ReturnType<typeof getBuildInfo> }[] = [
  { label: 'Environment', key: 'environment' },
  { label: 'Version', key: 'version' },
  { label: 'Built', key: 'buildDate' },
  { label: 'Project ID', key: 'projectId' },
  { label: 'Preview base', key: 'previewBase' },
  { label: 'Export base', key: 'exportBase' },
  { label: 'API base', key: 'apiBase' },
];

export function BuildInfoBadge() {
  const info = getBuildInfo();
  const user = getAuthUserDisplay();
  const userLabel = user ? formatAuthUserLabel(user) : undefined;

  return (
    <div className="fixed bottom-4 right-4 z-50 group">
      <div
        className="pointer-events-none absolute bottom-full right-0 mb-2 w-72 rounded-lg border border-slate-700/80 bg-slate-900/95 px-3 py-2.5 text-left opacity-0 shadow-xl shadow-black/40 backdrop-blur-sm transition-opacity duration-150 group-hover:opacity-100"
        role="tooltip"
      >
        <dl className="space-y-1.5 text-xs">
          {userLabel ? (
            <div className="grid grid-cols-[7rem_1fr] gap-2">
              <dt className="text-slate-500">User</dt>
              <dd className="break-all font-mono text-slate-200">{userLabel}</dd>
            </div>
          ) : null}
          {DETAIL_ROWS.map(({ label, key }) => {
            const raw = info[key];
            if (raw == null || raw === '') return null;
            const value = key === 'buildDate' ? formatBuildDate(String(raw)) : String(raw);
            return (
              <div key={key} className="grid grid-cols-[7rem_1fr] gap-2">
                <dt className="text-slate-500">{label}</dt>
                <dd className="break-all font-mono text-slate-200">{value}</dd>
              </div>
            );
          })}
        </dl>
      </div>

      <button
        type="button"
        className="rounded-full border border-slate-700/80 bg-slate-900/80 px-2.5 py-1 text-[11px] font-medium tracking-wide text-slate-400 shadow-sm backdrop-blur-sm transition-colors hover:border-violet-500/40 hover:text-slate-200"
        aria-label="Build information"
      >
        v{APP_VERSION}
        <span className="mx-1 text-slate-600">·</span>
        <span className={BUILD_ENVIRONMENT === 'prod' ? 'text-emerald-400/90' : 'text-amber-400/90'}>
          {BUILD_ENVIRONMENT}
        </span>
        {BUILD_DATE ? (
          <span className="sr-only">, built {formatBuildDate(BUILD_DATE)}</span>
        ) : null}
      </button>
    </div>
  );
}
