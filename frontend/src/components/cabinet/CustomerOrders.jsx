/**
 * Customer-facing orders/workflow view (used inside CustomerCabinet).
 * Replaces previous mock with real data from /api/customer-cabinet/{id}/orders.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { CheckCircle2, Clock, Loader2, Package, Receipt, Circle } from 'lucide-react';

import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_BADGE = {
  pending:     'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed:   'bg-emerald-100 text-emerald-700',
  cancelled:   'bg-rose-100 text-rose-700',
};

const STEP_META = {
  pending:     { icon: Circle,        color: 'text-gray-300',     label: 'Awaiting' },
  in_progress: { icon: Loader2,       color: 'text-blue-500 animate-spin', label: 'In Progress' },
  done:        { icon: CheckCircle2,  color: 'text-emerald-500',  label: 'Done' },
  skipped:     { icon: Clock,         color: 'text-amber-500',    label: 'Skipped' },
};

const fmt = (n, ccy = 'usd') => {
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: (ccy || 'USD').toUpperCase() }).format(n || 0); }
  catch { return `${(n || 0).toFixed(2)}`; }
};

export default function CustomerOrders({ customerId }) {
  const { t } = useLang();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/orders`);
      setOrders(r.data?.items || []);
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, [customerId]);

  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  if (loading && orders.length === 0) {
    return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  if (orders.length === 0) {
    return (
      <div className="text-center py-12 bg-white border border-dashed border-gray-200 rounded-2xl">
        <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="font-medium text-gray-700">{t('adm3_80bbd509fb')}</p>
        <p className="text-xs text-gray-500 mt-1">{t('adm3_af140b878b')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {orders.map((o) => {
        const totalSteps = (o.steps || []).length;
        const doneSteps = (o.steps || []).filter((s) => s.status === 'done').length;
        const pct = totalSteps ? Math.round((doneSteps / totalSteps) * 100) : 0;
        // Group steps by service
        const groups = {};
        for (const s of (o.steps || [])) {
          const key = s.service_item_id || 'other';
          if (!groups[key]) groups[key] = { name: s.service_name || t('adm3_108ede1c95'), steps: [] };
          groups[key].steps.push(s);
        }
        return (
          <div key={o.id} className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
            <div className="bg-gradient-to-r from-[#635BFF]/5 to-[#9D8EFF]/5 px-5 py-4 border-b border-gray-100">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{t('adm3_59b93795b2')}</p>
                  <p className="font-mono text-xs text-gray-700 mt-0.5">{o.id}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg text-gray-900">{fmt(o.amount, o.currency)}</p>
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium mt-1 ${STATUS_BADGE[o.status] || 'bg-gray-100 text-gray-600'}`}>{o.status === 'in_progress' ? t('adm3_877d2292fb') : o.status === 'completed' ? t('adm3_d0ec66887b') : o.status}</span>
                </div>
              </div>
              <div className="mt-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>{t('adm3_7274b0d653')}</span>
                  <span className="font-medium">{doneSteps}/{totalSteps} • {pct}%</span>
                </div>
                <div className="h-2 bg-white border border-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-[#635BFF] to-[#9D8EFF] rounded-full transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            </div>

            <div className="p-5 space-y-4">
              {Object.entries(groups).map(([gid, g]) => {
                const gDone = g.steps.filter((s) => s.status === 'done').length;
                const gTotal = g.steps.length;
                return (
                  <div key={gid}>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-semibold text-gray-900">{g.name}</h4>
                      <span className="text-xs text-gray-500">{gDone}/{gTotal}</span>
                    </div>
                    <div className="space-y-1.5 pl-1">
                      {g.steps.map((s) => {
                        const meta = STEP_META[s.status] || STEP_META.pending;
                        const Icon = meta.icon;
                        return (
                          <div key={s.id} className="flex items-center gap-3 py-1">
                            <Icon className={`w-4 h-4 ${meta.color} shrink-0`} />
                            <span className={`text-sm ${s.status === 'done' ? 'text-gray-500 line-through' : s.status === 'in_progress' ? 'text-gray-900 font-medium' : 'text-gray-600'}`}>{s.label}</span>
                            {s.note && <span className="text-xs text-gray-400 italic">— {s.note}</span>}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              {o.invoiceId && (
                <div className="pt-3 border-t border-gray-100 flex items-center gap-1.5 text-xs text-gray-500">
                  <Receipt className="w-3.5 h-3.5" /> {t('adm3_3b5a72d11b')} <span className="font-mono">{o.invoiceId}</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
