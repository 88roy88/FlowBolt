import { useState, useCallback, useEffect, useRef } from 'react';

const HIT_SIZE = 5;

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

    // Block pointer events on iframes while dragging (they swallow mouse events)
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

  return (
    <div
      role="separator"
      aria-orientation={direction}
      onMouseDown={handleMouseDown}
      style={{
        flexShrink: 0,
        width: isVertical ? '100%' : HIT_SIZE,
        height: isVertical ? HIT_SIZE : '100%',
        cursor: isVertical ? 'row-resize' : 'col-resize',
        position: 'relative',
        zIndex: 2,
        // The visible 1px line is drawn via the pseudo-element-like border
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      {/* Visible 1px line */}
      <div
        style={{
          position: 'absolute',
          ...(isVertical
            ? { left: 0, right: 0, top: '50%', height: 1, transform: 'translateY(-50%)' }
            : { top: 0, bottom: 0, left: '50%', width: 1, transform: 'translateX(-50%)' }
          ),
          background: isDragging ? 'var(--primary)' : 'var(--border)',
          transition: isDragging ? 'none' : 'background 0.15s ease',
        }}
      />
    </div>
  );
}
