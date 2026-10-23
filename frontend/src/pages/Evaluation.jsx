import { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { api, errorMessage } from '../services/api';
import ErrorBanner from '../components/common/ErrorBanner';

function Kpi({ label, value, unit = '%', hint }) {
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 card-shadow">
      <span className="text-xs font-bold uppercase tracking-wider text-slate-400">{label}</span>
      <div className="flex items-baseline gap-1 mt-1">
        <span className="text-3xl font-extrabold text-slate-900">{value}</span>
        <span className="text-xs font-bold text-slate-500">{unit}</span>
      </div>
      <p className="text-xs text-slate-500 mt-1">{hint}</p>
    </div>
  );
}

function ConfusionCell({ label, value, hint, cls }) {
  return (
    <div className={`p-3.5 rounded-xl border ${cls}`}>
      <span className="text-[10px] font-bold uppercase tracking-wider block">{label}</span>
      <p className="text-xl font-extrabold mt-1">{value}</p>
      <span className="text-[10px] opacity-70">{hint}</span>
    </div>
  );
}

export default function Evaluation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      setData(await api.getEvaluation(refresh));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(false); }, [load]);

  const cm = data?.confusion_matrix;
  const cc = data?.class_confusion;
  const col = data?.column_level;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Detector Evaluation</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Per-class precision and recall of the current rule set on the labelled test datasets
            {data ? ` (${data.dataset}; ${data.column_level?.columns.length ?? 0} labelled columns, ${data.samples} sampled values; evaluated ${data.evaluated_at})` : ''}.
          </p>
          {data?.skipped?.length > 0 && (
            <p className="text-xs text-amber-700 mt-1">Skipped: {data.skipped.join('; ')}</p>
          )}
        </div>
        <button type="button" onClick={() => load(true)} disabled={loading}
          className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> {loading ? 'Evaluating…' : 'Re-run Evaluation'}
        </button>
      </div>

      <ErrorBanner message={error} onRetry={() => load(true)} />
      {!data && !error && <p className="text-sm text-slate-500">Running the detector on the labelled test datasets…</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="Precision (micro)" value={data.overall.precision} hint={`Macro: ${data.macro.precision}%`} />
            <Kpi label="Recall (micro)" value={data.overall.recall} hint={`Macro: ${data.macro.recall}%`} />
            <Kpi label="F1 (micro)" value={data.overall.f1_score} hint={`Macro: ${data.macro.f1}% · Accuracy ${data.overall.accuracy}%`} />
            <Kpi label="Latency" value={data.overall.latency_ms} unit="ms / value" hint="Measured during this evaluation run" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow lg:col-span-2">
              <h2 className="text-base font-bold text-slate-900">Per-Class Precision / Recall / F1</h2>
              <p className="text-xs text-slate-500 mb-4">Each sampled value is scored against its column's true class. Values in Non-PII columns are negatives: predicting a class for them is a false positive.</p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.categories} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                    <Bar dataKey="precision" name="Precision %" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="recall" name="Recall %" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="f1" name="F1 %" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto mt-4">
                <table className="w-full text-xs text-left">
                  <thead className="text-slate-500 uppercase tracking-wider border-b border-slate-200">
                    <tr>{['Class', 'Precision', 'Recall', 'F1', 'Support', 'TP', 'FP', 'FN'].map((h) => <th key={h} className="py-2 pr-3">{h}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.categories.map((c) => (
                      <tr key={c.name}>
                        <td className="py-2 pr-3 font-semibold text-slate-800">{c.name}</td>
                        <td className="py-2 pr-3">{c.precision}%</td>
                        <td className="py-2 pr-3">{c.recall}%</td>
                        <td className="py-2 pr-3">{c.f1}%</td>
                        <td className="py-2 pr-3">{c.support}</td>
                        <td className="py-2 pr-3">{c.tp}</td>
                        <td className="py-2 pr-3">{c.fp}</td>
                        <td className="py-2 pr-3">{c.fn}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
              <h2 className="text-base font-bold text-slate-900 mb-1">PII vs. Non-PII</h2>
              <p className="text-xs text-slate-500 mb-4">Each sample counted once.</p>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <ConfusionCell label="True Positive" value={cm.true_positive} hint="PII detected" cls="bg-blue-50 border-blue-200 text-blue-900" />
                <ConfusionCell label="False Positive" value={cm.false_positive} hint="Non-PII flagged" cls="bg-slate-50 border-slate-200 text-slate-800" />
                <ConfusionCell label="False Negative" value={cm.false_negative} hint="PII missed" cls="bg-slate-50 border-slate-200 text-slate-800" />
                <ConfusionCell label="True Negative" value={cm.true_negative} hint="Non-PII ignored" cls="bg-slate-100 border-slate-200 text-slate-800" />
              </div>
              <p className="mt-3 text-[11px] text-slate-500">{cm.wrong_class} PII sample(s) detected but assigned the wrong class.</p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow overflow-x-auto">
            <h2 className="text-base font-bold text-slate-900 mb-1">Class Confusion Matrix</h2>
            <p className="text-xs text-slate-500 mb-3">Rows = true label, columns = predicted label.</p>
            <table className="text-xs text-center border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-left text-slate-400 font-medium">true \ predicted</th>
                  {cc.labels.map((l) => <th key={l} className="p-2 font-semibold text-slate-600">{l}</th>)}
                </tr>
              </thead>
              <tbody>
                {cc.matrix.map((row, r) => (
                  <tr key={cc.labels[r]}>
                    <th className="p-2 text-left font-semibold text-slate-600">{cc.labels[r]}</th>
                    {row.map((v, c) => (
                      <td key={c} className={`p-2 w-24 border border-slate-100 font-mono ${v === 0 ? 'text-slate-300' : r === c ? 'bg-blue-50 text-blue-800 font-bold' : 'bg-red-50 text-red-700 font-bold'}`}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
              <h2 className="text-base font-bold text-slate-900 mb-1">Misclassified Samples</h2>
              <p className="text-xs text-slate-500 mb-3">Synthetic test values the detector got wrong, for rule tuning.</p>
              {data.subsets?.length > 0 && (
                <ul className="text-xs text-slate-600 mb-3 space-y-0.5">
                  {data.subsets.map((s) => (
                    <li key={s.dataset}>
                      <span className="font-mono">{s.dataset}</span>: {s.columns} columns ({s.column_accuracy}% correct), {s.samples} values, precision {s.micro.precision}%, recall {s.micro.recall}%
                    </li>
                  ))}
                </ul>
              )}
              {data.errors.length === 0 ? (
                <p className="text-xs text-emerald-700">No misclassified samples.</p>
              ) : (
                <>
                  {data.errors_total > data.errors.length && (
                    <p className="text-[11px] text-slate-500 mb-2">Showing {data.errors.length} of {data.errors_total} misclassified values.</p>
                  )}
                  <div className="max-h-96 overflow-y-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="text-slate-500 uppercase border-b border-slate-200 sticky top-0 bg-white">
                        <tr><th className="py-2 pr-3">Value</th><th className="py-2 pr-3">Dataset / Column</th><th className="py-2 pr-3">True</th><th className="py-2">Predicted</th></tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {data.errors.map((e, i) => (
                          <tr key={i}>
                            <td className="py-2 pr-3 font-mono">{e.value}</td>
                            <td className="py-2 pr-3 font-mono text-slate-500">{e.dataset}<br />{e.column}</td>
                            <td className="py-2 pr-3">{e.true}</td>
                            <td className="py-2 text-red-700 font-semibold">{e.predicted}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>

            {col && (
              <div className="bg-white p-6 rounded-xl border border-slate-200 card-shadow">
                <h2 className="text-base font-bold text-slate-900 mb-1">Column-Level Check</h2>
                <p className="text-xs text-slate-500 mb-3">{col.dataset} · {col.accuracy}% of columns classified correctly (same code path as the scanner).</p>
                <table className="w-full text-xs text-left">
                  <thead className="text-slate-500 uppercase border-b border-slate-200">
                    <tr><th className="py-2 pr-3">Column</th><th className="py-2 pr-3">True</th><th className="py-2 pr-3">Predicted</th><th className="py-2 pr-3">Matched</th><th className="py-2 pr-3">Values OK</th><th className="py-2" /></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {col.columns.map((c, i) => (
                      <tr key={`${c.dataset}::${c.column}`}>
                        <td className="py-2 pr-3 font-mono">
                          {(i === 0 || col.columns[i - 1].dataset !== c.dataset) && (
                            <span className="block text-[10px] text-slate-400 normal-case">{c.dataset}</span>
                          )}
                          {c.column}
                        </td>
                        <td className="py-2 pr-3">{c.true}</td>
                        <td className="py-2 pr-3">{c.predicted}</td>
                        <td className="py-2 pr-3">{c.match_ratio != null ? `${Math.round(c.match_ratio * 100)}%` : '—'}</td>
                        <td className="py-2 pr-3">{c.values_tested != null ? `${c.values_correct}/${c.values_tested}` : '—'}</td>
                        <td className="py-2">
                          {c.correct ? <CheckCircle2 size={14} className="text-emerald-600" aria-label="correct" /> : <XCircle size={14} className="text-red-600" aria-label="incorrect" />}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {col.categories && (
                  <>
                    <h3 className="text-sm font-bold text-slate-900 mt-5 mb-2">Per-Class (column level)</h3>
                    <table className="w-full text-xs text-left">
                      <thead className="text-slate-500 uppercase border-b border-slate-200">
                        <tr><th className="py-2 pr-3">Class</th><th className="py-2 pr-3">Precision</th><th className="py-2 pr-3">Recall</th><th className="py-2 pr-3">F1</th><th className="py-2">Columns</th></tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {col.categories.map((c) => (
                          <tr key={c.name}>
                            <td className="py-2 pr-3 font-semibold text-slate-800">{c.name}</td>
                            <td className="py-2 pr-3">{c.precision}%</td>
                            <td className="py-2 pr-3">{c.recall}%</td>
                            <td className="py-2 pr-3">{c.f1}%</td>
                            <td className="py-2">{c.support}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
