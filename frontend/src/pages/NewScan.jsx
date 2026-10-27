import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorMessage } from '../services/api';
import {
  Database, Play, CheckCircle2, Loader2, ArrowRight, FileSpreadsheet, Upload, Link2, X, Eye, EyeOff, Info, Check, XCircle, HardDrive,
} from 'lucide-react';
import ErrorBanner from '../components/common/ErrorBanner';
import StatusBadge from '../components/common/StatusBadge';
import { NOT_PERSONAL } from '../constants';

const SOURCE_MODES = [
  { id: 'sql', title: 'Connect SQL Database', subtitle: 'PostgreSQL or MySQL', icon: Database },
  { id: 'sqlite', title: 'Upload SQLite Database', subtitle: '.db / .sqlite file, e.g. sample.db', icon: HardDrive },
  { id: 'csv', title: 'Upload CSV File', subtitle: 'Scan a structured .csv export', icon: FileSpreadsheet },
];

// File-upload source modes: accepted extensions and wording.
const FILE_MODES = {
  csv: { title: 'Upload CSV File', exts: ['.csv'], label: 'CSV file', icon: FileSpreadsheet, tip: <>Tip: try a file from <code>backend/data/synthetic/</code></>,
    help: 'Values are sampled per column; raw values are never stored, only masked examples.' },
  sqlite: { title: 'Upload SQLite Database', exts: ['.db', '.sqlite', '.sqlite3'], label: 'SQLite database', icon: HardDrive, tip: <>Tip: try <code>backend/data/sample.db</code></>,
    help: 'The file is opened read-only. Every table is scanned; raw values are never stored, only masked examples.' },
};

const DIALECT_DEFAULTS = {
  PostgreSQL: { port: '5432', dbName: '', schema: 'public' },
  MySQL: { port: '3306', dbName: '', schema: '' },
};

const inputCls = 'w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-800 placeholder-slate-400 bg-white';
const labelCls = 'block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1';

export default function NewScan() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const [sourceMode, setSourceMode] = useState('sql');
  const [csvFile, setCsvFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  const [sqlConfig, setSqlConfig] = useState({ dialect: 'PostgreSQL', host: '', username: '', password: '', ...DIALECT_DEFAULTS.PostgreSQL });
  const [showPassword, setShowPassword] = useState(false);
  const [isTestingConn, setIsTestingConn] = useState(false);
  const [conn, setConn] = useState(null); // { success, message, tables }

  const [checklistAttrs, setChecklistAttrs] = useState([]);
  const [checklist, setChecklist] = useState({});

  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [scanLogs, setScanLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getChecklist()
      .then((attrs) => {
        setChecklistAttrs(attrs);
        setChecklist(Object.fromEntries(attrs.map((a) => [a.key, !!a.required])));
      })
      .catch((err) => setError(errorMessage(err)));
    return () => clearInterval(pollRef.current);
  }, []);

  const fileMode = FILE_MODES[sourceMode];

  const pickFile = (file) => {
    if (!file || !fileMode) return;
    const lower = file.name.toLowerCase();
    if (!fileMode.exts.some((ext) => lower.endsWith(ext))) { setError(`Only ${fileMode.exts.join(', ')} files are accepted.`); return; }
    if (file.size > 50 * 1024 * 1024) { setError(`The ${fileMode.label} exceeds the 50 MB limit.`); return; }
    setError(null);
    setCsvFile(file);
  };

  const handleSqlChange = (key, value) => {
    setConn(null);
    setSqlConfig((prev) => (key === 'dialect' ? { ...prev, dialect: value, ...DIALECT_DEFAULTS[value] } : { ...prev, [key]: value }));
  };

  const isSqlite = sqlConfig.dialect === 'SQLite';
  const canTest = isSqlite ? !!sqlConfig.dbName.trim() : !!(sqlConfig.host.trim() && sqlConfig.dbName.trim());

  const handleTestConnection = async () => {
    setIsTestingConn(true);
    setConn(null);
    try {
      setConn(await api.testSqlConnection(sqlConfig));
    } catch (err) {
      setConn({ success: false, message: errorMessage(err), tables: [] });
    } finally {
      setIsTestingConn(false);
    }
  };

  const canLaunch = sourceMode === 'sql' ? !!conn?.success : !!csvFile;
  const finished = summary !== null;

  const handleStartScan = async () => {
    if (!canLaunch || isScanning) return;
    setIsScanning(true);
    setProgress(0);
    setSummary(null);
    setResults([]);
    setScanLogs([]);
    setError(null);
    try {
      let sourceRef;
      if (sourceMode === 'csv') {
        const upload = await api.uploadCsv(csvFile);
        sourceRef = upload.uploadId;
        setScanLogs([{ time: new Date().toLocaleTimeString(), text: `Uploaded ${upload.filename}: ${upload.rowCount} rows, ${upload.columns.length} columns` }]);
      } else if (sourceMode === 'sqlite') {
        const upload = await api.uploadSqlite(csvFile);
        sourceRef = upload.uploadId;
        setScanLogs([{ time: new Date().toLocaleTimeString(), text: `Uploaded ${upload.filename}: ${upload.tables.length} table(s): ${upload.tables.join(', ')}` }]);
      } else {
        sourceRef = sqlConfig;
      }
      const { scanId } = await api.startScan({ sourceType: sourceMode, sourceRef, checklist });

      pollRef.current = setInterval(async () => {
        try {
          const s = await api.getScan(scanId);
          setProgress(s.progress ?? 0);
          setScanLogs((prev) => (sourceMode !== 'sql' ? [prev[0], ...s.logs].filter(Boolean) : s.logs));
          if (s.status === 'completed' || s.status === 'failed') {
            clearInterval(pollRef.current);
            setIsScanning(false);
            if (s.status === 'completed') {
              setSummary(s.summary);
              setResults(await api.getScanResults(scanId));
            } else {
              setError(`Scan failed: ${s.error}`);
            }
          }
        } catch (pollErr) {
          clearInterval(pollRef.current);
          setIsScanning(false);
          setError(errorMessage(pollErr));
        }
      }, 800);
    } catch (err) {
      setIsScanning(false);
      setError(`Scan start failed: ${errorMessage(err)}`);
    }
  };

  const resetScan = () => {
    setSummary(null); setResults([]); setProgress(0); setScanLogs([]); setCsvFile(null); setConn(null); setError(null);
  };

  const piiResults = results.filter((r) => r.status !== NOT_PERSONAL);

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      <div className="pb-3 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Personal-Data Discovery Scanner</h1>
        <p className="text-slate-500 text-sm mt-0.5">Scan a SQL database, an uploaded SQLite file or a CSV file for candidate personal-data fields across the 5 data classes.</p>
      </div>

      <ErrorBanner message={error} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Step 1 */}
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
            <h2 className="text-base font-bold text-slate-900 mb-1">1. Select Data Source Type</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
              {SOURCE_MODES.map((mode) => {
                const Icon = mode.icon;
                const active = sourceMode === mode.id;
                return (
                  <button key={mode.id} type="button" aria-pressed={active} disabled={isScanning}
                    onClick={() => { if (mode.id !== sourceMode) setCsvFile(null); setSourceMode(mode.id); setConn(null); setError(null); }}
                    className={`p-4 rounded-xl border text-left flex items-start gap-3 transition-all cursor-pointer ${active ? 'border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/20' : 'border-slate-200 hover:border-slate-300 bg-white'}`}>
                    <div className={`p-2 rounded-lg mt-0.5 ${active ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500'}`}><Icon size={18} /></div>
                    <div>
                      <p className="text-sm font-bold text-slate-900">{mode.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{mode.subtitle}</p>
                    </div>
                    {active && <Check size={14} className="text-blue-600 ml-auto shrink-0 mt-1" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 2 */}
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
            {fileMode ? (
              <>
                <h2 className="text-base font-bold text-slate-900 mb-1">2. {fileMode.title}</h2>
                <p className="text-xs text-slate-500 mb-4">
                  Only {fileMode.exts.map((ext, i) => <span key={ext}>{i > 0 && ', '}<code className="bg-slate-100 px-1 rounded">{ext}</code></span>)} files, max 50 MB. {fileMode.help}
                </p>
                <div
                  role="button"
                  tabIndex={0}
                  aria-label={`Choose a ${fileMode.label}`}
                  onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !csvFile) fileInputRef.current?.click(); }}
                  onDrop={(e) => { e.preventDefault(); setIsDragging(false); pickFile(e.dataTransfer.files?.[0]); }}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onClick={() => !csvFile && fileInputRef.current?.click()}
                  className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed py-12 transition-all cursor-pointer ${isDragging ? 'border-blue-500 bg-blue-50' : csvFile ? 'border-emerald-400 bg-emerald-50/50 cursor-default' : 'border-slate-300 hover:border-blue-400 hover:bg-blue-50/30'}`}
                >
                  <input ref={fileInputRef} type="file" accept={fileMode.exts.join(',')} className="hidden" onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = ''; }} />
                  {csvFile ? (
                    <>
                      <fileMode.icon size={28} className="text-emerald-600" />
                      <div className="text-center">
                        <p className="text-sm font-bold text-slate-900">{csvFile.name}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{(csvFile.size / 1024).toFixed(1)} KB · Ready to scan</p>
                      </div>
                      <button type="button" disabled={isScanning} onClick={(e) => { e.stopPropagation(); setCsvFile(null); }}
                        className="flex items-center gap-1.5 text-xs text-red-600 font-semibold border border-red-200 bg-red-50 hover:bg-red-100 rounded-lg px-3 py-1.5 cursor-pointer">
                        <X size={12} /> Remove file
                      </button>
                    </>
                  ) : (
                    <>
                      <Upload size={28} className="text-blue-600" />
                      <p className="text-sm font-semibold text-slate-700">Drop your {fileMode.label} here, or <span className="text-blue-600 underline">browse</span></p>
                      <p className="text-xs text-slate-400">{fileMode.tip}</p>
                    </>
                  )}
                </div>
              </>
            ) : (
              <>
                <h2 className="text-base font-bold text-slate-900 mb-1">2. SQL Database Connection</h2>
                <p className="text-xs text-slate-500 mb-4">
                  {isSqlite ? 'SQLite file path, relative to the backend folder. The bundled demo database is data/sample.db.' : 'Credentials are used only for this scan and are not saved.'}
                </p>
                <div className="space-y-3">
                  <div>
                    <label htmlFor="sql-dialect" className={labelCls}>Database Type</label>
                    <select id="sql-dialect" value={sqlConfig.dialect} onChange={(e) => handleSqlChange('dialect', e.target.value)} className={inputCls}>
                      {Object.keys(DIALECT_DEFAULTS).map((d) => <option key={d}>{d}</option>)}
                    </select>
                  </div>
                  {!isSqlite && (
                    <div className="grid grid-cols-3 gap-3">
                      <div className="col-span-2">
                        <label htmlFor="sql-host" className={labelCls}>Host</label>
                        <input id="sql-host" type="text" placeholder="localhost" value={sqlConfig.host} onChange={(e) => handleSqlChange('host', e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label htmlFor="sql-port" className={labelCls}>Port</label>
                        <input id="sql-port" type="text" inputMode="numeric" value={sqlConfig.port} onChange={(e) => handleSqlChange('port', e.target.value)} className={inputCls} />
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div className={isSqlite ? 'col-span-2' : ''}>
                      <label htmlFor="sql-db" className={labelCls}>{isSqlite ? 'SQLite File' : 'Database Name'}</label>
                      <input id="sql-db" type="text" placeholder={isSqlite ? 'data/sample.db' : 'kyc_prod'} value={sqlConfig.dbName} onChange={(e) => handleSqlChange('dbName', e.target.value)} className={inputCls} />
                    </div>
                    {!isSqlite && (
                      <div>
                        <label htmlFor="sql-schema" className={labelCls}>Schema</label>
                        <input id="sql-schema" type="text" placeholder="public" value={sqlConfig.schema} onChange={(e) => handleSqlChange('schema', e.target.value)} className={inputCls} />
                      </div>
                    )}
                  </div>
                  {!isSqlite && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label htmlFor="sql-user" className={labelCls}>Username</label>
                        <input id="sql-user" type="text" autoComplete="username" value={sqlConfig.username} onChange={(e) => handleSqlChange('username', e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label htmlFor="sql-pass" className={labelCls}>Password</label>
                        <div className="relative">
                          <input id="sql-pass" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={sqlConfig.password} onChange={(e) => handleSqlChange('password', e.target.value)} className={`${inputCls} pr-9`} />
                          <button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((v) => !v)} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer">
                            {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-3 pt-1">
                    <button type="button" onClick={handleTestConnection} disabled={isTestingConn || !canTest || isScanning}
                      className="flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg border border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed">
                      {isTestingConn ? <Loader2 size={13} className="animate-spin" /> : <Link2 size={13} />}
                      {isTestingConn ? 'Testing…' : 'Test Connection'}
                    </button>
                    {conn?.success && (
                      <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
                        <CheckCircle2 size={13} /> {conn.message} · {conn.tables.length} table(s): {conn.tables.join(', ')}
                      </span>
                    )}
                    {conn && !conn.success && (
                      <span className="flex items-center gap-1.5 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-2.5 py-1 rounded-lg">
                        <XCircle size={13} /> {conn.message}
                      </span>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Step 3 */}
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
            <div className="flex items-start justify-between mb-1">
              <h2 className="text-base font-bold text-slate-900">3. Evidence Checklist</h2>
              <span className="flex items-center gap-1 text-[11px] text-blue-600 bg-blue-50 border border-blue-200 rounded-md px-2 py-0.5 font-medium">
                <Info size={11} /> config/evidence_checklist.yaml
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-3">Personal-data fields missing any selected attribute are flagged as evidence gaps.</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {checklistAttrs.map((attr) => (
                <label key={attr.key} className={`flex items-start gap-2 p-2.5 rounded-lg border text-xs cursor-pointer select-none ${checklist[attr.key] ? 'border-blue-300 bg-blue-50/50 text-blue-900' : 'border-slate-200 text-slate-600'}`}>
                  <input type="checkbox" checked={!!checklist[attr.key]} disabled={isScanning}
                    onChange={() => setChecklist((c) => ({ ...c, [attr.key]: !c[attr.key] }))} className="mt-0.5 accent-blue-600" />
                  <span>
                    <span className="font-semibold block">{attr.label}</span>
                    <span className="text-[11px] text-slate-500">{attr.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Console */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-slate-900">Execution Console</h2>
              {isScanning && <span className="flex items-center gap-1.5 text-xs text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-semibold border border-blue-200"><Loader2 size={13} className="animate-spin" /> Scanning</span>}
              {finished && <span className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-semibold border border-emerald-200"><CheckCircle2 size={13} /> Finished</span>}
            </div>
            <div className="mb-4">
              <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1.5"><span>Progress</span><span>{progress}%</span></div>
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-full bg-blue-600 transition-all duration-300 rounded-full" style={{ width: `${progress}%` }} />
              </div>
            </div>
            <div aria-live="polite" className="bg-slate-950 text-slate-300 rounded-xl p-3.5 font-mono text-[11px] h-64 overflow-y-auto space-y-1.5 border border-slate-800">
              <div className="text-slate-500">// PriVista discovery engine</div>
              {scanLogs.length === 0 ? (
                <div className="text-slate-500 italic">
                  {canLaunch ? 'Source ready. Click "Launch Scan".' : fileMode ? `Choose a ${fileMode.label} to enable scanning.` : 'Test the SQL connection to enable scanning.'}
                </div>
              ) : scanLogs.map((log, i) => (
                <div key={i} className="leading-relaxed"><span className="text-blue-400">[{log.time}]</span> {log.text}</div>
              ))}
            </div>

            <div className="mt-4 space-y-2">
              {!finished ? (
                <button type="button" disabled={isScanning || !canLaunch} onClick={handleStartScan}
                  className={`w-full py-2.5 px-4 rounded-lg font-bold text-sm flex items-center justify-center gap-2 cursor-pointer ${isScanning ? 'bg-blue-400 text-white cursor-not-allowed' : !canLaunch ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}>
                  {isScanning ? <><Loader2 size={16} className="animate-spin" /> Scanning… ({progress}%)</> : <><Play size={16} className="fill-white" /> Launch Scan</>}
                </button>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="p-2 rounded-lg bg-slate-50 border border-slate-200"><p className="text-lg font-extrabold text-slate-900">{summary.columns_scanned}</p>columns</div>
                    <div className="p-2 rounded-lg bg-blue-50 border border-blue-200"><p className="text-lg font-extrabold text-blue-800">{summary.pii_found}</p>PII candidates</div>
                    <div className="p-2 rounded-lg bg-amber-50 border border-amber-200"><p className="text-lg font-extrabold text-amber-800">{summary.gaps_found}</p>gaps</div>
                  </div>
                  <button type="button" onClick={() => navigate('/inventory')} className="w-full py-2.5 px-4 rounded-lg font-bold text-sm bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center gap-2 cursor-pointer">
                    Inspect Evidence Inventory <ArrowRight size={16} />
                  </button>
                  <button type="button" onClick={() => navigate('/gaps')} className="w-full py-2.5 px-4 rounded-lg font-bold text-sm bg-white border border-amber-300 hover:bg-amber-50 text-amber-700 flex items-center justify-center gap-2 cursor-pointer">
                    Review Evidence Gaps <ArrowRight size={16} />
                  </button>
                  <button type="button" onClick={resetScan} className="w-full py-2 px-4 rounded-lg font-semibold text-xs border border-slate-200 text-slate-700 hover:bg-slate-50 cursor-pointer">
                    Configure Another Scan
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {finished && (
        <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
          <div className="p-4 border-b border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Scan Results — {summary.source}</h2>
            <p className="text-xs text-slate-500">{piiResults.length} personal-data candidate(s); {results.length - piiResults.length} column(s) not flagged.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5">Source.Field</th><th className="px-4 py-2.5">Class</th><th className="px-4 py-2.5">Rule</th>
                  <th className="px-4 py-2.5">Matched</th><th className="px-4 py-2.5">Masked samples</th><th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2 font-mono">{r.source}.<strong>{r.field}</strong></td>
                    <td className="px-4 py-2">{r.class}</td>
                    <td className="px-4 py-2">{r.rule_name ?? '—'}</td>
                    <td className="px-4 py-2">{r.samples_scanned ? `${Math.round(r.match_ratio * 100)}% of ${r.samples_scanned}` : '—'}</td>
                    <td className="px-4 py-2 font-mono text-[11px] text-slate-500">{r.masked_examples?.join(', ') || '—'}</td>
                    <td className="px-4 py-2"><StatusBadge status={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
