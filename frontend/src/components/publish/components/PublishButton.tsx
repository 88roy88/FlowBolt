import { ReactNode } from 'react';
import { Globe, Loader2 } from 'lucide-react';
import { BTN_PRIMARY } from '../styles';

interface PublishButtonProps {
  publishing: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  icon?: ReactNode;
}

export function PublishButton({ publishing, disabled, onClick, label, icon }: PublishButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={BTN_PRIMARY}
    >
      {publishing ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        icon || <Globe size={14} />
      )}
      {label}
    </button>
  );
}
