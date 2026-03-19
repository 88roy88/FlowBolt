import { useState, useCallback, useEffect, useRef } from 'react';

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
        width: isVertical ? '100%' : 1,
        height: isVertical ? 1 : '100%',
        cursor: isVertical ? 'row-resize' : 'col-resize',
        background: 'var(--border)',
        boxShadow: isDragging ? '0 0 0 1px var(--primary)' : 'none',
        transition: isDragging ? 'none' : 'box-shadow 0.15s ease',
        // Invisible hit area
        padding: isVertical ? '2px 0' : '0 2px',
        margin: isVertical ? '-2px 0' : '0 -2px',
        backgroundClip: 'content-box',
        position: 'relative',
        zIndex: 2,
        ...style,
      }}
    />
  );
}
