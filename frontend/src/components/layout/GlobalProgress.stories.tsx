import type { Meta, StoryObj } from '@storybook/react-vite';

const meta: Meta = {
  title: 'Layout/GlobalProgress',
  parameters: { layout: 'fullscreen' },
};
export default meta;

function ProgressDemo({ percent, shimmer }: { percent: number; shimmer?: boolean }) {
  return (
    <div className="w-full bg-background">
      <div className="h-0.5 w-full overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ease-out ${shimmer ? 'progress-bar-shimmer' : 'bg-success'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="p-4 text-xs text-muted-foreground text-center">{percent}%</div>
    </div>
  );
}

export const Classifying: StoryObj = {
  render: () => <ProgressDemo percent={5} shimmer />,
};

export const Designing: StoryObj = {
  render: () => <ProgressDemo percent={15} shimmer />,
};

export const Planning: StoryObj = {
  render: () => <ProgressDemo percent={30} shimmer />,
};

export const Executing: StoryObj = {
  render: () => <ProgressDemo percent={65} shimmer />,
};

export const Complete: StoryObj = {
  render: () => <ProgressDemo percent={100} />,
};

export const AllStages: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-0 bg-background">
      {[5, 15, 30, 50, 65, 80, 100].map((p) => (
        <ProgressDemo key={p} percent={p} shimmer={p < 100} />
      ))}
    </div>
  ),
};
