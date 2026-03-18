/** Stub package run results for Flapi mock (server-spec §2.1). */
export const stubPackageResults = {
  sales_cube: [
    { region: 'North', amount: 100, product: 'Widget A' },
    { region: 'South', amount: 150, product: 'Widget B' },
    { region: 'East', amount: 80, product: 'Widget A' },
    { region: 'West', amount: 200, product: 'Widget C' },
  ],
  users_cube: [
    { id: 1, name: 'Alice', role: 'admin' },
    { id: 2, name: 'Bob', role: 'user' },
  ],
};

/** Intelligence-style stub for package 3: reports, entities, events, indicators. */
export const stubIntelligenceResults = {
  reports: [
    { id: 'RPT-001', title: 'Weekly Threat Assessment', classification: 'SECRET', date: '2025-03-10', summary: 'Rising activity in sector 7; three new entities linked to campaign Alpha.', source: 'OSINT' },
    { id: 'RPT-002', title: 'Entity Network Mapping', classification: 'CONFIDENTIAL', date: '2025-03-12', summary: 'Mapping of 12 entities and 8 events; cross-ref with financial indicators.', source: 'HUMINT' },
    { id: 'RPT-003', title: 'Indicator Bulletin', classification: 'RESTRICTED', date: '2025-03-14', summary: 'New IOCs associated with infrastructure; recommend blocking at perimeter.', source: 'SIGINT' },
    { id: 'RPT-004', title: 'Quarterly Strategic Summary', classification: 'CONFIDENTIAL', date: '2025-03-08', summary: 'Regional posture and key findings from HUMINT and SIGINT fusion.', source: 'FUSION' },
    { id: 'RPT-005', title: 'Infrastructure Deep Dive', classification: 'SECRET', date: '2025-03-11', summary: 'Technical analysis of Server Farm 7 and related C2 infrastructure.', source: 'SIGINT' },
    { id: 'RPT-006', title: 'Person-of-Interest Update', classification: 'RESTRICTED', date: '2025-03-13', summary: 'Movement and communications pattern for primary subject.', source: 'HUMINT' },
  ],
  entities: [
    { name: 'Alpha Corp', type: 'Organization', country: 'N/A', role: 'Suspected front', links: 4 },
    { name: 'John D.', type: 'Person', country: 'XX', role: 'Key contact', links: 2 },
    { name: 'Server Farm 7', type: 'Infrastructure', country: 'YY', role: 'Hosting', links: 12 },
    { name: 'Campaign Alpha', type: 'Campaign', country: 'N/A', role: 'Active op', links: 8 },
    { name: 'Delta Holdings', type: 'Organization', country: 'ZZ', role: 'Shell entity', links: 3 },
    { name: 'Jane M.', type: 'Person', country: 'XX', role: 'Finance', links: 5 },
    { name: 'Relay Node A', type: 'Infrastructure', country: 'YY', role: 'Proxy', links: 7 },
    { name: 'Operation Beta', type: 'Campaign', country: 'N/A', role: 'Dormant', links: 2 },
  ],
  events: [
    { date: '2025-03-01', location: 'Region A', type: 'Meeting', description: 'Stakeholder coordination' },
    { date: '2025-03-05', location: 'Online', type: 'Transfer', description: 'Funds moved to shell entity' },
    { date: '2025-03-09', location: 'Region B', type: 'Deployment', description: 'New infrastructure detected' },
    { date: '2025-03-12', location: 'N/A', type: 'Report', description: 'Assessment published internally' },
    { date: '2025-03-02', location: 'Capital', type: 'Meeting', description: 'Briefing to leadership' },
    { date: '2025-03-06', location: 'Online', type: 'Transfer', description: 'Secondary transfer to Delta' },
    { date: '2025-03-10', location: 'Region C', type: 'Deployment', description: 'Mirror site activation' },
    { date: '2025-03-14', location: 'N/A', type: 'Alert', description: 'IOC hit on perimeter' },
  ],
  indicators: [
    { ioc: '192.0.2.100', type: 'IPv4', confidence: 0.92 },
    { ioc: 'malware-sample.exe', type: 'FileHash', confidence: 0.88 },
    { ioc: 'phishing-domain.tld', type: 'Domain', confidence: 0.95 },
    { ioc: 'user@relay.com', type: 'Email', confidence: 0.75 },
    { ioc: '198.51.100.50', type: 'IPv4', confidence: 0.85 },
    { ioc: 'a1b2c3d4e5f6...', type: 'FileHash', confidence: 0.91 },
    { ioc: 'c2-server.tld', type: 'Domain', confidence: 0.89 },
    { ioc: 'alert@phish.tld', type: 'Email', confidence: 0.72 },
  ],
};

/** People & photos: package 4. Table: name, phone, last_seen_location; expand row to show image. */
export const stubPeopleWithPhotosResults = {
  people: [
    { id: 'p1', name: 'Alex Chen', phone: '+1-555-201-1001', last_seen_location: 'Building A, Floor 3', image_url: 'https://picsum.photos/seed/p1/400/400' },
    { id: 'p2', name: 'Sam Rivera', phone: '+1-555-201-1002', last_seen_location: 'Cafeteria', image_url: 'https://picsum.photos/seed/p2/400/400' },
    { id: 'p3', name: 'Jordan Lee', phone: '+1-555-201-1003', last_seen_location: 'Conference Room B', image_url: 'https://picsum.photos/seed/p3/400/400' },
    { id: 'p4', name: 'Casey Morgan', phone: '+1-555-201-1004', last_seen_location: 'Main Office', image_url: 'https://picsum.photos/seed/p4/400/400' },
    { id: 'p5', name: 'Riley Taylor', phone: '+1-555-201-1005', last_seen_location: 'Lab 2', image_url: 'https://picsum.photos/seed/p5/400/400' },
    { id: 'p6', name: 'Quinn Adams', phone: '+1-555-201-1006', last_seen_location: 'Parking Lot', image_url: 'https://picsum.photos/seed/p6/400/400' },
  ],
  photos: [
    { id: 'img1', photo_id: 'p1', url: 'https://picsum.photos/seed/p1/400/400', caption: 'Alex Chen' },
    { id: 'img2', photo_id: 'p2', url: 'https://picsum.photos/seed/p2/400/400', caption: 'Sam Rivera' },
    { id: 'img3', photo_id: 'p3', url: 'https://picsum.photos/seed/p3/400/400', caption: 'Jordan Lee' },
    { id: 'img4', photo_id: 'p4', url: 'https://picsum.photos/seed/p4/400/400', caption: 'Casey Morgan' },
    { id: 'img5', photo_id: 'p5', url: 'https://picsum.photos/seed/p5/400/400', caption: 'Riley Taylor' },
    { id: 'img6', photo_id: 'p6', url: 'https://picsum.photos/seed/p6/400/400', caption: 'Quinn Adams' },
  ],
};

/** Stub lib descriptors for GET /api/libs (server-spec §3.1). */
export const stubLibs = [
  { id: 'lodash', name: 'Lodash', type: 'js', files: { js: 'lodash.js' } },
  { id: 'chart-js', name: 'Chart.js', type: 'js', files: { js: 'chart-js.js' } },
  { id: 'bootstrap', name: 'Bootstrap', type: 'js-css', files: { js: 'bootstrap.js', css: 'bootstrap.css' } },
  { id: 'normalize', name: 'Normalize.css', type: 'css', files: { css: 'normalize.css' } },
  { id: 'font-awesome', name: 'Font Awesome', type: 'js-css', files: { js: 'font-awesome.js', css: 'font-awesome.css' } },
  { id: 'leaflet', name: 'Leaflet', type: 'js-css', files: { js: 'leaflet.js', css: 'leaflet.css' } },
  {
    id: 'sqlite3-wasm',
    name: 'SQLite3 WASM',
    type: 'js-css',
    files: { js: 'sqlite3-wasm.js', css: 'sqlite3-wasm.css', wasm: 'sqlite3-wasm.wasm' },
  },
  {
    id: 'pyodide',
    name: 'Pyodide',
    type: 'js-css',
    files: { js: 'pyodide.js', css: 'pyodide.css', wasm: 'pyodide.wasm' },
  },
  {
    id: 'monaco-editor',
    name: 'Monaco Editor',
    type: 'js-css',
    files: { js: 'monaco-editor.js', css: 'monaco-editor.css', wasm: 'monaco-editor.wasm' },
  },
];

/** In-memory store for runId → snippet (mock Redis). 12h TTL not enforced in mock. */
const runStore = new Map();

/**
 * @param {string} runId
 * @param {{ htmlSnippet: string, librariesUsed: string[] }} value
 */
export const putRun = (runId, value) => {
  runStore.set(runId, value);
};

/**
 * @param {string} runId
 * @returns {{ htmlSnippet: string, librariesUsed: string[] } | undefined}
 */
export const getRun = (runId) => runStore.get(runId);
