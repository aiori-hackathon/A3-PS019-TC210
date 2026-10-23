import { useEffect } from 'react';
import { Trash2, AlertTriangle, X, Loader2, Database, Tag } from 'lucide-react';

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  item,
  isDeleting = false
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isDeleting) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, isDeleting, onClose]);

  if (!isOpen || !item) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDeleting) {
          onClose();
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div 
        className="bg-white rounded-2xl shadow-2xl border border-slate-200/90 w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-150 relative"
      >
        {/* Header Accent Bar */}
        <div className="h-1.5 w-full bg-gradient-to-r from-rose-500 via-rose-600 to-amber-500" />

        {/* Content Container */}
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 shrink-0 shadow-xs">
                <Trash2 size={22} />
              </div>
              <div>
                <h3 id="delete-dialog-title" className="text-base font-bold text-slate-900 tracking-tight">
                  Delete Non-PII Record
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Confirm permanent removal from active inventory
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              disabled={isDeleting}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40 cursor-pointer"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </div>

          {/* Target Item Details Card */}
          <div className="mt-5 p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Field Name</span>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-200/70 text-slate-700 border border-slate-300">
                Non-PII Record
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-slate-900 bg-white px-2.5 py-1 rounded-lg border border-slate-200 shadow-2xs">
                {item.field}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] text-slate-600 border-t border-slate-200/60">
              <div className="flex items-center gap-1.5 truncate">
                <Database size={12} className="text-slate-400 shrink-0" />
                <span className="truncate font-mono" title={item.source}>{item.source || 'N/A'}</span>
              </div>
              <div className="flex items-center gap-1.5 truncate justify-end">
                <Tag size={12} className="text-slate-400 shrink-0" />
                <span className="truncate">{item.class || 'Non-PII'}</span>
              </div>
            </div>
          </div>

          {/* Informational Callout */}
          <div className="mt-4 p-3 rounded-xl bg-amber-50/70 border border-amber-200/80 flex items-start gap-2.5 text-xs text-amber-900 leading-relaxed">
            <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
            <p>
              This field is classified as <strong>Non-PII</strong>. Deleting it removes it from the inventory without affecting evidence coverage metrics. A later scan of the same source will list it again.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isDeleting}
              className="px-4 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-all disabled:opacity-50 cursor-pointer"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => onConfirm(item)}
              disabled={isDeleting}
              className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 active:bg-rose-800 rounded-xl shadow-xs hover:shadow transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
            >
              {isDeleting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Deleting…</span>
                </>
              ) : (
                <>
                  <Trash2 size={14} />
                  <span>Delete Record</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
