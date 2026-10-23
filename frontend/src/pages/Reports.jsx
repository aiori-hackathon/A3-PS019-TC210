import { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { FileText, Download, CheckCircle2, Calendar, Award, FileCode, Loader2, Scale } from 'lucide-react';
import { api, errorMessage } from '../services/api';
import ErrorBanner from '../components/common/ErrorBanner';

function DownloadButton({ id, format, busy, done, onClick, primary }) {
  const key = `${id}_${format}`;
  const Icon = format === 'pdf' ? Download : FileCode;
  return (
    <button type="button" onClick={() => onClick(id, format)} disabled={busy !== null}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
        primary ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'border border-slate-200 hover:bg-slate-50 text-slate-700'}`}>
      {done === key ? <CheckCircle2 size={14} /> : busy === key ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
      {format.toUpperCase()}
    </button>
  );
}

export default function Reports() {
  const location = useLocation();
  const [reports, setReports] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [done, setDone] = useState(null);

  const load = useCallback(async () => {
    try {
      setReports(await api.getReports());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);
  useEffect(() => { load(); }, [load, location.key]);

  const handleDownload = async (id, format) => {
    const key = `${id}_${format}`;
    setBusy(key);
    try {
      await api.downloadReport(id, format);
      setDone(key);
      setTimeout(() => setDone((p) => (p === key ? null : p)), 3000);
      load(); // scores may change once evaluation has been cached
    } catch (err) {
      setError(`Download failed: ${errorMessage(err)}`);
    } finally {
      setBusy(null);
    }
  };

  const manifest = reports.find((r) => r.id === 'evidence_manifest');
  const others = reports.filter((r) => r.id !== 'evidence_manifest');

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      <div className="pb-3 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Technical Evidence Reports</h1>
        <p className="text-slate-500 text-sm mt-0.5">Generated from the live inventory, gap register, rule configuration and evaluation results. PDF and JSON.</p>
      </div>

      <ErrorBanner message={error} onRetry={load} />

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 text-xs text-amber-900">
        <Scale size={18} className="text-amber-600 shrink-0" />
        <p>
          Reports contain <strong>technical evidence only</strong>: what was detected, how, and which metadata is declared or missing.
          They make no lawful-basis, compliance or data-flow determinations. Those remain with the human reviewer, who signs off in the PDF.
        </p>
      </div>

      {manifest && (
        <div className="bg-white rounded-2xl border border-slate-200 card-shadow p-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-600 text-white flex items-center justify-center shrink-0"><Award size={30} /></div>
            <div className="space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">Final Technical Report</span>
              <h2 className="text-lg font-bold text-slate-900">{manifest.title}</h2>
              <p className="text-xs text-slate-500 max-w-xl">{manifest.summary}</p>
              <p className="text-[11px] text-slate-400">{manifest.score}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <DownloadButton id={manifest.id} format="json" busy={busy} done={done} onClick={handleDownload} />
            <DownloadButton id={manifest.id} format="pdf" busy={busy} done={done} onClick={handleDownload} primary />
          </div>
        </div>
      )}

      <div className="space-y-4">
        {others.map((rep) => (
          <div key={rep.id} className="bg-white rounded-xl border border-slate-200 card-shadow p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-slate-100 text-slate-700 shrink-0"><FileText size={20} /></div>
              <div className="space-y-1">
                <h3 className="font-bold text-slate-900 text-sm">{rep.title}</h3>
                <p className="text-xs text-slate-500">{rep.summary}</p>
                <div className="flex items-center gap-3 text-[11px] text-slate-400 font-medium pt-1">
                  <span className="flex items-center gap-1"><Calendar size={12} /> Data as of {rep.generatedDate}</span>
                  <span>•</span>
                  <strong className="text-slate-700">{rep.score}</strong>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <DownloadButton id={rep.id} format="pdf" busy={busy} done={done} onClick={handleDownload} />
              <DownloadButton id={rep.id} format="json" busy={busy} done={done} onClick={handleDownload} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
