import { useState } from 'react';
import { X, ShieldCheck, Check, AlertCircle, Ban, BadgeCheck, Undo2 } from 'lucide-react';
import { errorMessage } from '../../services/api';
import { NOT_PERSONAL } from '../../constants';

const DEFAULT_ATTRS = [
  { key: 'purpose', label: 'Declared Purpose' },
  { key: 'retention', label: 'Retention Schedule' },
  { key: 'owner', label: 'Data Owner' },
];

const PLACEHOLDERS = {
  purpose: 'e.g. Identity Verification (KYC), Billing Settlement',
  retention: 'e.g. 7 Years after account closure',
  owner: 'e.g. Compliance & Risk',
};

function EvidenceRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-slate-100 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800 text-right">{value}</span>
    </div>
  );
}

function ModalForm({ item, checklist, onClose, onSave }) {
  const attrs = checklist?.length ? checklist : DEFAULT_ATTRS;
  const required = item.required_attributes ?? item.missingAttributes ?? ['purpose', 'retention'];
  const isNonPii = item.status === NOT_PERSONAL;
  const detectedPii = item.detected_class && item.detected_class !== NOT_PERSONAL;

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState(() => {
    const init = { sensitivity: item.sensitivity && item.sensitivity !== 'None' ? item.sensitivity : 'High' };
    attrs.forEach((a) => { init[a.key] = item[a.key] ?? ''; });
    return init;
  });

  const submit = async (patch) => {
    setSaving(true);
    setError(null);
    try {
      await onSave(patch);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const patch = { sensitivity: formData.sensitivity };
    attrs.forEach((a) => { patch[a.key] = formData[a.key]?.trim() || null; });
    submit(patch);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="metadata-modal-title"
      className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
    >
      <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between sticky top-0">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-blue-100 text-blue-700"><ShieldCheck size={20} /></div>
          <div>
            <h3 id="metadata-modal-title" className="font-bold text-slate-800 text-base">Review Field Evidence &amp; Metadata</h3>
            <p className="text-xs text-slate-500 font-mono">
              {item.source}.<span className="text-blue-700 font-semibold">{item.field}</span>
            </p>
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 cursor-pointer">
          <X size={18} />
        </button>
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Technical detection evidence (read-only) */}
        <div className="text-xs">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">Technical Detection Evidence</h4>
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
            <EvidenceRow label="Detected class" value={item.detected_class ?? item.class ?? '—'} />
            <EvidenceRow label="Rule" value={item.rule_name ?? '—'} />
            <EvidenceRow label="Entity" value={item.pii_type ?? '—'} />
            <EvidenceRow label="Method" value={item.detection_method ?? '—'} />
            <EvidenceRow
              label="Values matched"
              value={item.samples_scanned ? `${item.samples_matched} / ${item.samples_scanned} (${Math.round((item.match_ratio ?? 0) * 100)}%)` : '—'}
            />
            <EvidenceRow label="Mean confidence" value={item.confidence != null ? `${Math.round(item.confidence * 100)}%` : '—'} />
            <EvidenceRow label="Column-name context boost" value={item.context_boost ? 'Yes' : 'No'} />
            <EvidenceRow label="Metadata link" value={item.metadata_link ?? '—'} />
            <EvidenceRow label="Review status" value={item.review_status ?? '—'} />
            {item.masked_examples?.length > 0 && (
              <div className="pt-2">
                <span className="text-slate-500">Masked samples</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.masked_examples.map((ex) => (
                    <code key={ex} className="bg-white border border-slate-200 rounded px-1.5 py-0.5 text-[11px]">{ex}</code>
                  ))}
                </div>
              </div>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Detection is technical evidence only. Whether this is personal data in a legal sense is the reviewer&apos;s decision.
          </p>
        </div>

        {/* Declared metadata form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Declared Metadata</h4>
          {isNonPii ? (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-600 flex gap-2">
              <AlertCircle size={16} className="text-slate-500 shrink-0" />
              <p>This field is classified as not personal data, so no purpose/retention evidence is required.</p>
            </div>
          ) : (
            <>
              {attrs.map((a) => {
                const isReq = required.includes(a.key);
                return (
                  <div key={a.key}>
                    <label htmlFor={`meta-${a.key}`} className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      {a.label} {isReq ? <span className="text-red-600">*</span> : <span className="normal-case font-normal text-slate-400">(optional)</span>}
                    </label>
                    <input
                      id={`meta-${a.key}`}
                      type="text"
                      required={isReq}
                      maxLength={200}
                      placeholder={PLACEHOLDERS[a.key] ?? ''}
                      value={formData[a.key] ?? ''}
                      onChange={(e) => setFormData({ ...formData, [a.key]: e.target.value })}
                      className="w-full text-sm bg-white border border-slate-200 rounded-lg p-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    />
                  </div>
                );
              })}
              <div>
                <label htmlFor="meta-sensitivity" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Handling Tier</label>
                <select
                  id="meta-sensitivity"
                  value={formData.sensitivity}
                  onChange={(e) => setFormData({ ...formData, sensitivity: e.target.value })}
                  className="w-full text-sm bg-white border border-slate-200 rounded-lg p-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="Critical">Critical</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
            </>
          )}

          {error && <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">{error}</p>}

          <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-end gap-2">
            {!isNonPii && (
              <>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => submit({ review_decision: 'non_pii' })}
                  className="px-3 py-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 flex items-center gap-1 cursor-pointer disabled:opacity-60"
                  title="Reviewer decision: this field is not personal data (false positive)"
                >
                  <Ban size={14} /> Mark Not Personal Data
                </button>
                {item.review_decision !== 'confirmed' && (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => submit({ review_decision: 'confirmed' })}
                    className="px-3 py-2 border border-emerald-200 rounded-lg text-xs font-semibold text-emerald-700 hover:bg-emerald-50 flex items-center gap-1 cursor-pointer disabled:opacity-60"
                    title="Reviewer confirms the detection is a personal-data field"
                  >
                    <BadgeCheck size={14} /> Confirm Detection
                  </button>
                )}
              </>
            )}
            {isNonPii && detectedPii && (
              <button
                type="button"
                disabled={saving}
                onClick={() => submit({ review_decision: 'reset' })}
                className="px-3 py-2 border border-blue-200 rounded-lg text-xs font-semibold text-blue-700 hover:bg-blue-50 flex items-center gap-1 cursor-pointer disabled:opacity-60"
              >
                <Undo2 size={14} /> Restore as {item.detected_class}
              </button>
            )}
            <button type="button" onClick={onClose} className="px-3 py-2 border border-slate-200 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-50 cursor-pointer">
              Close
            </button>
            {!isNonPii && (
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
              >
                <Check size={14} /> {saving ? 'Saving…' : 'Save Metadata'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}


export default function MetadataModal({ isOpen, onClose, item, checklist, onSave }) {
  if (!isOpen || !item) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <ModalForm key={item.id || item.field} item={item} checklist={checklist} onClose={onClose} onSave={onSave} />
    </div>
  );
}
