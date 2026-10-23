import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Search, Plus } from 'lucide-react';
import { api } from '../../services/api';

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

export default function Topbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api.getScanHistory(5).then(setHistory).catch(() => setHistory([]));
  }, [location.key]);

  const submitSearch = (e) => {
    e.preventDefault();
    navigate(`/inventory?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    <header className="h-16 bg-[#0F172A] border-b border-slate-800 px-6 flex items-center justify-between shrink-0 relative z-20 text-slate-200">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-semibold text-slate-100">PS-019 Evidence Workspace</span>
        <span className="text-slate-600">/</span>
        <span className="text-amber-300 bg-amber-950/60 px-2 py-0.5 rounded-md font-medium text-xs border border-amber-800/80">
          Synthetic data · Technical evidence only
        </span>
      </div>

      <div className="flex items-center gap-4">
        <form onSubmit={submitSearch} role="search" className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="search"
            aria-label="Search inventory"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search inventory (e.g. aadhaar, pan)…"
            className="pl-9 pr-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-lg text-sm w-72 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
          />
        </form>

        <button type="button" onClick={() => navigate('/scan')}
          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-2 rounded-lg text-sm font-semibold cursor-pointer">
          <Plus size={16} /> Start Scan
        </button>

        <div className="relative">
          <button type="button" onClick={() => setShowNotifications((v) => !v)} aria-label="Recent scans" aria-expanded={showNotifications}
            className="relative p-2 text-slate-400 hover:text-white hover:bg-slate-800/80 rounded-lg cursor-pointer">
            <Bell size={18} />
            {history.length > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-blue-500 ring-2 ring-slate-900" />}
          </button>
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-slate-900 rounded-xl shadow-2xl border border-slate-800 p-3 z-50">
              <div className="pb-2 mb-2 border-b border-slate-800 text-xs font-bold text-slate-200 uppercase tracking-wider">Recent scans</div>
              {history.length === 0 && <p className="text-xs text-slate-400 p-2">No scans yet.</p>}
              <div className="space-y-2">
                {history.map((h) => (
                  <div key={h.scan_id} className="p-2.5 rounded-lg text-xs bg-slate-800/40 border border-slate-800">
                    <p className="font-semibold text-slate-100">
                      {h.status === 'completed' ? '✓' : '✗'} {h.source} <span className="text-slate-500 uppercase">({h.source_type})</span>
                    </p>
                    <p className="text-slate-400 text-[11px]">
                      {h.status === 'completed'
                        ? `${h.columns_scanned} columns · ${h.pii_found} PII candidates · ${h.gaps_found} gaps`
                        : `Failed: ${h.error}`}
                    </p>
                    <span className="text-[10px] text-slate-500">{timeAgo(h.finished_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
