import { Button, type ButtonProps } from './button';

// A disabled button fires no mouse events, so the tooltip has to live on a wrapper.
export function ActionButton({ title, ...props }: ButtonProps & { title: string }) {
  return (
    <span className="inline-flex" title={title}>
      <Button variant="outline" size="sm" {...props} />
    </span>
  );
}
