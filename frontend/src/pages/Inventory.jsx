import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Database, Search, Download, Edit3, Trash2, Check, RotateCcw, Plus } from 'lucide-react';
import { api, display, errorMessage } from '../services/api';
import MetadataModal from '../components/common/MetadataModal';
import DeleteConfirmModal from '../components/common/DeleteConfirmModal';
import ErrorBanner from '../components/common/ErrorBanner';
import StatusBadge from '../components/common/StatusBadge';

const csvCell = (v) => {
  const s = v === null || v === undefined ? '' : Array.isArray(v) ? v.join('; ') : String(v);
  return `"${s.replace(/"/g, '""')}"`;
};

export default function Inventory() {
  const location = useLocation();
  const navigate = useNavigate();
  const [inventory, setInventory] = useState([]);
  const [checklist, setChecklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState(() => new URLSearchParams(location.search).get('q') ?? '');
  const [selectedClass, setSelectedClass] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');
  const [selectedSource, setSelectedSource] = useState('All');
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [inv, cl] = await Promise.all([api.getInventory(), api.getChecklist()]);
      setInventory(inv);
      setChecklist(cl);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load, location.key]);

  useEffect(() => {
    const q = new URLSearchParams(location.search).get('q');
    if (q !== null) setSearch(q);
  }, [location.search]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSave = async (patch) => {
    const saved = await api.updateInventory(selectedItem.id, patch);
    setInventory((prev) => prev.map((i) => (i.id === saved.id ? saved : i)));
    showToast(`Saved "${saved.field}" — status: ${saved.status}`);
  };

  const handleConfirmDelete = async (item) => {
    setIsDeleting(true);
    try {
      await api.deleteInventory(item.id);
      setInventory((prev) => prev.filter((i) => i.id !== item.id));
      setItemToDelete(null);
      showToast(`Non-PII field "${item.field}" deleted from inventory.`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Clear the whole inventory and scan history? Declared metadata in the registry is kept. This cannot be undone.')) return;
    try {
      await api.resetInventory(false);
      await load();
      showToast('Inventory cleared.');
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const sources = [...new Set(inventory.map((i) => i.source))].sort();
  const q = search.trim().toLowerCase();
  const filtered = inventory.filter((item) => {
    const hay = [item.field, item.source, item.purpose, item.retention, item.owner, item.rule_name]
      .filter(Boolean).join(' ').toLowerCase();
    return (!q || hay.includes(q))
      && (selectedClass === 'All' || item.class === selectedClass)
      && (selectedStatus === 'All' || item.status === selectedStatus)
      && (selectedSource === 'All' || item.source === selectedSource);
  });

  const exportCSV = () => {
    const headers = ['Source', 'Field', 'Data Class', 'Rule', 'Detection Method', 'Match Ratio', 'Confidence', 'Purpose', 'Retention', 'Owner', 'Missing Attributes', 'Status', 'Review Status', 'Metadata Link'];
    const rows = filtered.map((i) => [
      i.source, i.field, i.class, i.rule_name, i.detection_method, i.match_ratio, i.confidence,
      i.purpose, i.retention, i.owner, i.missing_attributes, i.status, i.review_status, i.metadata_link,
    ].map(csvCell).join(','));
    const blob = new Blob([[headers.map(csvCell).join(','), ...rows].join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `privista_evidence_inventory_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const selectCls = 'px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-blue-500';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 relative">
      {toastMessage && (
        <div role="status" className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-2.5 rounded-xl shadow-xl flex items-center gap-2.5 text-xs font-semibold border border-slate-700">
          <Check size={13} className="text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Evidence Inventory</h1>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              {filtered.length} of {inventory.length} fields
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-0.5">
            Every scanned field with its detection evidence and linked purpose / retention / owner metadata.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={handleReset} disabled={!inventory.length}
            className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 hover:bg-red-50 hover:border-red-200 text-slate-600 hover:text-red-700 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-40">
            <RotateCcw size={14} /> Reset
          </button>
          <button type="button" onClick={exportCSV} disabled={!filtered.length}
            className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-40">
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onRetry={load} />

      <div className="bg-white p-4 rounded-xl border border-slate-200 card-shadow flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} />
          <input
            type="search"
            aria-label="Search inventory"
            placeholder="Search fields, sources, purposes, owners..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
          />
        </div>
        <select aria-label="Filter by source" value={selectedSource} onChange={(e) => setSelectedSource(e.target.value)} className={selectCls}>
          <option value="All">All Sources</option>
          {sources.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select aria-label="Filter by data class" value={selectedClass} onChange={(e) => setSelectedClass(e.target.value)} className={selectCls}>
          <option value="All">All Data Classes</option>
          {['Name', 'Email ID', 'Phone Number', 'Financial Data', 'Government ID', 'Non-PII'].map((c) => <option key={c}>{c}</option>)}
        </select>
        <select aria-label="Filter by status" value={selectedStatus} onChange={(e) => setSelectedStatus(e.target.value)} className={selectCls}>
          <option value="All">All Statuses</option>
          <option value="Matched">Matched</option>
          <option value="Evidence Gap">Evidence Gap</option>
          <option value="Non-PII">Non-PII</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/80 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="px-5 py-3.5">Field</th>
                <th className="px-5 py-3.5">Classification</th>
                <th className="px-5 py-3.5">Detection Evidence</th>
                <th className="px-5 py-3.5">Purpose</th>
                <th className="px-5 py-3.5">Retention</th>
                <th className="px-5 py-3.5">Owner</th>
                <th className="px-5 py-3.5">Status</th>
                <th className="px-5 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && !inventory.length && (
                <tr><td colSpan={8} className="px-6 py-10 text-center text-slate-400">Loading inventory…</td></tr>
              )}
              {!loading && !inventory.length && !error && (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center">
                    <p className="text-sm font-semibold text-slate-700">No fields scanned yet</p>
                    <p className="text-xs text-slate-500 mt-1">Scan the bundled SQLite database or upload a CSV to build the inventory.</p>
                    <button type="button" onClick={() => navigate('/scan')} className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold cursor-pointer">
                      <Plus size={14} /> New Scan
                    </button>
                  </td>
                </tr>
              )}
              {filtered.map((item) => {
                const isNonPii = item.status === 'Non-PII';
                return (
                  <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5">
                      <span className="font-mono font-bold text-blue-700 bg-blue-50/80 px-2 py-0.5 rounded border border-blue-100">{item.field}</span>
                      <div className="flex items-center gap-1 mt-1 text-[11px] text-slate-500 font-mono">
                        <Database size={11} className="text-slate-400 shrink-0" />
                        <span className="truncate max-w-[180px]" title={item.source}>{item.source}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-slate-700 font-medium block">{item.class}</span>
                      {!isNonPii && (
                        <span className={`text-[10px] font-bold px-1.5 rounded inline-block mt-0.5 border ${
                          item.sensitivity === 'Critical' ? 'bg-red-50 text-red-700 border-red-200'
                            : item.sensitivity === 'High' ? 'bg-amber-50 text-amber-700 border-amber-200'
                              : 'bg-blue-50 text-blue-700 border-blue-200'}`}>
                          {item.sensitivity} tier
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-600">
                      {item.rule_name ? (
                        <>
                          <span className="block font-medium text-slate-700">{item.rule_name}</span>
                          <span className="text-[11px] text-slate-500">
                            {item.samples_scanned ? `${item.samples_matched}/${item.samples_scanned} values` : 'name only'} · {Math.round((item.confidence ?? 0) * 100)}% conf
                          </span>
                        </>
                      ) : <span className="text-slate-400">No rule matched</span>}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700 max-w-[180px]"><span className="truncate block" title={item.purpose ?? ''}>{display(item.purpose)}</span></td>
                    <td className="px-5 py-3.5 text-slate-600">{display(item.retention)}</td>
                    <td className="px-5 py-3.5 text-slate-600">{display(item.owner)}</td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={item.status} />
                      {item.missing_attributes?.length > 0 && (
                        <span className="block text-[10px] text-amber-700 mt-1">missing: {item.missing_attributes.join(', ')}</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button type="button" onClick={() => setSelectedItem(item)}
                          className="px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 rounded-md cursor-pointer inline-flex items-center gap-1">
                          <Edit3 size={13} />
                          {item.status === 'Matched' ? 'Review' : isNonPii ? 'View' : 'Fix Gap'}
                        </button>
                        {isNonPii && (
                          <button type="button" onClick={() => setItemToDelete(item)} aria-label={`Delete ${item.field}`}
                            className="px-2 py-1 text-xs font-semibold text-rose-600 hover:bg-rose-50 border border-rose-200/60 rounded-md cursor-pointer inline-flex items-center gap-1">
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <MetadataModal isOpen={!!selectedItem} onClose={() => setSelectedItem(null)} item={selectedItem} checklist={checklist} onSave={handleSave} />
      <DeleteConfirmModal isOpen={!!itemToDelete} item={itemToDelete} isDeleting={isDeleting} onClose={() => setItemToDelete(null)} onConfirm={handleConfirmDelete} />
    </div>
  );
}
