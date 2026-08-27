/**
 * RingostatSupervisionPanel
 * -------------------------
 * Passive supervision widget for team leads and admins.
 *
 *   - Team lead → sees team's calls (scope=team)
 *   - Admin/owner/master_admin → sees company-wide calls (scope=company)
 *
 * Renders a small floating card (bottom-right) with a few KPIs:
 *   total / answered / missed / pending_outcome / unassigned / answer_rate
 * and a "View team" button that opens a full breakdown sheet.
 *
 * Designed to NOT interrupt: no toasts, no popups, no forced banners.
 * Polls every 60 sec.
 */
import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Phone, PhoneOff, PhoneCall, Users, AlertTriangle, X } from 'lucide-react';
import { useLang } from '../../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

function getToken() {
  return (
    localStorage.getItem('token') ||
    localStorage.getItem('auth_token') ||
    localStorage.getItem('access_token') ||
    ''
  );
}

async function jget(path) {
  const r = await fetch(`${BACKEND_URL}${path}`, {
    credentials: 'include',
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function RingostatSupervisionPanel({ role = '' }) {
  const { t } = useLang();
  // Tiny template helper for `{n}` substitutions in translated strings.
  const tn = (key, vars = {}) =>
    Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)), t(key));
  const [overview, setOverview] = useState(null);
  const [managers, setManagers] = useState([]);
  const [period, setPeriod] = useState(1); // 1=today, 7=week
  const [sheetOpen, setSheetOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    // Default to collapsed so the floating panel doesn't overlap data
    // tables (e.g. Customer 360 Deposits/Sales action column). The pill
    // remains visible and one click expands the full panel.
    const stored = localStorage.getItem('ringostat_supervision_collapsed');
    return stored === null ? true : stored === '1';
  });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const isCompany = ['admin', 'owner', 'master_admin'].includes((role || '').toLowerCase());

  const load = async () => {
    try {
      setErr('');
      const ov = await jget(`/api/teamlead/calls/overview?days=${period}`);
      setOverview(ov);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  const loadManagers = async () => {
    try {
      const m = await jget(`/api/teamlead/calls/managers?days=${period}`);
      setManagers(m.rows || []);
    } catch (e) {
      // ignore
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  useEffect(() => {
    if (sheetOpen) loadManagers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetOpen]);

  if (loading) return null;
  if (err || !overview) return null;

  const kpi = overview.totals || {};
  const alerts = overview.alerts || {};
  const hasAlerts =
    alerts.many_missed || alerts.many_pending_outcome || alerts.many_unassigned;

  if (collapsed) {
    return (
      <button
        onClick={() => {
          setCollapsed(false);
          localStorage.removeItem('ringostat_supervision_collapsed');
        }}
        className={`fixed bottom-4 right-4 z-40 rounded-full shadow-lg p-3 transition flex items-center gap-2
          ${hasAlerts ? 'bg-amber-500 text-white animate-pulse' : 'bg-slate-700 text-white hover:bg-slate-800'}`}
        title={t(isCompany ? 'rs_company_calls_overview' : 'rs_team_calls_overview')}
        data-testid="ringostat-supervision-collapsed"
      >
        <PhoneCall className="h-5 w-5" />
        <span className="text-xs font-semibold">{kpi.all ?? 0}</span>
      </button>
    );
  }

  return (
    <>
      <Card className="fixed bottom-4 right-4 z-40 w-[320px] shadow-2xl border-slate-200 dark:border-slate-700" data-testid="ringostat-supervision-panel">
        <CardContent className="p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Users className="h-4 w-4 text-blue-600" />
              {t(isCompany ? 'rs_company_calls' : 'rs_team_calls')}
              <Badge variant="outline" className="text-[10px]">
                {period === 1 ? t('rs_today') : tn(period === 7 ? 'rs_7d' : 'rs_last_days_tpl', { n: period })}
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              <button
                className={`text-[10px] px-1.5 py-0.5 rounded ${period === 1 ? 'bg-blue-500 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}
                onClick={() => setPeriod(1)}
                data-testid="ringostat-period-1d"
              >
                {t('rs_1d')}
              </button>
              <button
                className={`text-[10px] px-1.5 py-0.5 rounded ${period === 7 ? 'bg-blue-500 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}
                onClick={() => setPeriod(7)}
                data-testid="ringostat-period-7d"
              >
                {t('rs_7d')}
              </button>
              <button
                className="text-slate-400 hover:text-slate-700 ml-1"
                onClick={() => {
                  setCollapsed(true);
                  localStorage.setItem('ringostat_supervision_collapsed', '1');
                }}
                title={t('rs_collapse')}
                data-testid="ringostat-supervision-collapse"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-xl font-bold text-slate-900 dark:text-slate-100">{kpi.all ?? 0}</div>
              <div className="text-[10px] text-slate-500">{t('rs_total')}</div>
            </div>
            <div>
              <div className="text-xl font-bold text-green-600">{kpi.answered ?? 0}</div>
              <div className="text-[10px] text-slate-500">{t('rs_answered')}</div>
            </div>
            <div>
              <div className={`text-xl font-bold ${kpi.missed > 5 ? 'text-red-600' : 'text-slate-500'}`}>
                {kpi.missed ?? 0}
              </div>
              <div className="text-[10px] text-slate-500">{t('rs_missed')}</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t border-slate-100 dark:border-slate-800">
            <div>
              <div className="text-lg font-semibold">{kpi.answer_rate ?? 0}%</div>
              <div className="text-[10px] text-slate-500">{t('rs_rate')}</div>
            </div>
            <div>
              <div className={`text-lg font-semibold ${kpi.pending_outcome > 10 ? 'text-amber-600' : 'text-slate-500'}`}>
                {kpi.pending_outcome ?? 0}
              </div>
              <div className="text-[10px] text-slate-500">{t('rs_pending')}</div>
            </div>
            <div>
              <div className={`text-lg font-semibold ${kpi.unassigned > 5 ? 'text-red-600' : 'text-slate-500'}`}>
                {kpi.unassigned ?? 0}
              </div>
              <div className="text-[10px] text-slate-500">{t('rs_unassigned')}</div>
            </div>
          </div>

          {hasAlerts && (
            <div className="flex items-start gap-1.5 p-2 bg-amber-50 dark:bg-amber-950/30 rounded text-[11px] text-amber-800 dark:text-amber-300">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
              <div>
                {alerts.many_missed && <div>• {t('rs_too_many_missed')} ({kpi.missed})</div>}
                {alerts.many_pending_outcome && <div>• {kpi.pending_outcome} {t('rs_calls_waiting_outcomes')}</div>}
                {alerts.many_unassigned && <div>• {kpi.unassigned} {t('rs_unassigned_check_sip')}</div>}
              </div>
            </div>
          )}

          <Button
            size="sm"
            variant="outline"
            className="w-full text-xs"
            onClick={() => setSheetOpen(true)}
            data-testid="ringostat-supervision-breakdown"
          >
            {t(isCompany ? 'rs_view_company_breakdown' : 'rs_view_team_breakdown')}
          </Button>
        </CardContent>
      </Card>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle>
              {t(isCompany ? 'rs_company_calls_overview' : 'rs_team_calls_overview')}
            </SheetTitle>
            <SheetDescription>
              {period === 1 ? t('rs_last_24h') : tn('rs_last_days_tpl', { n: period })} ·{' '}
              {overview.scope === 'company' ? t('rs_all_managers') : tn('rs_members_tpl', { n: overview.team_size || 0 })}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-2">
            {managers.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-6">
                {t('rs_no_call_data')}
              </div>
            )}
            {managers.map((m) => (
              <div
                key={m.manager_id || 'unassigned'}
                className={`p-2 rounded border ${
                  m.manager_id ? 'border-slate-200 dark:border-slate-700' : 'border-red-200 bg-red-50 dark:bg-red-950/30'
                }`}
              >
                <div className="flex items-center justify-between text-sm">
                  <div className="font-semibold">{m.manager_name}</div>
                  {m.role && (
                    <Badge variant="outline" className="text-[10px]">
                      {m.role}
                    </Badge>
                  )}
                </div>
                <div className="grid grid-cols-4 gap-1 mt-1 text-center text-xs">
                  <div>
                    <div className="font-semibold">{m.total}</div>
                    <div className="text-[10px] text-slate-500">{t('rs_total').toLowerCase()}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-green-600">{m.answered}</div>
                    <div className="text-[10px] text-slate-500">{t('rs_short_ans')}</div>
                  </div>
                  <div>
                    <div className={`font-semibold ${m.missed > 0 ? 'text-red-600' : ''}`}>{m.missed}</div>
                    <div className="text-[10px] text-slate-500">{t('rs_short_miss')}</div>
                  </div>
                  <div>
                    <div className={`font-semibold ${m.pending_outcome > 0 ? 'text-amber-600' : ''}`}>
                      {m.pending_outcome}
                    </div>
                    <div className="text-[10px] text-slate-500">{t('rs_short_pend')}</div>
                  </div>
                </div>
                {m.last_call_at && (
                  <div className="text-[10px] text-slate-400 mt-1">
                    {t('rs_short_last')} {new Date(m.last_call_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
