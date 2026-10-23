import { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, Search, Plus, X, Play, Zap, Trash2, Lock } from 'lucide-react';
import { api, errorMessage } from '../services/api';
import ErrorBanner from '../components/common/ErrorBanner';

const CLASSES = ['Name', 'Email ID', 'Phone Number', 'Financial Data', 'Government ID'];
const EMPTY_RULE = { name: '', identifier: '', category: 'Government ID', pattern: '', confidenceThreshold: 60, context: '', columnKeywords: '' };
const inputCls = 'w-full text-sm bg-white border border-slate-200 rounded-lg p-2.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500';

export default function DetectionRules() {
  const [rules, setRules] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [testText, setTestText] = useState('Customer KYC record: Name: Rohan Sharma, Aadhaar: 3412 8921 5432, PAN: ABCDE1234F, Phone: +919876543210, Card: 4111 1111 1111 1111, Email: rohan.sharma@example.com');
  const [testContext, setTestContext] = useState('');
  const [testResults, setTestResults] = useState(null);
  const [testing, setTesting] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRule, setNewRule] = useState(EMPTY_RULE);
  const [formError, setFormError] = useState(null);

  const load = useCallback(async () => {
    try {
      setRules(await api.getRules());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const runLiveTest = async () => {
    setTesting(true);
    try {
      setTestResults(await api.testRules(testText, testContext));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  const toggleRule = async (id) => {
    try {
      const updated = await api.toggleRule(id);
      setRules((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const deleteRule = async (rule) => {
    if (!window.confirm(`Delete custom rule "${rule.name}"?`)) return;
    try {
      await api.deleteRule(rule.id);
      setRules((prev) => prev.filter((r) => r.id !== rule.id));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleCreateRule = async (e) => {
    e.preventDefault();
    setFormError(null);
    try {
      const created = await api.createRule(newRule);
      setRules((prev) => [...prev, created]);
      setShowAddModal(false);
      setNewRule(EMPTY_RULE);
    } catch (err) {
      setFormError(errorMessage(err));
    }
  };

  const q = search.toLowerCase();
  const filteredRules = rules.filter((r) => [r.name, r.identifier, r.category].join(' ').toLowerCase().includes(q));

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Detection Rules</h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              {rules.filter((r) => r.enabled).length} of {rules.length} active
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-0.5">
            Configurable rules from <code>config/rules.yaml</code>. These are the rules the scanner and evaluation actually use; changes apply to the next scan.
          </p>
        </div>
        <button type="button" onClick={() => { setShowAddModal(true); setFormError(null); }}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer">
          <Plus size={16} /> New Custom Rule
        </button>
      </div>

      <ErrorBanner message={error} onRetry={load} />

      <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
        <div className="flex items-center gap-2 mb-2">
          <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600"><Zap size={16} /></div>
          <h2 className="text-sm font-bold text-slate-900">Rule Sandbox</h2>
          <span className="text-[11px] text-slate-400">Runs the real detector with all enabled rules</span>
        </div>
        <div className="space-y-3">
          <label htmlFor="sandbox-text" className="sr-only">Sandbox text</label>
          <textarea id="sandbox-text" rows={3} value={testText} onChange={(e) => setTestText(e.target.value)} maxLength={10000}
            className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none" />
          <div className="flex flex-wrap items-center gap-3">
            <input type="text" aria-label="Simulated column name" placeholder="Optional column name for context (e.g. account_number)" value={testContext}
              onChange={(e) => setTestContext(e.target.value)} className="flex-1 min-w-[240px] text-xs p-2 bg-slate-50 border border-slate-200 rounded-lg" />
            <button type="button" onClick={runLiveTest} disabled={testing || !testText.trim()}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50">
              <Play size={13} className="fill-white" /> {testing ? 'Evaluating…' : 'Evaluate Text'}
            </button>
          </div>
          {testResults && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">{testResults.length} rule(s) matched</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {testResults.map((res) => (
                  <div key={res.ruleId} className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between text-xs gap-2">
                    <div>
                      <p className="font-bold text-slate-800">{res.ruleName} <span className="font-normal text-slate-400">→ {res.category}</span></p>
                      <p className="text-[11px] font-mono text-blue-600 mt-0.5 break-all">{res.matches.join(', ')}</p>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded shrink-0">{res.confidence}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
        <input type="search" aria-label="Search rules" placeholder="Search rules..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredRules.map((rule) => (
          <div key={rule.id} className={`p-5 rounded-xl border card-shadow bg-white space-y-3 ${rule.enabled ? 'border-slate-200' : 'border-slate-200/60 opacity-60'}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-bold text-slate-900 text-sm">{rule.name}</h3>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">{rule.identifier}</span>
                  {rule.builtin ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-50 text-slate-500 border border-slate-200 flex items-center gap-1"><Lock size={9} /> rules.yaml</span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200">custom</span>
                  )}
                  {!rule.available && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-700 border border-red-200">unavailable</span>}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">→ {rule.category}</p>
              </div>
              <div className="flex items-center gap-2">
                {!rule.builtin && (
                  <button type="button" onClick={() => deleteRule(rule)} aria-label={`Delete ${rule.name}`} className="p-1 text-rose-500 hover:bg-rose-50 rounded cursor-pointer"><Trash2 size={14} /></button>
                )}
                <button type="button" role="switch" aria-checked={rule.enabled} aria-label={`${rule.enabled ? 'Disable' : 'Enable'} ${rule.name}`} onClick={() => toggleRule(rule.id)}
                  className={`w-11 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors ${rule.enabled ? 'bg-blue-600' : 'bg-slate-300'}`}>
                  <div className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${rule.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                </button>
              </div>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 font-mono text-[11px] text-slate-700 break-all">
              <span className="text-slate-400 select-none mr-2">pattern:</span>{rule.pattern}
            </div>
            {rule.context?.length > 0 && (
              <p className="text-[11px] text-slate-500">Context words: <span className="font-mono">{rule.context.join(', ')}</span></p>
            )}
            <div className="flex items-center justify-between text-xs pt-1 text-slate-500 border-t border-slate-100">
              <span>Method: <strong className="text-slate-700">{rule.algorithm}</strong></span>
              <span className="text-blue-700 font-semibold bg-blue-50 px-2 py-0.5 rounded border border-blue-100 shrink-0">≥ {rule.confidenceThreshold}% conf</span>
            </div>
          </div>
        ))}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="new-rule-title" className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-blue-100 text-blue-700"><ShieldCheck size={20} /></div>
                <div>
                  <h3 id="new-rule-title" className="font-bold text-slate-800 text-base">Create Custom Regex Rule</h3>
                  <p className="text-xs text-slate-500">Base score 85%; +context boost when the column name contains a context word</p>
                </div>
              </div>
              <button type="button" aria-label="Close" onClick={() => setShowAddModal(false)} className="p-1 rounded-lg text-slate-400 hover:bg-slate-200 cursor-pointer"><X size={18} /></button>
            </div>
            <form onSubmit={handleCreateRule} className="p-6 space-y-4 text-xs">
              <div>
                <label htmlFor="r-name" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Rule Name *</label>
                <input id="r-name" required maxLength={80} placeholder="e.g. Employee ID" value={newRule.name} onChange={(e) => setNewRule({ ...newRule, name: e.target.value })} className={inputCls} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="r-id" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Identifier *</label>
                  <input id="r-id" required pattern="[A-Z][A-Z0-9_]{1,40}" title="UPPER_SNAKE_CASE" placeholder="EMP_ID" value={newRule.identifier}
                    onChange={(e) => setNewRule({ ...newRule, identifier: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_') })} className={`${inputCls} font-mono`} />
                </div>
                <div>
                  <label htmlFor="r-cat" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Data Class</label>
                  <select id="r-cat" value={newRule.category} onChange={(e) => setNewRule({ ...newRule, category: e.target.value })} className={inputCls}>
                    {CLASSES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="r-pattern" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Regex Pattern *</label>
                <input id="r-pattern" required maxLength={500} placeholder="\bEMP-[0-9]{6}\b" value={newRule.pattern} onChange={(e) => setNewRule({ ...newRule, pattern: e.target.value })} className={`${inputCls} font-mono`} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="r-ctx" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Context words</label>
                  <input id="r-ctx" placeholder="employee, staff" value={newRule.context} onChange={(e) => setNewRule({ ...newRule, context: e.target.value })} className={inputCls} />
                </div>
                <div>
                  <label htmlFor="r-kw" className="block font-bold text-slate-700 uppercase tracking-wider mb-1">Column keywords</label>
                  <input id="r-kw" placeholder="empid, employee" value={newRule.columnKeywords} onChange={(e) => setNewRule({ ...newRule, columnKeywords: e.target.value })} className={inputCls} />
                </div>
              </div>
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label htmlFor="r-th" className="font-bold text-slate-700 uppercase tracking-wider">Minimum confidence</label>
                  <span className="font-mono font-bold text-blue-700">{newRule.confidenceThreshold}%</span>
                </div>
                <input id="r-th" type="range" min="30" max="99" value={newRule.confidenceThreshold}
                  onChange={(e) => setNewRule({ ...newRule, confidenceThreshold: Number(e.target.value) })} className="w-full accent-blue-600" />
                <p className="text-[11px] text-slate-400 mt-1">Above 85% only matches with column-name context will count.</p>
              </div>
              {formError && <p role="alert" className="text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">{formError}</p>}
              <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
                <button type="button" onClick={() => setShowAddModal(false)} className="px-4 py-2 border border-slate-200 rounded-lg font-medium text-slate-600 hover:bg-slate-50 cursor-pointer">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold cursor-pointer">Register Rule</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
