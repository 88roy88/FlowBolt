// Shared person roster for packages 22 (name search) and 23 (person by name).
// Keeping both packages aligned against this list means every name returned by
// 22 resolves to a real profile in 23.

export interface PersonDetail {
  name: string;
  title: string;
  department: string;
  email: string;
  phone: string;
  location: string;
  bio: string;
  image_url: string;
}

function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function makePerson(partial: Omit<PersonDetail, 'email' | 'image_url'> & { email?: string; image_url?: string }): PersonDetail {
  const s = slug(partial.name);
  return {
    email: partial.email ?? `${s.replace(/-/g, '.')}@example.com`,
    image_url: partial.image_url ?? `https://picsum.photos/seed/${s}/512/512`,
    ...partial,
  };
}

export const people: PersonDetail[] = [
  makePerson({
    name: 'Alex Chen',
    title: 'Staff Engineer',
    department: 'Platform',
    phone: '+1-555-201-1001',
    location: 'Building A, Floor 3',
    bio: 'Leads the data-plane reliability team.',
  }),
  makePerson({
    name: 'Alexandra Reeve',
    title: 'Product Manager',
    department: 'Growth',
    phone: '+1-555-201-1010',
    location: 'NYC — Floor 12',
    bio: 'Runs activation experiments.',
  }),
  makePerson({
    name: 'Alice Thompson',
    title: 'QA Lead',
    department: 'Quality',
    phone: '+1-555-201-1011',
    location: 'Austin — Floor 2',
    bio: 'Owns release certification and flaky-test triage.',
  }),
  makePerson({
    name: 'Alistair Grey',
    title: 'Technical Writer',
    department: 'Docs',
    phone: '+44-20-555-0012',
    location: 'London — Shoreditch',
    bio: 'Publishes the API changelog weekly.',
  }),
  makePerson({
    name: 'Amir Patel',
    title: 'Data Engineer',
    department: 'Analytics',
    phone: '+1-555-201-1013',
    location: 'SF — Floor 7',
    bio: 'Maintains the warehouse transforms.',
  }),
  makePerson({
    name: 'Ben Carter',
    title: 'Backend Engineer',
    department: 'Backend',
    phone: '+1-555-201-1014',
    location: 'Building B, Floor 1',
    bio: 'Works on the billing service.',
  }),
  makePerson({
    name: 'Benjamin Ross',
    title: 'Principal Engineer',
    department: 'Architecture',
    phone: '+1-555-201-1015',
    location: 'Remote — Denver',
    bio: 'Sets technical direction for the platform org.',
  }),
  makePerson({
    name: 'Casey Morgan',
    title: 'Product Designer',
    department: 'Design',
    phone: '+1-555-201-1004',
    location: 'Main Office',
    bio: 'Focused on dashboard ergonomics and motion systems.',
  }),
  makePerson({
    name: 'Dana Kim',
    title: 'ML Engineer',
    department: 'Research',
    phone: '+1-555-201-1016',
    location: 'SF — Floor 9',
    bio: 'Trains the retrieval-ranking models.',
  }),
  makePerson({
    name: 'Daniel Foster',
    title: 'Support Lead',
    department: 'Customer Success',
    phone: '+1-555-201-1017',
    location: 'Austin — Floor 3',
    bio: 'Runs the escalation queue.',
  }),
  makePerson({
    name: 'Elena Vargas',
    title: 'Staff Designer',
    department: 'Design',
    phone: '+34-91-555-0018',
    location: 'Madrid',
    bio: 'Leads the design-system working group.',
  }),
  makePerson({
    name: 'Eli Brooks',
    title: 'DevOps Engineer',
    department: 'Infrastructure',
    phone: '+1-555-201-1019',
    location: 'Remote — Portland',
    bio: 'Owns the CI/CD pipeline.',
  }),
  makePerson({
    name: 'Farah Ahmad',
    title: 'Legal Counsel',
    department: 'Legal',
    phone: '+971-4-555-0020',
    location: 'Dubai',
    bio: 'Handles commercial contracts and DPAs.',
  }),
  makePerson({
    name: 'Gabriel Moreno',
    title: 'Sales Engineer',
    department: 'Sales',
    phone: '+55-11-555-0021',
    location: 'São Paulo',
    bio: 'Pre-sales for the LATAM region.',
  }),
  makePerson({
    name: 'Hannah Stern',
    title: 'Engineering Manager',
    department: 'Frontend',
    phone: '+1-555-201-1022',
    location: 'NYC — Floor 14',
    bio: 'Manages the app-shell team.',
  }),
  makePerson({
    name: 'Isla Novak',
    title: 'Researcher',
    department: 'Research',
    phone: '+420-2-555-0023',
    location: 'Prague',
    bio: 'Studies long-context retrieval.',
  }),
  makePerson({
    name: 'Jordan Lee',
    title: 'Engineering Manager',
    department: 'Backend',
    phone: '+1-555-201-1003',
    location: 'Conference Room B',
    bio: 'Manages the ingestion group; formerly an SRE.',
  }),
  makePerson({
    name: 'Julia Park',
    title: 'Finance Analyst',
    department: 'Finance',
    phone: '+82-2-555-0024',
    location: 'Seoul',
    bio: 'Owns ARR forecasting.',
  }),
  makePerson({
    name: 'Kai Nguyen',
    title: 'Mobile Engineer',
    department: 'Mobile',
    phone: '+1-555-201-1025',
    location: 'SF — Floor 5',
    bio: 'Ships the iOS app.',
  }),
  makePerson({
    name: 'Kira Delgado',
    title: 'Recruiter',
    department: 'People Ops',
    phone: '+1-555-201-1026',
    location: 'Austin — Floor 1',
    bio: 'Runs the engineering pipeline.',
  }),
  makePerson({
    name: 'Leo Marchetti',
    title: 'Solutions Architect',
    department: 'Sales',
    phone: '+39-02-555-0027',
    location: 'Milan',
    bio: 'Pre-sales for the EMEA region.',
  }),
  makePerson({
    name: 'Maya Okafor',
    title: 'Data Scientist',
    department: 'Analytics',
    phone: '+234-1-555-0028',
    location: 'Lagos',
    bio: 'Builds churn models.',
  }),
  makePerson({
    name: 'Noa T',
    title: 'Data Scientist',
    department: 'Analytics',
    phone: '+972-3-555-0022',
    location: 'Tel Aviv — Floor 2',
    bio: 'Builds forecasting models for the revenue team.',
  }),
  makePerson({
    name: 'Omar Haddad',
    title: 'Security Analyst',
    department: 'Security',
    phone: '+962-6-555-0029',
    location: 'Amman',
    bio: 'Runs the vulnerability-management program.',
  }),
  makePerson({
    name: 'Priya Shah',
    title: 'Content Strategist',
    department: 'Marketing',
    phone: '+91-22-555-0030',
    location: 'Mumbai',
    bio: 'Owns the product-marketing calendar.',
  }),
  makePerson({
    name: 'Quinn Adams',
    title: 'Security Engineer',
    department: 'Security',
    phone: '+1-555-201-1006',
    location: 'Parking Lot',
    bio: 'Runs the red-team program.',
  }),
  makePerson({
    name: 'Rivky Katz',
    title: 'Frontend Engineer',
    department: 'Web',
    phone: '+972-3-555-0033',
    location: 'Tel Aviv — Floor 4',
    bio: 'Owns the design-system component library.',
  }),
  makePerson({
    name: 'Roy Mezan',
    title: 'Software Engineer',
    department: 'AI Builder',
    phone: '+972-3-555-0044',
    location: 'Tel Aviv — Floor 5',
    bio: 'Works on the FLAPI integration layer and the planner agent.',
  }),
  makePerson({
    name: 'Sam Rivera',
    title: 'SRE',
    department: 'Platform',
    phone: '+1-555-201-1002',
    location: 'Cafeteria',
    bio: 'Runs production on-call rotations.',
  }),
  makePerson({
    name: 'Tova Bloom',
    title: 'Accountant',
    department: 'Finance',
    phone: '+972-3-555-0034',
    location: 'Tel Aviv — Floor 1',
    bio: 'Handles AP and reimbursements.',
  }),
];

export const peopleByName: Map<string, PersonDetail> = new Map(
  people.map((p) => [p.name.toLowerCase(), p]),
);
