// Stable color per project based on name hash
const PROJECT_COLORS = [
  'bg-primary/20 text-primary',
  'bg-success/20 text-success',
  'bg-warning/20 text-warning',
  'bg-project-purple/20 text-project-purple',
  'bg-destructive/20 text-destructive',
  'bg-project-teal/20 text-project-teal',
  'bg-project-peach/20 text-project-peach',
  'bg-project-sky/20 text-project-sky',
];

function getProjectColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  return PROJECT_COLORS[Math.abs(hash) % PROJECT_COLORS.length];
}

function getInitials(name: string) {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

const SIZES = {
  sm: 'w-5 h-5 rounded text-[9px]',
  md: 'w-7 h-7 rounded-md text-[11px]',
  lg: 'w-8 h-8 rounded-md text-xs',
};

export function ProjectAvatar({ name, size = 'md', className = '' }: { name: string; size?: keyof typeof SIZES; className?: string; }) {
  return (
    <div className={`${SIZES[size]} flex items-center justify-center font-bold shrink-0 ${getProjectColor(name)} ${className}`}>
      {getInitials(name)}
    </div>
  );
}
