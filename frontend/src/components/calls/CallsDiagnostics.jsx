/**
 * BIBI Cars — W2A — CallsDiagnostics
 * =====================================
 * Admin-only side panel that explains WHY calls match (or don't match)
 * a particular customer. Helpful for triaging Ringostat link mismatches,
 * stale customer phones, orphan leads etc.
 *
 * Reads GET /api/admin/customers/{id}/calls/diagnostics.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  X, MagnifyingGlass, Bug, Phone, IdentificationCard, Funnel,
} from '@phosphor-icons/react';
import { API_URL } from '../../App';
import { useLang } from '../../i18n';
import MatchChips from './MatchChips';

const SectionTitle = ({ children, icon: Icon }) => (
  <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-[#71717A] mb-2 mt-4 first:mt-0">
    {Icon && <Icon size={14} weight="duotone" />}
    <span>{children}</span>
  </div>
);

const KV = ({ label, value, mono = true }) => (
  <div className="flex items-center justify-between py-1 border-b border-[#F4F4F5] last:border-0">
    <span className="text-xs text-[#71717A]">{label}</span>
    <span className={`text-xs ${mono ? 'font-mono' : ''} text-[#18181B]`}>{value ?? <span className="text-zinc-300">—</span>}</span>
  </div>
);

const ChipList = ({ items }) => {
  if (!items || items.length === 0) return <span className="text-zinc-300 text-xs">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((it, i) => (
        <span key={i} className="text-[11px] px-1.5 py-0.5 rounded-md bg-zinc-100 text-zinc-700 font-mono">{it}</span>
      ))}
    </div>
  );
};

const PerKeyBar = ({ label, count, total, color }) => {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="mb-1.5">
      <div className="flex items-center justify-between text-[11px] mb-0.5">
        <span className="text-[#52525B]">{label}</span>
        <span className="font-mono text-[#71717A]">{count} / {total} ({pct}%)</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

const CallsDiagnostics = ({ customerId, open, onClose }) => {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !customerId) return;
    let cancel = false;
    setLoading(true);
    setError(null);
    axios.get(`${API_URL}/api/admin/customers/${customerId}/calls/diagnostics`)
      .then((res) => { if (!cancel) setData(res.data); })
      .catch((e) => {
        if (cancel) return;
        const msg = e?.response?.data?.detail || e?.message || 'Failed to load diagnostics';
        setError(msg);
        if (e?.response?.status !== 401) toast.error(msg);
      })
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, [open, customerId]);

  if (!open) return null;

  const ids = data?.identifiers || {};
  const counts = data?.counts || {};
  const perKey = counts.perKey || {};
  const sample = data?.sample || [];
  const total = counts.matched || 0;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        data-testid="diagnostics-backdrop"
      />
      <aside
        className="fixed top-0 right-0 h-full w-full sm:w-[560px] bg-white shadow-2xl z-50 flex flex-col"
        data-testid="calls-diagnostics"
      >
        <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Bug size={20} weight="duotone" className="text-[#4F46E5]" />
              <h3 className="text-base font-semibold text-[#18181B]">
                {t('w2a_diag_title') || 'Calls matching diagnostics'}
              </h3>
            </div>
            <p className="text-xs text-[#71717A] mt-1">{t('w2a_diag_subtitle') || 'Why calls match this customer'}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-zinc-100" data-testid="diagnostics-close" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="py-10 text-center text-[#71717A] text-sm" data-testid="diagnostics-loading">
              {t('w2a_loading') || 'Loading…'}
            </div>
          )}
          {error && (
            <div className="py-10 text-center text-rose-600 text-sm" data-testid="diagnostics-error">{error}</div>
          )}
          {!loading && !error && data && (
            <>
              {/* Customer */}
              <SectionTitle icon={IdentificationCard}>
                {t('w2a_diag_customer') || 'Customer'}
              </SectionTitle>
              <div className="border border-[#E4E4E7] rounded-md p-3">
                <KV label="id"             value={data.customer?.id} />
                <KV label="name"           value={data.customer?.name} mono={false} />
                <KV label="phone"          value={data.customer?.phone} />
                <KV label="secondaryPhone" value={data.customer?.secondaryPhone} />
              </div>

              {/* Identifiers */}
              <SectionTitle icon={MagnifyingGlass}>
                {t('w2a_diag_identifiers') || 'Resolved identifiers'}
              </SectionTitle>
              <div className="border border-[#E4E4E7] rounded-md p-3 space-y-2">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">customerIds</div>
                  <ChipList items={ids.customerIds} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">leadIds</div>
                  <ChipList items={ids.leadIds} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">dealIds</div>
                  <ChipList items={ids.dealIds} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">phonesPrimary</div>
                  <ChipList items={ids.phonesPrimary} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">phonesSecondary</div>
                  <ChipList items={ids.phonesSecondary} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-[#71717A] mb-1">phonesLead</div>
                  <ChipList items={ids.phonesLead} />
                </div>
              </div>

              {/* Counters */}
              <SectionTitle icon={Funnel}>
                {t('w2a_diag_breakdown') || 'Match breakdown'} ({total})
              </SectionTitle>
              <div className="border border-[#E4E4E7] rounded-md p-3">
                <PerKeyBar label={t('w2a_match_customer_id')     || 'Customer ID'}     count={perKey.customer_id     || 0} total={total} color="bg-indigo-500" />
                <PerKeyBar label={t('w2a_match_lead_id')         || 'Lead ID'}         count={perKey.lead_id         || 0} total={total} color="bg-violet-500" />
                <PerKeyBar label={t('w2a_match_deal_id')         || 'Deal ID'}         count={perKey.deal_id         || 0} total={total} color="bg-amber-500" />
                <PerKeyBar label={t('w2a_match_phone_primary')   || 'Phone (primary)'} count={perKey.phone_primary   || 0} total={total} color="bg-emerald-500" />
                <PerKeyBar label={t('w2a_match_phone_secondary') || 'Phone (secondary)'} count={perKey.phone_secondary || 0} total={total} color="bg-teal-500" />
                <PerKeyBar label={t('w2a_match_phone_lead')      || 'Phone (lead)'}    count={perKey.phone_lead      || 0} total={total} color="bg-sky-500" />
              </div>

              {/* Coverage gaps */}
              <SectionTitle>
                {t('w2a_diag_gaps') || 'Coverage gaps'}
              </SectionTitle>
              <div className="border border-[#E4E4E7] rounded-md p-3 grid grid-cols-2 gap-3 text-xs">
                <div><div className="text-[#71717A]">{t('w2a_diag_with_recording') || 'With recording'}</div><div className="text-base font-semibold text-emerald-600">{counts.withRecording ?? 0}</div></div>
                <div><div className="text-[#71717A]">{t('w2a_diag_no_manager') || 'Without manager'}</div><div className="text-base font-semibold text-rose-600">{counts.missing?.withoutManager ?? 0}</div></div>
                <div><div className="text-[#71717A]">{t('w2a_diag_no_outcome') || 'Without outcome'}</div><div className="text-base font-semibold text-amber-600">{counts.missing?.withoutOutcome ?? 0}</div></div>
                <div><div className="text-[#71717A]">{t('w2a_diag_no_ai') || 'Without AI analysis'}</div><div className="text-base font-semibold text-zinc-600">{counts.missing?.withoutAI ?? 0}</div></div>
              </div>

              {/* Sample */}
              <SectionTitle icon={Phone}>
                {t('w2a_diag_sample') || 'Sample (latest 50)'}
              </SectionTitle>
              <div className="border border-[#E4E4E7] rounded-md overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-zinc-50 text-[10px] uppercase text-[#71717A]">
                    <tr>
                      <th className="text-left px-2 py-1.5">Call</th>
                      <th className="text-left px-2 py-1.5">Dir</th>
                      <th className="text-left px-2 py-1.5">Matched by</th>
                      <th className="text-left px-2 py-1.5">ACL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sample.map((s, i) => (
                      <tr key={s.callId || i} className="border-t border-[#F4F4F5]" data-testid={`diag-sample-${i}`}>
                        <td className="px-2 py-1.5 font-mono text-[10px]">{(s.callId || '').slice(0, 14)}</td>
                        <td className="px-2 py-1.5">{s.direction}</td>
                        <td className="px-2 py-1.5">
                          <MatchChips matchedBy={s.matchedBy} reasons={s.reasons} size="xs" />
                        </td>
                        <td className="px-2 py-1.5">
                          {s.permitted
                            ? <span className="text-emerald-600">✓</span>
                            : <span className="text-rose-500">✗</span>}
                        </td>
                      </tr>
                    ))}
                    {sample.length === 0 && (
                      <tr><td colSpan={4} className="px-2 py-3 text-center text-[#71717A]">no calls</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
};

export default CallsDiagnostics;
