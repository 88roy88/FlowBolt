import { MockPackage, tag } from './package-base.js';

function getRealtimeMetrics() {
  const now = Date.now();
  const cycleSeconds = Math.floor(now / 10000) % 10;

  return {
    servers: [
      { id: 'srv-001', name: 'Web Server 1', cpu: 45 + (cycleSeconds * 5), memory: 62 + (cycleSeconds * 3), status: cycleSeconds < 8 ? 'healthy' : 'warning' },
      { id: 'srv-002', name: 'Web Server 2', cpu: 38 + (cycleSeconds * 4), memory: 58 + (cycleSeconds * 2), status: 'healthy' },
      { id: 'srv-003', name: 'Database Primary', cpu: 72 - (cycleSeconds * 2), memory: 85 + (cycleSeconds * 1), status: cycleSeconds > 7 ? 'warning' : 'healthy' },
      { id: 'srv-004', name: 'Cache Server', cpu: 25 + (cycleSeconds * 3), memory: 42 + (cycleSeconds * 4), status: 'healthy' },
    ],
    transactions: {
      total: 15000 + (cycleSeconds * 1250),
      success: 14700 + (cycleSeconds * 1200),
      failed: 300 + (cycleSeconds * 50),
      rate_per_second: 125 + (cycleSeconds * 15),
    },
    users: {
      active: 2340 + (cycleSeconds * 180),
      peak_today: 3500 + (cycleSeconds * 50),
      new_signups: 45 + (cycleSeconds * 5),
    },
    metrics: {
      response_time_ms: 145 + (cycleSeconds * 12),
      error_rate: 2.1 + (cycleSeconds * 0.3),
      throughput_mbps: 850 + (cycleSeconds * 50),
    },
    alerts: cycleSeconds > 6 ? [
      { id: 'alert-1', severity: 'warning', message: 'High CPU usage on srv-003', timestamp: new Date(now - 30000).toISOString() },
      { id: 'alert-2', severity: 'info', message: 'Scheduled maintenance in 2 hours', timestamp: new Date(now - 60000).toISOString() },
    ] : [
      { id: 'alert-2', severity: 'info', message: 'All systems operational', timestamp: new Date(now - 5000).toISOString() },
    ],
    timestamp: new Date(now).toISOString(),
  };
}

export default new MockPackage({
  id: 5,
  name: 'Real-Time Server Dashboard',
  tags: [tag('real-time'), tag('monitoring')],
  schema: {
    servers: ['id', 'name', 'cpu', 'memory', 'status'],
    transactions: ['total', 'success', 'failed', 'rate_per_second'],
    users: ['active', 'peak_today', 'new_signups'],
    metrics: ['response_time_ms', 'error_rate', 'throughput_mbps'],
    alerts: ['id', 'severity', 'message', 'timestamp'],
  },
  getResults() {
    return getRealtimeMetrics();
  },
});
