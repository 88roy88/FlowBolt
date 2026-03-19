import type { Meta, StoryObj } from '@storybook/react-vite';
import { CardWrapper } from './CardWrapper';
import { PlanOverviewCard } from './PlanOverviewCard';
import { TaskProgressCard } from './TaskProgressCard';
import { DesignCompleteCard } from './DesignCompleteCard';
import { CasesFetchedCard } from './CasesFetchedCard';
import { ProjectSummaryCard } from './ProjectSummaryCard';
import { ErrorFixRequestCard } from './ErrorFixRequestCard';
import { FixProgressCard } from './FixProgressCard';
import { DiffBlock } from './DiffBlock';

// CardWrapper
const cardMeta: Meta<typeof CardWrapper> = {
  title: 'Chat/Cards/CardWrapper',
  component: CardWrapper,
};
export default cardMeta;

export const Default: StoryObj = {
  render: () => <CardWrapper>Default card content</CardWrapper>,
};

export const WithAccents: StoryObj = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 500 }}>
      <CardWrapper accent="primary">Primary accent</CardWrapper>
      <CardWrapper accent="success">Success accent</CardWrapper>
      <CardWrapper accent="warning">Warning accent</CardWrapper>
      <CardWrapper accent="destructive">Destructive accent</CardWrapper>
    </div>
  ),
};

export const PlanAccepted: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <PlanOverviewCard
        overview={{
          summary: 'Build a dashboard app with user authentication, data visualization charts, and a settings page.',
          features: [
            { title: 'Authentication', description: 'Login/signup with email and password' },
            { title: 'Dashboard', description: 'Charts and KPI cards showing key metrics' },
            { title: 'Settings', description: 'User profile and app preferences' },
          ],
          decisions: [
            { id: '1', title: 'Styling', chosen: 'Tailwind CSS', alternatives: ['CSS Modules', 'Styled Components'] },
            { id: '2', title: 'Charts', chosen: 'Recharts', alternatives: ['Chart.js', 'D3'] },
          ],
        }}
        accepted={true}
      />
    </div>
  ),
};

export const PlanRejected: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <PlanOverviewCard
        overview={{ summary: 'A simple todo app.', features: [], decisions: [] }}
        accepted={false}
      />
    </div>
  ),
};

export const TaskProgressRunning: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <TaskProgressCard
        tasks={[
          { id: '1', title: 'Set up project structure', status: 'completed' },
          { id: '2', title: 'Create authentication flow', status: 'completed' },
          { id: '3', title: 'Build dashboard components', status: 'running' },
          { id: '4', title: 'Add settings page', status: 'pending' },
        ]}
      />
    </div>
  ),
};

export const TaskProgressComplete: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <TaskProgressCard
        tasks={[
          { id: '1', title: 'Set up project', status: 'completed' },
          { id: '2', title: 'Build UI', status: 'completed' },
          { id: '3', title: 'Deploy failed', status: 'failed' },
        ]}
      />
    </div>
  ),
};

export const DesignComplete_: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <DesignCompleteCard architecture={true} ux={true} />
    </div>
  ),
};

export const DesignPartial: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <DesignCompleteCard architecture={true} ux={false} />
    </div>
  ),
};

export const CasesFetched_: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <CasesFetchedCard
        cases={[
          { packageId: '4', packageName: 'People & Photos', dataSchema: 'Array of person records with id, name, phone, photo_url', relevantFields: 'name, phone, photo_url' },
          { packageId: '6', packageName: 'People Hebrew Names', dataSchema: 'Array with ID, Hebrew name, department', relevantFields: 'hebrew_name' },
        ]}
      />
    </div>
  ),
};

export const ProjectSummary_: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <ProjectSummaryCard
        summary={{
          summary: 'A people directory app that displays contacts with photos and Hebrew names.',
          tech_stack: ['React', 'TypeScript', 'Tailwind CSS', 'Recharts'],
          features: ['Search by name', 'Photo gallery view', 'Hebrew name display'],
          file_overview: {
            'src/App.tsx': 'Main application component',
            'src/components/PersonCard.tsx': 'Individual person card',
            'src/hooks/usePeopleSearch.ts': 'Search and data fetching hook',
          },
        }}
      />
    </div>
  ),
};

export const ErrorFixRequest_: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <ErrorFixRequestCard
        errorMessage="Cannot read properties of undefined (reading 'map')"
        errorFile="/src/components/PeopleGrid.tsx"
        errorLine={42}
        errorStack={`TypeError: Cannot read properties of undefined (reading 'map')\n    at PeopleGrid (PeopleGrid.tsx:42:18)\n    at renderWithHooks (react-dom.development.js:16305:18)`}
      />
    </div>
  ),
};

export const FixProgressRunning: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <FixProgressCard
        steps={[
          { id: '1', step: 'discover', status: 'completed', message: 'Found error in PeopleGrid.tsx' },
          { id: '2', step: 'generate', status: 'completed', message: 'Generated fix for undefined data' },
          { id: '3', step: 'write', status: 'running', message: 'Writing changes...' },
        ]}
        content="The error occurs because the data array is undefined before the API response arrives. Adding a null check."
        isLive
      />
    </div>
  ),
};

export const FixProgressDone: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <FixProgressCard
        steps={[
          { id: '1', step: 'discover', status: 'completed', message: 'Found error' },
          { id: '2', step: 'generate', status: 'completed', message: 'Generated fix' },
          { id: '3', step: 'write', status: 'completed', message: 'Applied changes' },
          { id: '4', step: 'validate', status: 'completed', message: 'Validated fix' },
        ]}
        content="Added null check for the people array before mapping."
      />
    </div>
  ),
};

export const DiffBlock_: StoryObj = {
  render: () => (
    <div style={{ maxWidth: 500 }}>
      <DiffBlock
        fileDiff={{
          path: 'src/components/PeopleGrid.tsx',
          diff: `@@ -40,7 +40,7 @@\n function PeopleGrid({ people }) {\n   return (\n     <div className="grid">\n-      {people.map((person) => (\n+      {(people ?? []).map((person) => (\n         <PersonCard key={person.id} person={person} />\n       ))}\n     </div>`,
        }}
      />
    </div>
  ),
};
