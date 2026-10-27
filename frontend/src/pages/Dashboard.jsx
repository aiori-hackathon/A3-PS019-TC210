import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Database, Shield, ShieldCheck, CheckCircle2, AlertTriangle, ArrowRight, Search, Plus, Scale } from 'lucide-react';
import {
  PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar,
} from 'recharts';
import { api, display, errorMessage } from '../services/api';
import MetadataModal from '../components/common/MetadataModal';
import ErrorBanner from '../components/common/ErrorBanner';
import StatusBadge from '../components/common/StatusBadge';
import { NOT_PERSONAL } from '../constants';

const EMPTY_SUMMARY = {
  total_sources: 0, total_sources_sub: '—', pii_fields: 0, pii_change: 'No scans yet', metadata_matched: 0,
  metadata_percentage: '0%', evidence_gaps: 0, gap_percentage: '0%', evidence_coverage: '0%', coverage_sub: '—', last_scan_date: 'Never',
};

function Kpi({ label, value, sub, icon: Icon, iconCls, onClick, children }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick}
      className={`bg-white p-5 rounded-xl border border-slate-200 card-shadow card-hover text-left ${onClick ? 'cursor-pointer' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        <div className={`p-2 rounded-lg ${iconCls}`}><Icon size={18} /></div>
      </div>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      {sub && <p className="text-xs text-slate-500 mt-1 truncate" title={sub}>{sub}</p>}
      {children}
    </Tag>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [charts, setCharts] = useState({ pii_by_class: [], trend: [] });
  const [inventory, setInventory] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [checklist, setChecklist] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, c, inv, g, cl] = await Promise.all([
        api.getSummary(), api.getCharts(), api.getInventory(), api.getEvidenceGaps(), api.getChecklist(),
      ]);
      setSummary(s); setCharts(c); setInventory(inv); setGaps(g); setChecklist(cl);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => { load(); }, [load, location.key]);

  // Evaluation is cached on the backend; loaded separately so the dashboard renders immediately.
  useEffect(() => {
    api.getEvaluation().then(setEvaluation).catch((err) => setEvalError(errorMessage(err)));
  }, []);

  const handleSave = async (patch) => {
    if (selected.gapId) await api.resolveGap(selected.gapId, patch);
    else await api.updateInventory(selected.id, patch);
    await load();
  };

  const piiItems = inventory.filter((i) => i.status !== NOT_PERSONAL);
  const q = searchQuery.toLowerCase();
  const filteredInventory = piiItems.filter((i) => [i.field, i.class, i.source].join(' ').toLowerCase().includes(q));
  const totalPii = charts.pii_by_class.reduce((a, b) => a + b.value, 0);
  const hasData = inventory.length > 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Privacy Evidence Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">Personal-data discovery, metadata linkage and evidence coverage. Technical evidence only.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right hidden md:block">
            <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider block">Last Scan</span>
            <span className="text-xs font-semibold text-slate-700">{summary.last_scan_date}{summary.last_scan_source ? ` · ${summary.last_scan_source}` : ''}</span>
          </div>
          <button type="button" onClick={() => navigate('/scan')} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer">
            <Plus size={16} /> Start New Scan
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onRetry={load} />

      {!hasData && !error && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-blue-900">No scans yet</p>
            <p className="text-xs text-blue-800 mt-0.5">Connect a PostgreSQL or MySQL database or upload a CSV to populate the evidence inventory.</p>
          </div>
          <button type="button" onClick={() => navigate('/scan')} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold cursor-pointer">Run first scan</button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <Kpi label="Sources Scanned" value={summary.total_sources} sub={summary.total_sources_sub} icon={Database} iconCls="bg-blue-50 text-blue-600" />
        <Kpi label="PII Candidates" value={summary.pii_fields} sub={summary.pii_change} icon={Shield} iconCls="bg-blue-100 text-blue-700" />
        <Kpi label="Metadata Linked" value={summary.metadata_matched} icon={ShieldCheck} iconCls="bg-slate-100 text-slate-700">
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-blue-600 rounded-full" style={{ width: summary.metadata_percentage }} /></div>
            <span className="text-[11px] font-semibold text-slate-600">{summary.metadata_percentage}</span>
          </div>
        </Kpi>
        <Kpi label="Evidence Gaps" value={summary.evidence_gaps} sub={`${summary.gap_percentage} of PII candidates`} icon={AlertTriangle} iconCls="bg-amber-50 text-amber-600" onClick={() => navigate('/gaps')} />
        <Kpi label="Evidence Coverage" value={summary.evidence_coverage} sub={summary.coverage_sub} icon={CheckCircle2} iconCls="bg-emerald-50 text-emerald-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-bold text-slate-900">PII by Data Class</h2>
            <span className="text-xs text-slate-400 font-mono">{totalPii} total</span>
          </div>
          <p className="text-xs text-slate-500 mb-4">Candidate fields across the 5 predefined classes</p>
          {totalPii === 0 ? (
            <p className="h-56 flex items-center justify-center text-xs text-slate-400">No personal-data candidates yet</p>
          ) : (
            <div className="h-56 flex items-center">
              <ResponsiveContainer width="52%" height="100%">
                <PieChart>
                  <Pie data={charts.pii_by_class} innerRadius={55} outerRadius={75} paddingAngle={4} dataKey="value" stroke="#ffffff" strokeWidth={2}>
                    {charts.pii_by_class.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                  </Pie>
                  <Tooltip formatter={(value, name) => [`${value} fields`, name]} contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="w-[48%] pl-2 space-y-2">
                {charts.pii_by_class.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="w-2.5 h-2.5 rounded-xs shrink-0" style={{ backgroundColor: item.color }} />
                      <span className="text-slate-600 truncate">{item.name}</span>
                    </div>
                    <span className="font-semibold text-slate-800 ml-1">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow lg:col-span-2">
          <h2 className="text-base font-bold text-slate-900">Inventory Growth vs. Open Gaps (per scan)</h2>
          <p className="text-xs text-slate-500 mb-4">Inventory totals recorded after each completed scan</p>
          {charts.trend.length === 0 ? (
            <p className="h-56 flex items-center justify-center text-xs text-slate-400">Run a scan to start the trend</p>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={charts.trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} labelFormatter={(l, p) => `${l} · ${p?.[0]?.payload?.source ?? ''}`} />
                  <Line type="monotone" dataKey="value" name="PII candidates" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="gaps" name="Open gaps" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Personal-Data Inventory <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 ml-1">{piiItems.length}</span></h2>
            <p className="text-xs text-slate-500 mt-0.5">Candidate fields mapped to declared purpose and retention.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input type="search" aria-label="Filter inventory" placeholder="Filter by field, class, or source..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs w-60 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <button type="button" onClick={() => navigate('/inventory')} className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 cursor-pointer">
              View All <ArrowRight size={13} />
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/80 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Field</th><th className="px-6 py-3">Data Class</th><th className="px-6 py-3">Source</th>
                <th className="px-6 py-3">Declared Purpose</th><th className="px-6 py-3">Retention</th><th className="px-6 py-3">Status</th><th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredInventory.length === 0 && <tr><td colSpan={7} className="px-6 py-8 text-center text-slate-400">No personal-data candidates to show</td></tr>}
              {filteredInventory.slice(0, 6).map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/70">
                  <td className="px-6 py-3.5"><span className="font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-bold border border-blue-100">{row.field}</span></td>
                  <td className="px-6 py-3.5 text-slate-600 font-medium">{row.class}</td>
                  <td className="px-6 py-3.5 text-slate-500 font-mono text-[11px]">{row.source}</td>
                  <td className="px-6 py-3.5 text-slate-700 max-w-[220px] truncate" title={row.purpose ?? ''}>{display(row.purpose)}</td>
                  <td className="px-6 py-3.5 text-slate-600">{display(row.retention)}</td>
                  <td className="px-6 py-3.5"><StatusBadge status={row.status} /></td>
                  <td className="px-6 py-3.5 text-right">
                    <button type="button" onClick={() => setSelected(row)} className="px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 rounded-md cursor-pointer">
                      {row.status === 'Matched' ? 'Review' : 'Resolve Gap'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-bold text-slate-900">Highest-Severity Gaps <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 ml-1">{gaps.length}</span></h2>
            <button type="button" onClick={() => navigate('/gaps')} className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 cursor-pointer">Manage All <ArrowRight size={13} /></button>
          </div>
          <p className="text-xs text-slate-500 mb-4">Candidates missing required purpose / retention / owner metadata.</p>
          <div className="space-y-3">
            {gaps.length === 0 && <p className="text-xs text-slate-400">No open gaps.</p>}
            {gaps.slice(0, 3).map((gap) => (
              <div key={gap.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-900 text-xs">{gap.source}.{gap.field}</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${gap.severity === 'Critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{gap.severity}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{gap.gapReason}</p>
                </div>
                <button type="button" onClick={() => setSelected({ ...(inventory.find((i) => i.id === gap.item_id) ?? gap), gapId: gap.id })}
                  className="shrink-0 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer">
                  + Add Metadata
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2"><Scale size={16} className="text-blue-600" /> Detector Evaluation</h2>
            <button type="button" onClick={() => navigate('/evaluation')} className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 cursor-pointer">Details <ArrowRight size={13} /></button>
          </div>
          {evalError && <p className="text-xs text-red-600">{evalError}</p>}
          {!evaluation && !evalError && <p className="text-xs text-slate-400">Running evaluation on the labelled test set…</p>}
          {evaluation && (
            <>
              <p className="text-xs text-slate-500 mb-4">{evaluation.samples} manually labelled samples ({evaluation.dataset}).</p>
              <div className="grid grid-cols-3 gap-3 mb-4">
                {[['Precision', evaluation.overall.precision], ['Recall', evaluation.overall.recall], ['F1 Score', evaluation.overall.f1_score]].map(([l, v]) => (
                  <div key={l} className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 text-center">
                    <span className="text-[11px] font-semibold uppercase text-slate-400">{l}</span>
                    <p className="text-xl font-extrabold text-slate-900 mt-0.5">{v}%</p>
                  </div>
                ))}
              </div>
              <div className="h-28">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={evaluation.categories} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                    <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '11px' }} />
                    <Bar dataKey="precision" name="Precision %" fill="#2563eb" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="recall" name="Recall %" fill="#94a3b8" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>

      <MetadataModal isOpen={!!selected} onClose={() => setSelected(null)} item={selected} checklist={checklist} onSave={handleSave} />
    </div>
  );
}
