/**
 * Admin Security page — /admin/security
 *
 * Combines three concerns that belong together for the admin:
 *   1. "My 2FA" — set up Google Authenticator on the current admin
 *      account. Per-user TOTP via /api/me/2fa/*.
 *   2. Team-lead OTP recipient — where the team-lead login codes
 *      are addressed. Admin reads them in the panel below.
 *   3. Pending team-lead OTP codes — fallback view since there is
 *      no SMTP integration. Admin reads the code and forwards it
 *      to the team-lead by phone/messenger.
 *   4. Daily-reset config — toggle the manager 12:00 Sofia auto-logout.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  ShieldCheck,
  EnvelopeSimple,
  Clock,
  Lock,
  Check,
  X,
  ArrowsClockwise,
  Eye,
  EyeSlash,
  CopySimple,
  Warning,
  DesktopTower,
  DeviceMobile,
  Globe,
  UserCircle,
  Hourglass,
} from '@phosphor-icons/react';
import RefreshButton from '../../components/ui/RefreshButton';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const fmt = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return String(iso); }
};

/* ─────────────────────────────────────────────────────── 2FA section */
const TwoFactorSection = () => {
  const [status, setStatus] = useState(null);
  const [setupData, setSetupData] = useState(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/me/2fa/status`);
      setStatus(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load 2FA status');
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const beginSetup = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API_URL}/api/me/2fa/setup`);
      setSetupData(data);
      setCode('');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Setup failed');
    } finally {
      setBusy(false);
    }
  };

  const verifySetup = async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/me/2fa/verify`, { code: code.trim() });
      toast.success('2FA enabled');
      setSetupData(null);
      setCode('');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Invalid code');
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    if (!window.confirm('Disable 2FA on this account?')) return;
    const c = window.prompt('Enter current 6-digit code to confirm:');
    if (!c) return;
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/me/2fa/disable`, { code: c });
      toast.success('2FA disabled');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to disable');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5 sm:p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <ShieldCheck size={20} weight="bold" />
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-[#18181B]">My two-factor authentication</h2>
          <p className="text-xs text-[#71717A] mt-0.5">
            Protects your admin account with Google Authenticator. Required for admin role logins when enabled.
          </p>
        </div>
        {status?.enabled && (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-emerald-100 text-emerald-700">
            Active
          </span>
        )}
      </div>

      {!status?.enabled && !setupData && (
        <div className="space-y-3">
          <p className="text-sm text-[#52525B]">2FA is currently <strong>off</strong>. Click below to start setup.</p>
          <button onClick={beginSetup} disabled={busy} data-testid="begin-2fa-setup"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400 text-[#18181B] font-semibold hover:bg-amber-300 disabled:opacity-50">
            <Lock size={16} weight="bold" /> Set up Google Authenticator
          </button>
        </div>
      )}

      {setupData && (
        <div className="space-y-4">
          <div className="flex items-start gap-4 flex-wrap">
            <img src={setupData.qrCode} alt="QR" className="w-44 h-44 border border-[#E4E4E7] rounded-xl" data-testid="2fa-qr" />
            <div className="flex-1 min-w-0 space-y-2">
              <p className="text-sm text-[#52525B]">
                1. Open <strong>Google Authenticator</strong> on your phone.<br />
                2. Scan the QR code, or enter the secret manually.<br />
                3. Enter the 6-digit code below to activate.
              </p>
              <div className="flex items-center gap-2">
                <code className="text-xs bg-[#F4F4F5] px-2 py-1 rounded font-mono">
                  {showSecret ? setupData.secret : '•'.repeat(setupData.secret.length)}
                </code>
                <button onClick={() => setShowSecret((s) => !s)} className="p-1 hover:bg-[#F4F4F5] rounded">
                  {showSecret ? <EyeSlash size={14} /> : <Eye size={14} />}
                </button>
                <button onClick={() => { navigator.clipboard?.writeText(setupData.secret); toast.success('Copied'); }}
                  className="p-1 hover:bg-[#F4F4F5] rounded">
                  <CopySimple size={14} />
                </button>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input type="text" inputMode="numeric" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000" data-testid="2fa-verify-code"
              className="input w-32 text-center tracking-widest font-mono" />
            <button onClick={verifySetup} disabled={busy || code.length !== 6} data-testid="2fa-verify-submit"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#18181B] text-white text-sm font-semibold hover:bg-[#27272A] disabled:opacity-50">
              <Check size={14} weight="bold" /> Activate
            </button>
            <button onClick={() => setSetupData(null)} className="px-3 py-2 rounded-xl bg-white border border-[#E4E4E7] text-sm hover:bg-[#FAFAFA]">
              Cancel
            </button>
          </div>
        </div>
      )}

      {status?.enabled && (
        <button onClick={disable} disabled={busy} data-testid="2fa-disable"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-rose-200 text-rose-700 text-sm font-medium hover:bg-rose-50">
          <X size={14} weight="bold" /> Disable 2FA
        </button>
      )}
    </div>
  );
};

/* ────────────────────────────────────── Team-lead OTP config & pending */
const TeamLeadOtpSection = () => {
  const [recipient, setRecipient] = useState('');
  const [savedRecipient, setSavedRecipient] = useState('');
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const cfg = await axios.get(`${API_URL}/api/admin/security/team-lead-otp-config`);
      setRecipient(cfg.data?.recipient_email || '');
      setSavedRecipient(cfg.data?.recipient_email || '');
      const pen = await axios.get(`${API_URL}/api/admin/security/pending-otps`, { params: { limit: 25 } });
      setPending(Array.isArray(pen.data?.data) ? pen.data.data : []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load OTP config');
    }
  }, []);
  useEffect(() => {
    load();
    const id = setInterval(load, 10_000); // refresh pending every 10s
    return () => clearInterval(id);
  }, [load]);

  const saveRecipient = async () => {
    setBusy(true);
    try {
      await axios.put(`${API_URL}/api/admin/security/team-lead-otp-config`, {
        recipient_email: recipient.trim() || null,
      });
      toast.success('Recipient saved');
      setSavedRecipient(recipient.trim());
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5 sm:p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <EnvelopeSimple size={20} weight="bold" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-[#18181B]">Team-lead OTP recipient</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Where the team-lead login codes are addressed. The admin reads the code in the panel below and forwards it by phone/messenger — no SMTP needed.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input type="email" value={recipient} onChange={(e) => setRecipient(e.target.value)}
            placeholder="e.g. admin@bibi.cars" data-testid="otp-recipient-input"
            className="input flex-1 min-w-[200px]" />
          <button onClick={saveRecipient} disabled={busy || recipient.trim() === (savedRecipient || '').trim()}
            data-testid="otp-recipient-save"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#18181B] text-white text-sm font-semibold hover:bg-[#27272A] disabled:opacity-50">
            <Check size={14} weight="bold" /> Save
          </button>
        </div>
        {!savedRecipient && (
          <div className="mt-3 flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-2.5">
            <Warning size={14} weight="fill" className="flex-shrink-0 mt-0.5" />
            <span>No recipient set. Codes will be addressed to each team-lead's own email by default — you should still read them here.</span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-[#E4E4E7]">
          <div className="flex items-center gap-2">
            <Clock size={18} className="text-[#18181B]" />
            <h3 className="font-semibold text-[#18181B]">Pending OTP codes ({pending.length})</h3>
          </div>
          <RefreshButton
            onClick={load}
            ariaLabel="Refresh pending codes"
            size="sm"
            testId="pending-otps-refresh"
          />
        </div>
        {pending.length === 0 ? (
          <div className="p-8 text-center text-sm text-[#71717A]">No pending codes — clean queue.</div>
        ) : (
          <div className="divide-y divide-[#F4F4F5]" data-testid="pending-otps-list">
            {pending.map((o) => (
              <div key={o.id} className="p-4 flex items-center gap-4 hover:bg-[#FAFAFA]">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-[#18181B] truncate">{o.user_email}</div>
                  <div className="text-[10px] text-[#A1A1AA]">Issued {fmt(o.created_at)} · Expires {fmt(o.expires_at)} · {o.attempts}/5 attempts</div>
                </div>
                <code className="text-2xl font-mono font-bold tracking-[0.3em] text-amber-700 bg-amber-50 px-3 py-1 rounded-lg" data-testid={`otp-code-${o.id}`}>
                  {o.code}
                </code>
                <button onClick={() => { navigator.clipboard?.writeText(o.code); toast.success('Code copied'); }}
                  className="p-2 hover:bg-[#F4F4F5] rounded-lg text-[#52525B]" title="Copy">
                  <CopySimple size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ──────────────────────────────────────────────── Daily reset section */
const DailyResetSection = () => {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/admin/security/daily-reset-config`);
      setCfg(data);
    } catch {/* silent */}
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async () => {
    if (!cfg) return;
    setBusy(true);
    try {
      await axios.put(`${API_URL}/api/admin/security/daily-reset-config`, { enabled: !cfg.enabled });
      toast.success(`Daily reset ${!cfg.enabled ? 'enabled' : 'disabled'}`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to toggle');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5 sm:p-6">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <Clock size={20} weight="bold" />
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-[#18181B]">Manager daily session reset</h2>
          <p className="text-xs text-[#71717A] mt-0.5">
            Forces every manager to log in again every day at 12:00 Europe/Sofia. Admins and team-leads are unaffected.
          </p>
        </div>
        {cfg && (
          <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full ${
            cfg.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-[#F4F4F5] text-[#71717A]'
          }`}>
            {cfg.enabled ? 'On' : 'Off'}
          </span>
        )}
      </div>
      <div className="flex justify-center mt-4">
        <button onClick={toggle} disabled={busy || !cfg} data-testid="daily-reset-toggle"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#18181B] text-white text-sm font-semibold hover:bg-[#27272A] disabled:opacity-50">
          {cfg?.enabled ? 'Disable daily reset' : 'Enable daily reset'}
        </button>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────── Manager re-logins (post 12:00 Sofia) */
const ManagerReloginsSection = () => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data: payload } = await axios.get(`${API_URL}/api/admin/security/manager-relogins`);
      setData(payload);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load manager re-logins');
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const mgrs = data?.managers || [];
  const summary = data?.summary || {};
  const sinceLabel = data?.since_label || '—';

  return (
    <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5 sm:p-6" data-testid="manager-relogins-section">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center flex-shrink-0">
            <UserCircle size={20} weight="bold" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[#18181B]">Manager re-logins since 12:00 Europe/Sofia</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Daily reset cuts every manager session at <strong>12:00 Europe/Sofia</strong>.
              Each morning they have to sign in again. This table shows exactly
              <strong> who did, when, from where and on what device</strong>.
              <br />
              <span className="text-[#A1A1AA]">Since: {sinceLabel}</span>
            </p>
          </div>
        </div>
        <RefreshButton
          onClick={load}
          loading={busy}
          ariaLabel="Refresh manager re-logins"
          testId="manager-relogins-refresh"
        />
      </div>

      {/* Summary chips */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="px-3 py-2.5 rounded-xl border border-[#E4E4E7] bg-[#FAFAFA]">
          <div className="text-[10px] uppercase tracking-wider text-[#71717A] font-semibold">Managers</div>
          <div className="text-xl font-bold text-[#18181B]">{summary.total_managers ?? '—'}</div>
        </div>
        <div className="px-3 py-2.5 rounded-xl border border-emerald-200 bg-emerald-50">
          <div className="text-[10px] uppercase tracking-wider text-emerald-700 font-semibold">Signed back in</div>
          <div className="text-xl font-bold text-emerald-700">{summary.relogged_in ?? '—'}</div>
        </div>
        <div className={`px-3 py-2.5 rounded-xl border ${(summary.pending || 0) > 0 ? 'border-amber-200 bg-amber-50' : 'border-[#E4E4E7] bg-[#FAFAFA]'}`}>
          <div className={`text-[10px] uppercase tracking-wider font-semibold ${(summary.pending || 0) > 0 ? 'text-amber-700' : 'text-[#71717A]'}`}>Still pending</div>
          <div className={`text-xl font-bold ${(summary.pending || 0) > 0 ? 'text-amber-700' : 'text-[#18181B]'}`}>{summary.pending ?? '—'}</div>
        </div>
      </div>

      {mgrs.length === 0 ? (
        <div className="text-center text-sm text-[#71717A] py-6 border border-dashed border-[#E4E4E7] rounded-xl">
          No manager accounts found.
        </div>
      ) : (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-sm" data-testid="manager-relogins-table">
            <thead className="bg-[#FAFAFA] border-y border-[#E4E4E7]">
              <tr className="text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                <th className="px-3 py-2 font-semibold">Manager</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">First re-login</th>
                <th className="px-3 py-2 font-semibold">IP</th>
                <th className="px-3 py-2 font-semibold">Device</th>
                <th className="px-3 py-2 font-semibold text-center">Logins today</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F4F4F5]">
              {mgrs.map((m) => {
                const Icon = (m.device?.kind === 'phone' || m.device?.kind === 'tablet') ? DeviceMobile : DesktopTower;
                return (
                  <tr key={m.id || m.email}
                    className={m.relogged_in ? 'hover:bg-[#FAFAFA]' : 'bg-amber-50/40 hover:bg-amber-50/60'}
                    data-testid={`manager-relogin-row-${m.email}`}>
                    <td className="px-3 py-3">
                      <div className="font-semibold text-[#18181B]">{m.name}</div>
                      <div className="text-[11px] text-[#A1A1AA]">{m.email}</div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {m.relogged_in ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold uppercase tracking-wider">
                          <Check size={10} weight="bold" /> Signed back in
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold uppercase tracking-wider">
                          <Hourglass size={10} weight="fill" /> Pending {m.pending_minutes != null ? `· ${m.pending_minutes}m` : ''}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs text-[#52525B] whitespace-nowrap">
                      {m.relogged_in ? (
                        <>
                          <div className="font-medium text-[#18181B]">{fmt(m.first_login_at)}</div>
                          {m.minutes_since_reset_to_login != null && (
                            <div className="text-[10px] text-[#A1A1AA]">
                              +{m.minutes_since_reset_to_login}m after reset
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="text-[#A1A1AA] italic">— hasn't signed in yet</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs text-[#52525B] whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Globe size={12} className="text-[#A1A1AA]" />
                        {m.ip || '—'}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <div className="flex items-center gap-2 text-[#52525B]">
                        <Icon size={14} className="text-[#A1A1AA]" />
                        <span className="font-medium">{m.device?.os || '—'}</span>
                        <span className="text-[#A1A1AA]">·</span>
                        <span>{m.device?.browser || '—'}</span>
                      </div>
                      {m.user_agent && (
                        <div className="text-[10px] text-[#A1A1AA] truncate max-w-[260px]" title={m.user_agent}>
                          {m.user_agent}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="inline-block px-2 py-0.5 rounded-md bg-[#F4F4F5] text-[#27272A] text-xs font-semibold tabular-nums">
                        {m.login_count_since}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

/* ────────────────────────────────────────────────────── Page wrapper */
const AdminSecurityPage = () => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    data-testid="admin-security-page"
    className="space-y-5"
  >
    {/* Unified PageHeader — matches Executive Center spec */}
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
        <ShieldCheck size={20} weight="bold" />
      </div>
      <div className="min-w-0 flex-1">
        <h1
          className="text-2xl font-bold text-[#18181B] leading-tight"
          style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
        >
          Security
        </h1>
        <p className="text-[12px] text-[#71717A] mt-0.5">
          2FA, team-lead OTP delivery, daily-reset policy, and manager re-login compliance.
        </p>
      </div>
    </div>

    <ManagerReloginsSection />
    <TwoFactorSection />
    <TeamLeadOtpSection />
    <DailyResetSection />
  </motion.div>
);

export default AdminSecurityPage;
