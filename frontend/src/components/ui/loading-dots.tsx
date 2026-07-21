import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const CYCLE_MS = 400;

// Animated "Loading" label whose trailing dots cycle . → .. → ... → (none).
// The dots live in a fixed-width span so surrounding layout doesn't shift as
// they animate.
export function LoadingDots({ className }: { className?: string }) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % 4), CYCLE_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <span className={className}>
      {t('common.loading', 'Loading')}
      <span aria-hidden className="inline-block w-[1.5ch] text-start align-baseline">
        {'.'.repeat(step)}
      </span>
    </span>
  );
}
