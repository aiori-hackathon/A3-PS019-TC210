import { AlertOctagon, RefreshCw } from 'lucide-react';

export default function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
      <AlertOctagon size={16} className="mt-0.5 shrink-0 text-red-600" />
      <p className="flex-1">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 rounded-md border border-red-300 bg-white px-2 py-1 font-semibold text-red-700 hover:bg-red-100 cursor-pointer"
        >
          <RefreshCw size={12} /> Retry
        </button>
      )}
    </div>
  );
}
