import { MockPackage, tag } from './package-base.js';

const data = {
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

export default new MockPackage({
  id: 3,
  name: 'Intelligence Briefing',
  tags: [tag('מודיעין')],
  data,
});
