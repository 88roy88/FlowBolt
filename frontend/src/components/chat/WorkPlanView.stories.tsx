import type { Meta, StoryObj } from '@storybook/react-vite';
import { WorkPlanView } from './WorkPlanView';

// Mock the store so respondToPlan doesn't crash
import { useChatStore } from '../../stores/chat';

const meta: Meta<typeof WorkPlanView> = {
  title: 'Chat/WorkPlanView',
  component: WorkPlanView,
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 550, padding: 20 }}>
        <Story />
      </div>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof WorkPlanView>;

export const FullPlan: Story = {
  args: {
    overview: {
      summary: 'Build a people directory app that displays contacts with photos and Hebrew names, with search functionality and a responsive grid layout.',
      features: [
        { title: 'People Grid', description: 'Responsive card grid showing person photo, name, and department' },
        { title: 'Search', description: 'Real-time search filtering by name across both English and Hebrew' },
        { title: 'Profile Modal', description: 'Click a person card to see full details in a modal overlay' },
        { title: 'Photo Fallback', description: 'Show initials avatar when photo URL is missing or broken' },
      ],
      decisions: [
        { id: '1', title: 'Styling', chosen: 'Tailwind CSS', alternatives: ['CSS Modules', 'Styled Components'] },
        { id: '2', title: 'State Management', chosen: 'React hooks + context', alternatives: ['Zustand', 'Redux'] },
        { id: '3', title: 'Photo Handling', chosen: 'Lazy load with fallback', alternatives: ['Eager load', 'No photos'] },
      ],
    },
  },
};

export const MinimalPlan: Story = {
  args: {
    overview: {
      summary: 'Create a simple landing page with a hero section, features list, and contact form.',
      features: [
        { title: 'Hero Section', description: 'Full-width banner with headline and CTA button' },
      ],
      decisions: [],
    },
  },
};

export const PlanWithManyDecisions: Story = {
  args: {
    overview: {
      summary: 'Build an e-commerce dashboard with inventory management, order tracking, and analytics.',
      features: [
        { title: 'Inventory', description: 'CRUD operations for products with image upload' },
        { title: 'Orders', description: 'Order list with status filters and detail view' },
        { title: 'Analytics', description: 'Charts showing revenue, orders per day, and top products' },
      ],
      decisions: [
        { id: '1', title: 'Charts Library', chosen: 'Recharts', alternatives: ['Chart.js', 'Nivo', 'D3'] },
        { id: '2', title: 'Data Fetching', chosen: 'React Query', alternatives: ['SWR', 'Plain fetch'] },
        { id: '3', title: 'Form Handling', chosen: 'React Hook Form', alternatives: ['Formik', 'Native forms'] },
        { id: '4', title: 'Routing', chosen: 'React Router', alternatives: ['TanStack Router', 'Next.js'] },
        { id: '5', title: 'Database', chosen: 'Supabase', alternatives: ['Firebase', 'PlanetScale'] },
      ],
    },
  },
};
