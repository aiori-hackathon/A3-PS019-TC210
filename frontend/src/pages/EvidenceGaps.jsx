import { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle, ShieldAlert, CheckCircle2, Database, PlusCircle, Info } from 'lucide-react';
import { api, display, errorMessage } from '../services/api';
import MetadataModal from '../components/common/MetadataModal';
import ErrorBanner from '../components/common/ErrorBanner';

const SEVERITY_STYLE = {
  Critical: 'bg-red-50 text-red-700 border-red-200',
  High: 'bg-amber-50 text-amber-700 border-amber-200',
  Medium: 'bg-blue-50 text-blue-700 border-blue-200',
};

export default function EvidenceGaps() {
  const location = useLocation();
  const [gaps, setGaps] = useState([]);
  const [inventory, setInventory] = useState({});
  const [checklist, setChecklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [severity, setSeverity] = useState('All');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [g, inv, cl] = await Promise.all([api.getEvidenceGaps(), api.getInventory(), api.getChecklist()]);
      setGaps(g);
      setInventory(Object.fromEntries(inv.map((i) => [i.id, i])));
      setChecklist(cl);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load, location.key]);

  const handleSave = async (patch) => {
    await api.resolveGap(selected.gapId, patch);
    await load();
  };

  const openGap = (gap) => {
    const item = inventory[gap.item_id] ?? gap;
    setSelected({ ...item, gapId: gap.id });
  };

  const count = (s) => gaps.filter((g) => g.severity === s).length;
  const shown = severity === 'All' ? gaps : gaps.filter((g) => g.severity === severity);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Missing-Metadata &amp; Evidence Gaps</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
              {gaps.length} open
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-0.5">
            Personal-data candidates that lack one or more required evidence-checklist attributes.
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onRetry={load} />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { s: 'Critical', icon: ShieldAlert, cls: 'bg-red-50 text-red-600', hint: 'Financial / Government ID' },
          { s: 'High', icon: AlertTriangle, cls: 'bg-amber-50 text-amber-600', hint: 'Purpose or retention missing' },
          { s: 'Medium', icon: Info, cls: 'bg-blue-50 text-blue-600', hint: 'Only optional attributes missing' },
        ].map(({ s, icon: Icon, cls, hint }) => (
          <button
            type="button"
            key={s}
            onClick={() => setSeverity(severity === s ? 'All' : s)}
            aria-pressed={severity === s}
            className={`bg-white p-4 rounded-xl border card-shadow flex items-center gap-3 text-left cursor-pointer ${severity === s ? 'border-blue-400 ring-1 ring-blue-400/30' : 'border-slate-200'}`}
          >
            <div className={`p-2.5 rounded-lg ${cls}`}><Icon size={20} /></div>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{s} gaps</span>
              <p className="text-xl font-extrabold text-slate-900">{count(s)}</p>
              <span className="text-[10px] text-slate-400">{hint}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {loading && !gaps.length && <p className="text-xs text-slate-400">Loading gaps…</p>}
        {!loading && !error && shown.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-3">
              <CheckCircle2 size={24} />
            </div>
            <h3 className="text-base font-bold text-slate-900">No open evidence gaps</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
              Every discovered personal-data candidate has the required checklist attributes declared (or no scan has run yet).
            </p>
          </div>
        )}
        {shown.map((gap) => (
          <div key={gap.id} className="bg-white rounded-xl border border-slate-200 card-shadow p-5 hover:border-blue-300 transition-all space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-mono font-bold text-sm text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded border border-slate-200">{gap.field}</span>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${SEVERITY_STYLE[gap.severity]}`}>{gap.severity}</span>
                  <span className="text-xs text-slate-500 font-medium">{gap.class}</span>
                  {gap.confidence != null && <span className="text-[11px] text-slate-400">detection confidence {Math.round(gap.confidence * 100)}%</span>}
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500 font-mono pt-1">
                  <Database size={13} className="text-slate-400" />
                  <span>{gap.source}</span>
                  <span className="text-slate-300">·</span>
                  <span className="uppercase">{gap.source_type}</span>
                </div>
              </div>
              <button type="button" onClick={() => openGap(gap)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer shrink-0">
                <PlusCircle size={15} /> Review &amp; Add Metadata
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-xs border-t border-slate-100">
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200/80">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Missing checklist attributes</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {gap.missingAttributes.map((attr) => (
                    <span key={attr} className="bg-white text-red-700 border border-red-200 px-2 py-0.5 rounded text-[11px] font-medium">✗ {attr}</span>
                  ))}
                </div>
              </div>
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200/80">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Currently declared</span>
                <p>Purpose: <strong>{display(gap.purpose)}</strong></p>
                <p>Retention: <strong>{display(gap.retention)}</strong></p>
                <p>Owner: <strong>{display(gap.owner)}</strong></p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200/80">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Suggested next step</span>
                <p className="text-slate-600 text-[11px]">{gap.recommendation}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <MetadataModal isOpen={!!selected} onClose={() => setSelected(null)} item={selected} checklist={checklist} onSave={handleSave} />
    </div>
  );
}
