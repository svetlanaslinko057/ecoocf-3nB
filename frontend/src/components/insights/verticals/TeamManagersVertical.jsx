/**
 * TeamManagersVertical.jsx — hidden for manager role.
 *  Sections:
 *   1. Manager Scorecards (ranking + KPIs)
 *   2. Manager Load Board
 *   3. SLA / Response Time
 *   4. Login Activity Audit
 */
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { Users, Clock, Shield, Trophy } from '@phosphor-icons/react';
import { InsightsCard, InsightsSection, InsightsLoading, InsightsEmpty, MetricChip } from '../shared/InsightsCard';
import { safeGet, fmtCompact, fmtPct } from '../shared/insightsApi';
import ManagerDrillSheet from '../shared/ManagerDrillSheet';
import { useLang } from '../../../i18n';

const TeamManagersVertical = ({ scope, period = 30 }) => {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [scorecards, setScorecards] = useState([]);
  const [load, setLoad] = useState([]);
  const [perf, setPerf] = useState(null);
  const [loginAudit, setLoginAudit] = useState([]);
  const [drillManager, setDrillManager] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [lb, mgrs, perfRes, audit] = await Promise.all([
        safeGet('/api/admin/kpi/leaderboard'),
        safeGet('/api/team/managers'),
        safeGet('/api/team/performance'),
        safeGet('/api/admin/login-audit', { limit: 50 }),
      ]);
      if (!alive) return;
      setScorecards(lb.data?.managers || []);
      setLoad(Array.isArray(mgrs.data) ? mgrs.data : mgrs.data?.items || []);
      setPerf(perfRes.data || {});
      setLoginAudit(Array.isArray(audit.data) ? audit.data : audit.data?.items || audit.data?.events || []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [scope, period]);

  if (loading) return <InsightsLoading rows={8} />;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-6">
      <InsightsSection id="manager-scorecards" title={t('ins_sec_scorecards')} subtitle={t('ins_sec_scorecards_sub')} tip={t('ins_tip_scorecards')}>
        <InsightsCard testId="insights-manager-scorecards-table" padded={false}>
          {scorecards.length === 0 ? <div className="p-5"><InsightsEmpty title="No managers data" /></div> : (
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">#</th>
                  <th className="px-4 py-2 text-left font-medium">Manager</th>
                  <th className="px-4 py-2 text-left font-medium">Role</th>
                  <th className="px-4 py-2 text-right font-medium">Leads</th>
                  <th className="px-4 py-2 text-right font-medium">Converted</th>
                  <th className="px-4 py-2 text-right font-medium">Score</th>
                </tr></thead>
                <tbody>
                  {scorecards.map((m, i) => (
                    <tr key={m.id || i} className="border-b border-zinc-50 cursor-pointer hover:bg-zinc-50" onClick={() => setDrillManager(m)} data-testid={`insights-scorecard-row-${i}`}>
                      <td className="px-4 py-2 tabular-nums text-zinc-500">{i+1}</td>
                      <td className="px-4 py-2 font-medium text-zinc-900"><Trophy size={12} weight="duotone" className={`mr-1 inline ${i===0?'text-amber-500':i===1?'text-zinc-400':i===2?'text-amber-700':'text-transparent'}`} />{m.name || m.email}</td>
                      <td className="px-4 py-2 text-zinc-600">{m.role}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.leads)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.conversions)}</td>
                      <td className="px-4 py-2 text-right"><MetricChip value={fmtPct(m.score)} tone={m.score>=50?'positive':m.score>=20?'warning':'negative'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="load-board" title={t('ins_sec_load_board')} subtitle={t('ins_sec_load_board_sub')} tip={t('ins_tip_load_board')}>
        <InsightsCard testId="insights-manager-load-board" padded={false}>
          {load.length === 0 ? <div className="p-5"><InsightsEmpty title="No managers" /></div> : (
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">Manager</th>
                  <th className="px-4 py-2 text-right font-medium">Leads</th>
                  <th className="px-4 py-2 text-right font-medium">Customers</th>
                  <th className="px-4 py-2 text-right font-medium">Deals</th>
                  <th className="px-4 py-2 text-right font-medium">Tasks</th>
                  <th className="px-4 py-2 text-right font-medium">Load</th>
                </tr></thead>
                <tbody>
                  {load.map((m, i) => {
                    const total = (m.leadsCount ?? m.leads ?? 0) + (m.customersCount ?? m.customers ?? 0) + (m.dealsCount ?? m.deals ?? 0);
                    const overload = total > 50;
                    return (
                      <tr key={m.id || i} className="border-b border-zinc-50 cursor-pointer hover:bg-zinc-50" onClick={() => setDrillManager(m)} data-testid={`insights-load-row-${i}`}>
                        <td className="px-4 py-2 font-medium text-zinc-900">{m.name || m.email}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.leadsCount ?? m.leads ?? 0)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.customersCount ?? m.customers ?? 0)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.dealsCount ?? m.deals ?? 0)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(m.tasksCount ?? m.tasks ?? 0)}</td>
                        <td className="px-4 py-2 text-right"><MetricChip value={total} tone={overload?'negative':total>25?'warning':'positive'} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="sla-response" title={t('ins_sec_sla_response')} subtitle={t('ins_sec_sla_response_sub')} tip={t('ins_tip_sla_response')}>
        <InsightsCard testId="insights-sla-response-card">
          {!perf?.responseTime || (Array.isArray(perf?.responseTime) && perf.responseTime.length === 0) ? <InsightsEmpty title="No response time data" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={Array.isArray(perf.responseTime) ? perf.responseTime : Object.entries(perf.responseTime || {}).map(([name, val]) => ({ name, value: val }))} margin={{ top: 4, right: 8, left: -16, bottom: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#71717a' }} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={32} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Bar dataKey="value" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="login-audit" title={t('ins_sec_login_audit')} subtitle={t('ins_sec_login_audit_sub')} tip={t('ins_tip_login_audit')}>
        <InsightsCard testId="insights-login-audit-table" padded={false}>
          {loginAudit.length === 0 ? <div className="p-5"><InsightsEmpty title="No login events yet" /></div> : (
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">User</th>
                  <th className="px-4 py-2 text-left font-medium">Role</th>
                  <th className="px-4 py-2 text-left font-medium">When</th>
                  <th className="px-4 py-2 text-left font-medium">IP / Device</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                </tr></thead>
                <tbody>
                  {loginAudit.slice(0, 100).map((e, i) => (
                    <tr key={e._id || e.id || i} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-4 py-2 font-medium text-zinc-900">{e.email || e.userEmail || e.user || '—'}</td>
                      <td className="px-4 py-2 text-zinc-700">{e.role || '—'}</td>
                      <td className="px-4 py-2 text-zinc-500">{e.ts || e.timestamp || e.createdAt || '—'}</td>
                      <td className="px-4 py-2 text-zinc-600">{e.ip || '—'} {e.userAgent ? `· ${(e.userAgent || '').slice(0, 30)}` : ''}</td>
                      <td className="px-4 py-2"><MetricChip value={e.status || (e.success ? 'success' : 'failed')} tone={e.success || e.status==='success' ? 'positive' : 'negative'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      {/* Manager drill-down sheet — opens on row click in Scorecards / Load Board */}
      <ManagerDrillSheet open={!!drillManager} onOpenChange={(o) => !o && setDrillManager(null)} manager={drillManager} />
    </motion.div>
  );
};

export default TeamManagersVertical;
