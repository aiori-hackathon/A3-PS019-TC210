import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { api } from '../../services/api';
import { 
  LayoutDashboard, 
  Search, 
  Database, 
  AlertCircle, 
  ShieldCheck, 
  BarChart3, 
  FileText, 
  CheckCircle2
} from 'lucide-react';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'New Scan', path: '/scan', icon: Search },
  { name: 'Evidence Inventory', path: '/inventory', icon: Database },
  { name: 'Evidence Gaps', path: '/gaps', icon: AlertCircle, countKey: 'evidence_gaps' },
  { name: 'Detection Rules', path: '/rules', icon: ShieldCheck },
  { name: 'Evaluation', path: '/evaluation', icon: BarChart3 },
  { name: 'Audit Reports', path: '/reports', icon: FileText },
];

export default function Sidebar() {
  const location = useLocation();
  const [summary, setSummary] = useState(null);
  const [online, setOnline] = useState(null);

  useEffect(() => {
    api.getSummary()
      .then((s) => { setSummary(s); setOnline(true); })
      .catch(() => setOnline(false));
  }, [location.key]);

  return (
    <aside className="w-64 bg-[#0F172A] border-r border-slate-800 flex flex-col justify-between shrink-0 select-none text-slate-200">
      <div>
        {/* Brand Header */}
        <div className="h-16 px-6 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800/90 border border-slate-700/80 shadow-2xs flex items-center justify-center p-1 overflow-hidden shrink-0">
              <img src="/logo.png" alt="PriVista SparkX" className="w-full h-full object-contain" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-lg text-white tracking-tight">PriVista</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  Gov
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">Privacy & Data Shield</p>
            </div>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="p-3">
          <p className="px-3 pt-3 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Platform Modules
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) => `
                  group flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150
                  ${isActive 
                    ? 'bg-blue-600 text-white font-semibold shadow-sm shadow-blue-600/30' 
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
                  }
                `}
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-3">
                      <item.icon 
                        size={18} 
                        className={`transition-colors ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-blue-400'}`} 
                      />
                      <span>{item.name}</span>
                    </div>

                    {item.badge && (
                      <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded-full flex items-center gap-1 ${
                        isActive 
                          ? 'bg-red-700/80 text-red-100' 
                          : 'bg-red-500/20 text-red-300 border border-red-500/30'
                      }`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse"></span>
                        {item.badge}
                      </span>
                    )}

                    {item.countKey && summary?.[item.countKey] > 0 && (
                      <span className={`px-2 py-0.5 text-[11px] font-semibold rounded-full ${
                        isActive 
                          ? 'bg-red-700/80 text-white' 
                          : 'bg-red-500/20 text-red-300 border border-red-500/30'
                      }`}>
                        {summary[item.countKey]}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      {/* System Status and Workspace Info */}
      <div className="p-4 border-t border-slate-800/80 space-y-3">
        {/* Guard Status Box */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 shadow-2xs">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
              </span>
              <span className="text-xs font-semibold text-slate-200">Backend API</span>
            </div>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
              online ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/20'
                : online === false ? 'text-red-300 bg-red-500/15 border-red-500/30'
                  : 'text-slate-400 bg-slate-500/15 border-slate-500/20'}`}>
              {online ? 'Online' : online === false ? 'Offline' : '…'}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            {online === false
              ? 'Start the backend on port 8000.'
              : summary
                ? `${summary.total_sources} source(s) · ${summary.fields_scanned} fields scanned · ${summary.scans_run} scan(s)`
                : 'Connecting…'}
          </p>
        </div>

        {/* Workspace Identity */}
        <div className="flex items-center justify-between px-2 pt-1">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <CheckCircle2 size={14} className="text-blue-400" />
            <span>PS-019 Discovery</span>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">v2.0.0</span>
        </div>
      </div>
    </aside>
  );
}