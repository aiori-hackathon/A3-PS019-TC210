import { AlertTriangle, CheckCircle2, MinusCircle } from 'lucide-react';

export default function StatusBadge({ status }) {
  if (status === 'Matched') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 size={12} /> Matched
      </span>
    );
  }
  if (status === 'Non-PII') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-50 text-slate-600 border border-slate-200">
        <MinusCircle size={12} /> Non-PII
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
      <AlertTriangle size={12} /> Evidence Gap
    </span>
  );
}
