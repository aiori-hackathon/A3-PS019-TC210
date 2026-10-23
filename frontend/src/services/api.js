
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, 
  headers: { 'Content-Type': 'application/json' },
});


export function errorMessage(err) {
  if (!err) return 'Unknown error';
  if (err.code === 'ERR_NETWORK') {
    return `Cannot reach the PriVista backend at ${API_BASE_URL}. Start it with "uvicorn app.main:app --port 8000" in /backend.`;
  }
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  return err.message ?? String(err);
}

const data = (p) => p.then((r) => r.data);

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}


export const display = (v, fallback = '—') => (v === null || v === undefined || v === '' ? fallback : v);

export const api = {
  // Config
  getChecklist:    () => data(client.get('/config/checklist')),
  getDataClasses:  () => data(client.get('/config/data-classes')),

  // Dashboard
  getSummary:      () => data(client.get('/dashboard/summary')),
  getCharts:       () => data(client.get('/dashboard/charts')),

  // Inventory & gaps
  getInventory:    () => data(client.get('/inventory/')),
  updateInventory: (id, patch) => data(client.patch(`/inventory/${id}`, patch)),
  deleteInventory: (id) => data(client.delete(`/inventory/${id}`)),
  resetInventory:  (includeDeclarations = false) =>
    data(client.post('/inventory/reset', null, { params: { confirm: true, include_declarations: includeDeclarations } })),
  getEvidenceGaps: () => data(client.get('/evidence-gaps/')),
  resolveGap:      (id, metadata) => data(client.post(`/evidence-gaps/${id}/resolve`, metadata)),

  // Rules
  getRules:        () => data(client.get('/rules/')),
  toggleRule:      (id) => data(client.post(`/rules/${id}/toggle`)),
  createRule:      (rule) => data(client.post('/rules/', rule)),
  deleteRule:      (id) => data(client.delete(`/rules/${id}`)),
  testRules:       (text, context) => data(client.post('/rules/test', { text, context: context || null })),

  // Evaluation
  getEvaluation:   (refresh = false) => data(client.get('/evaluation/', { params: { refresh } })),

  // Scanning
  testSqlConnection: (config) => data(client.post('/scan/test-connection', config)),
  uploadCsv: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return data(client.post('/scan/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }));
  },
  startScan:       (payload) => data(client.post('/scan/start', payload)),
  getScan:         (scanId) => data(client.get(`/scan/${scanId}`)),
  getScanResults:  (scanId) => data(client.get(`/scan/${scanId}/results`)),
  getScanHistory:  (limit = 20) => data(client.get('/scan/history', { params: { limit } })),

  // Reports
  getReports:      () => data(client.get('/reports/')),
  downloadReport: async (id, format = 'json') => {
    const res = await client.get(`/reports/${id}/download`, { params: { format }, responseType: 'blob' });
    let filename = `privista_${id}.${format}`;
    const disposition = res.headers?.['content-disposition'];
    const match = disposition?.match(/filename="?([^";]+)"?/);
    if (match?.[1]) filename = match[1];
    triggerDownload(res.data, filename);
  },
};

export { triggerDownload };
