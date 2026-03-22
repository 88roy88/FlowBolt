interface FlowLogoProps {
  size?: number;
  className?: string;
}

export function FlowLogo({ size = 20, className }: FlowLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
    >
      {/* Rounded play triangle pointing right */}
      <path d="M6.5 3.8C5.3 3.05 3.75 3.92 3.75 5.33v13.34c0 1.41 1.55 2.28 2.75 1.53l11.25-6.67c1.15-.72 1.15-2.34 0-3.06L6.5 3.8z" />
    </svg>
  );
}

interface FlowBrandProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function FlowBrand({ size = 'md', className }: FlowBrandProps) {
  const config = {
    sm: { icon: 16, text: 'text-[15px]', gap: 'gap-1' },
    md: { icon: 20, text: 'text-[18px]', gap: 'gap-1.5' },
    lg: { icon: 28, text: 'text-[28px]', gap: 'gap-2' },
  }[size];

  return (
    <div className={`flex items-center ${config.gap} ${className ?? ''}`}>
      <FlowLogo size={config.icon} className="text-[#2bbcc4]" />
      <span className={`font-bold tracking-tight ${config.text}`}>
        <span className="text-[#2bbcc4]">FLOW</span>
        <span className="text-foreground">44</span>
      </span>
    </div>
  );
}
