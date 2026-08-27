/**
 * Login Audit page — журнал входов сотрудников.
 *
 * Используется ДВУМЯ роутами:
 *   /admin/login-audit  → admin scope, источник /api/admin/login-audit
 *   /team/login-audit   → team-lead scope, источник /api/team-lead/login-audit
 *
 * Сам компонент один — endpoint и заголовок выбираются по prop `scope`.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  ShieldCheck,
  Globe,
  DesktopTower,
  DeviceMobile,
  CheckCircle,
  XCircle,
  ArrowsClockwise,
  Funnel,
  EnvelopeSimple,
  Key,
  SignOut,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';
import RefreshButton from '../../components/ui/RefreshButton';
import WhiteSelect from '../../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const METHOD_PILL = {
  password:    { bg: '#EEF2FF', color: '#4338CA', label: 'Password',   Icon: Key },
  totp:        { bg: '#ECFDF5', color: '#047857', label: 'TOTP',       Icon: ShieldCheck },
  email_otp:   { bg: '#FFF7ED', color: '#C2410C', label: 'Email-OTP',  Icon: EnvelopeSimple },
  manual:      { bg: '#F4F4F5', color: '#52525B', label: 'Manual',     Icon: SignOut },
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return String(iso); }
};

const DeviceCell = ({ device, ua }) => {
  const os = device?.os || 'Unknown';
  const br = device?.browser || 'Unknown';
  const kind = device?.kind || 'desktop';
  const Icon = kind === 'phone' || kind === 'tablet' ? DeviceMobile : DesktopTower;
  return (
    <div className="flex items-center gap-2 text-xs text-[#52525B]">
      <Icon size={14} />
      <span className="font-medium">{os}</span>
      <span className="text-[#A1A1AA]">·</span>
      <span>{br}</span>
      {ua && <span title={ua} className="text-[#A1A1AA] text-[10px] truncate max-w-[180px]">{ua}</span>}
    </div>
  );
};

const LoginAuditPage = ({ scope = 'admin' }) => {
  const { t } = useLang();
  const endpoint = scope === 'team'
    ? `${API_URL}/api/team-lead/login-audit`
    : `${API_URL}/api/admin/login-audit`;
  const title = scope === 'team' ? 'Team Login Audit' : 'Login Audit';
  const subtitle = scope === 'team'
    ? 'Every staff login — managers, team-leads, admins. Filter, audit, follow-up.'
    : 'Every staff login from the past 30 days. Filter by method, role, success.';

  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    role: '',
    method: '',
    event: '',
    success: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 300 };
      if (filters.role)    params.role = filters.role;
      if (filters.method)  params.method = filters.method;
      if (filters.event)   params.event = filters.event;
      if (filters.success !== '') params.success = filters.success === 'true';
      const { data } = await axios.get(endpoint, { params });
      setItems(Array.isArray(data?.data) ? data.data : []);
      setSummary(data?.summary || {});
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load audit');
    } finally {
      setLoading(false);
    }
  }, [endpoint, filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const summaryCards = useMemo(() => ([
    { label: 'Logins today',  value: summary.loginsToday ?? 0, color: '#18181B' },
    { label: 'Last 7 days',   value: summary.logins7d ?? 0,    color: '#18181B' },
    { label: 'Failed today',  value: summary.failedToday ?? 0, color: (summary.failedToday || 0) > 0 ? '#DC2626' : '#18181B', alert: (summary.failedToday || 0) > 0 },
    { label: 'Unique users today', value: summary.uniqueUsersToday ?? 0, color: '#18181B' },
  ]), [summary]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid={`login-audit-${scope}`}
      className="space-y-5"
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ShieldCheck size={20} weight="bold" />
          </div>
          <div className="min-w-0 flex-1">
            <h1
              className="text-2xl font-bold text-[#18181B] leading-tight"
              style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
            >
              {title}
            </h1>
            <p className="text-[12px] text-[#71717A] mt-0.5">{subtitle}</p>
          </div>
        </div>
        <RefreshButton
          onClick={fetchData}
          loading={loading}
          ariaLabel="Refresh login audit"
          testId="login-audit-refresh"
        />
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {summaryCards.map((c) => (
          <div
            key={c.label}
            className={`bg-white rounded-2xl border ${c.alert ? 'border-rose-200 ring-1 ring-rose-100' : 'border-[#E4E4E7]'} p-4`}
          >
            <div className="text-xs font-medium uppercase tracking-wider text-[#71717A] mb-1">{c.label}</div>
            <div className="text-2xl font-bold" style={{ color: c.color }}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Filters — white-themed dropdowns matching the design system (see WhiteSelect). */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] p-3 flex flex-wrap items-center gap-2 sm:gap-3">
        <Funnel size={16} className="text-[#71717A] ml-1 flex-shrink-0" />
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 sm:gap-3 flex-1 min-w-0">
          <div className="min-w-0 sm:w-[160px]">
            <WhiteSelect
              value={filters.role}
              onChange={(e) => setFilters({ ...filters, role: e.target.value })}
              ariaLabel="Filter by role"
              data-testid="audit-filter-role"
              options={[
                { value: '', label: 'All roles' },
                { value: 'admin', label: 'Admin' },
                { value: 'team_lead', label: 'Team lead' },
                { value: 'manager', label: 'Manager' },
              ]}
            />
          </div>
          <div className="min-w-0 sm:w-[160px]">
            <WhiteSelect
              value={filters.method}
              onChange={(e) => setFilters({ ...filters, method: e.target.value })}
              ariaLabel="Filter by method"
              data-testid="audit-filter-method"
              options={[
                { value: '', label: 'All methods' },
                { value: 'password', label: 'Password' },
                { value: 'totp', label: 'TOTP' },
                { value: 'email_otp', label: 'Email-OTP' },
                { value: 'manual', label: 'Manual' },
              ]}
            />
          </div>
          <div className="min-w-0 sm:w-[160px]">
            <WhiteSelect
              value={filters.event}
              onChange={(e) => setFilters({ ...filters, event: e.target.value })}
              ariaLabel="Filter by event"
              data-testid="audit-filter-event"
              options={[
                { value: '', label: 'All events' },
                { value: 'login', label: 'Login' },
                { value: 'logout', label: 'Logout' },
              ]}
            />
          </div>
          <div className="min-w-0 sm:w-[160px]">
            <WhiteSelect
              value={filters.success}
              onChange={(e) => setFilters({ ...filters, success: e.target.value })}
              ariaLabel="Filter by outcome"
              data-testid="audit-filter-outcome"
              options={[
                { value: '', label: 'All outcomes' },
                { value: 'true', label: 'Success' },
                { value: 'false', label: 'Failed' },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-sm text-[#71717A]">Loading…</div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center text-sm text-[#71717A]">No login events match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="login-audit-table">
              <thead className="bg-[#FAFAFA] border-b border-[#E4E4E7]">
                <tr className="text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                  <th className="px-4 py-3 font-semibold">When</th>
                  <th className="px-4 py-3 font-semibold">User</th>
                  <th className="px-4 py-3 font-semibold">Role</th>
                  <th className="px-4 py-3 font-semibold">Event</th>
                  <th className="px-4 py-3 font-semibold">Method</th>
                  <th className="px-4 py-3 font-semibold">IP</th>
                  <th className="px-4 py-3 font-semibold">Device</th>
                  <th className="px-4 py-3 font-semibold text-center">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F4F4F5]">
                {items.map((it) => {
                  const m = METHOD_PILL[it.method] || METHOD_PILL.password;
                  const MIcon = m.Icon;
                  return (
                    <tr key={it.id} className="hover:bg-[#FAFAFA]" data-testid={`audit-row-${it.id}`}>
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-[#52525B]">{fmtDate(it.at)}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-[#18181B]">{it.user_name || it.user_email || '—'}</div>
                        {it.user_email && it.user_name && (
                          <div className="text-[10px] text-[#A1A1AA]">{it.user_email}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-[#F4F4F5] text-[#52525B]">
                          {it.role || '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-[#18181B] capitalize">{(it.event || '').replace(/_/g,' ')}</td>
                      <td className="px-4 py-3">
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
                          style={{ background: m.bg, color: m.color }}
                        >
                          <MIcon size={10} weight="fill" /> {m.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-[#52525B]">
                        <div className="flex items-center gap-1">
                          <Globe size={12} className="text-[#A1A1AA]" />
                          {it.ip || '—'}
                        </div>
                      </td>
                      <td className="px-4 py-3"><DeviceCell device={it.device} ua={it.user_agent} /></td>
                      <td className="px-4 py-3 text-center">
                        {it.success
                          ? <CheckCircle size={18} weight="fill" className="text-emerald-600 inline" />
                          : <XCircle size={18} weight="fill" className="text-rose-600 inline" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default LoginAuditPage;
