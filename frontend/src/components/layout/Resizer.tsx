import { useState, useCallback, useEffect, useRef } from 'react';

const HIT_SIZE = 7;

type ResizerProps = {
  direction: 'horizontal' | 'vertical';
  onDrag: (delta: number) => void;
  style?: React.CSSProperties;
};

export function Resizer({ direction, onDrag, style }: ResizerProps) {
  const isVertical = direction === 'vertical';
  const [isDragging, setIsDragging] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
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

    const iframes = document.querySelectorAll('iframe');
    iframes.forEach((f) => (f.style.pointerEvents = 'none'));

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
      iframes.forEach((f) => (f.style.pointerEvents = ''));
    };
  }, [isDragging, isVertical, onDrag]);

  const active = isDragging || isHovered;

  return (
    <div
      role="separator"
      aria-orientation={direction}
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        flexShrink: 0,
        width: isVertical ? '100%' : HIT_SIZE,
        height: isVertical ? HIT_SIZE : '100%',
        cursor: isVertical ? 'row-resize' : 'col-resize',
        position: 'relative',
        zIndex: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      <div
        style={{
          position: 'absolute',
          ...(isVertical
            ? { left: 0, right: 0, top: '50%', height: active ? 3 : 1, transform: 'translateY(-50%)' }
            : { top: 0, bottom: 0, left: '50%', width: active ? 3 : 1, transform: 'translateX(-50%)' }
          ),
          background: active ? 'var(--primary)' : 'var(--border)',
          boxShadow: active ? '0 0 6px color-mix(in srgb, var(--primary) 40%, transparent)' : 'none',
          transition: 'all 0.15s ease',
        }}
      />
    </div>
  );
}
