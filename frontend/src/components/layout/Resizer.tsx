import { useState, useCallback, useEffect, useRef } from 'react';

const RESIZER_SIZE = 6;

type ResizerProps = {
  direction: 'horizontal' | 'vertical';
  onDrag: (delta: number) => void;
  style?: React.CSSProperties;
};

export function Resizer({ direction, onDrag, style }: ResizerProps) {
  const isVertical = direction === 'vertical';
  const [isDragging, setIsDragging] = useState(false);
  const startPosRef = useRef(0);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      startPosRef.current = isVertical ? e.clientY : e.clientX;
      setIsDragging(true);
    },
    [isVertical]
  );

  useEffect(() => {
    if (!isDragging) return;
    const handleMove = (e: MouseEvent) => {
      const current = isVertical ? e.clientY : e.clientX;
      const delta = current - startPosRef.current;
      startPosRef.current = current;
      onDrag(delta);
    };
    const handleUp = () => setIsDragging(false);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [isDragging, isVertical, onDrag]);

  return (
    <div
      role="separator"
      aria-orientation={direction}
      onMouseDown={handleMouseDown}
      style={{
        flexShrink: 0,
        width: isVertical ? '100%' : RESIZER_SIZE,
        height: isVertical ? RESIZER_SIZE : '100%',
        cursor: isVertical ? 'row-resize' : 'col-resize',
        background: isDragging ? 'var(--accent)' : 'var(--border)',
        opacity: isDragging ? 0.6 : 1,
        transition: isDragging ? 'none' : 'background 0.15s ease',
        ...(isVertical ? { minHeight: RESIZER_SIZE } : { minWidth: RESIZER_SIZE }),
        ...style,
      }}
    />
  );
}
