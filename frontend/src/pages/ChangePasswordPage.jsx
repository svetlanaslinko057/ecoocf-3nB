/**
 * ChangePasswordPage — единая страница смены пароля для всех staff-ролей.
 * Доступна по /admin/profile/password, /team/profile/password,
 * /manager/profile/password (один компонент, тот же эндпоинт).
 *
 * UX:
 *   - три поля: current_password, new_password, confirm
 *   - LIVE policy meter (≥8, upper, lower, digit, special, no-whitespace)
 *     с галочками; правила приходят с бэкенда GET /api/auth/password-policy
 *   - submit → POST /api/auth/change-password (auth bearer уже в axios.defaults)
 *   - после успеха показывается success-баннер + redirect на свой workspace.
 *
 * Backend контракт:
 *   GET  /api/auth/password-policy → { rules: string[], … }
 *   POST /api/auth/password/validate { password } → { ok, failures, checks }
 *   POST /api/auth/change-password { current_password, new_password } → { success }
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  LockKey,
  Eye,
  EyeSlash,
  Check,
  X,
  ShieldCheck,
  Warning,
} from '@phosphor-icons/react';
import { useAuth } from '../App';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const RULE_LABELS = {
  length:        'At least 8 characters',
  lower:         'One lowercase letter (a-z)',
  upper:         'One uppercase letter (A-Z)',
  digit:         'One digit (0-9)',
  special:       'One special character (- _ ! @ # $ % …)',
  no_whitespace: 'No spaces or tabs',
};

const RULE_ORDER = ['length', 'lower', 'upper', 'digit', 'special', 'no_whitespace'];

const ChangePasswordPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [policy, setPolicy] = useState(null);
  const [checks, setChecks] = useState({
    length: false, lower: false, upper: false, digit: false, special: false, no_whitespace: true,
  });
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showCur, setShowCur] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showCnf, setShowCnf] = useState(false);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  // Load policy descriptor on mount.
  useEffect(() => {
    axios.get(`${API_URL}/api/auth/password-policy`).then((r) => setPolicy(r.data)).catch(() => {});
  }, []);

  // Live policy meter — runs locally; we mirror the backend rules so we don't
  // hit the server for each keystroke. Backend validates again on submit.
  useEffect(() => {
    const pwd = newPwd || '';
    setChecks({
      length:        pwd.length >= 8,
      lower:         /[a-z]/.test(pwd),
      upper:         /[A-Z]/.test(pwd),
      digit:         /[0-9]/.test(pwd),
      special:       /[!@#$%^&*()_+\-=\[\]{};:,.?/\\|<>~'"]/.test(pwd),
      no_whitespace: !/\s/.test(pwd),
    });
  }, [newPwd]);

  const allChecksOk = RULE_ORDER.every((k) => checks[k]);
  const confirmMatches = confirm.length > 0 && newPwd === confirm;
  const canSubmit = !!currentPwd && allChecksOk && confirmMatches && !busy;

  const submit = useCallback(async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setError('');
    if (!canSubmit) return;
    setBusy(true);
    try {
      const resp = await axios.post(`${API_URL}/api/auth/change-password`, {
        current_password: currentPwd,
        new_password: newPwd,
      });
      // The backend bumps tokenVersion (revoking all prior sessions) and
      // returns a fresh JWT so THIS session stays alive. Persist it.
      const fresh = resp?.data?.access_token;
      if (fresh) {
        localStorage.setItem('token', fresh);
        axios.defaults.headers.common['Authorization'] = `Bearer ${fresh}`;
      }
      setSuccess(true);
      toast.success('Password updated. Other sessions were signed out.');
      // Stay on the page; user can navigate back.
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Change failed';
      setError(typeof detail === 'string' ? detail : 'Change failed');
      toast.error(typeof detail === 'string' ? detail : 'Change failed');
    } finally {
      setBusy(false);
    }
  }, [canSubmit, currentPwd, newPwd]);

  const back = () => {
    const role = (user?.role || '').toLowerCase();
    if (role === 'manager') navigate('/manager');
    else if (role === 'team_lead') navigate('/team/dashboard');
    else navigate('/admin');
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl mx-auto p-4 sm:p-6 space-y-5"
      data-testid="change-password-page"
    >
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-2xl bg-amber-100 border border-amber-200 flex items-center justify-center">
          <LockKey size={22} className="text-amber-700" weight="duotone" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[#18181B]">Change password</h1>
          <p className="text-sm text-[#71717A]">
            Update the password for your <strong>{user?.email}</strong> account ({(user?.role || '').replace('_', ' ')}).
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5 sm:p-7">
        <form onSubmit={submit} className="space-y-5" autoComplete="off">
          {/* Current password */}
          <div>
            <label className="block text-[11px] uppercase tracking-[0.14em] text-[#52525B] font-semibold mb-1.5">
              Current password
            </label>
            <div className="relative">
              <input
                type={showCur ? 'text' : 'password'}
                value={currentPwd}
                onChange={(e) => setCurrentPwd(e.target.value)}
                placeholder="Enter your current password"
                className="w-full h-11 pl-3 pr-10 rounded-lg bg-[#FAFAFA] border border-[#E4E4E7] outline-none focus:border-[#FEAE00] focus:ring-2 focus:ring-[#FEAE00]/30"
                data-testid="current-password-input"
                autoComplete="current-password"
                required
              />
              <button type="button" onClick={() => setShowCur(!showCur)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-[#F4F4F5] text-[#71717A]">
                {showCur ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* New password + live meter */}
          <div>
            <label className="block text-[11px] uppercase tracking-[0.14em] text-[#52525B] font-semibold mb-1.5">
              New password
            </label>
            <div className="relative">
              <input
                type={showNew ? 'text' : 'password'}
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                placeholder="At least 8 chars · upper · lower · digit · special"
                className="w-full h-11 pl-3 pr-10 rounded-lg bg-[#FAFAFA] border border-[#E4E4E7] outline-none focus:border-[#FEAE00] focus:ring-2 focus:ring-[#FEAE00]/30"
                data-testid="new-password-input"
                autoComplete="new-password"
                required
              />
              <button type="button" onClick={() => setShowNew(!showNew)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-[#F4F4F5] text-[#71717A]">
                {showNew ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <ul className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {RULE_ORDER.map((k) => {
                const ok = checks[k];
                return (
                  <li key={k}
                    data-testid={`pwd-rule-${k}`}
                    className={`flex items-center gap-2 text-[12px] ${ok ? 'text-emerald-700' : 'text-[#71717A]'}`}>
                    {ok
                      ? <Check size={14} weight="bold" className="text-emerald-600" />
                      : <X size={14} className="text-[#D4D4D8]" />}
                    {RULE_LABELS[k]}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Confirm */}
          <div>
            <label className="block text-[11px] uppercase tracking-[0.14em] text-[#52525B] font-semibold mb-1.5">
              Repeat new password
            </label>
            <div className="relative">
              <input
                type={showCnf ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat the new password"
                className={`w-full h-11 pl-3 pr-10 rounded-lg bg-[#FAFAFA] border outline-none focus:ring-2 ${
                  confirm.length === 0
                    ? 'border-[#E4E4E7] focus:border-[#FEAE00] focus:ring-[#FEAE00]/30'
                    : confirmMatches
                      ? 'border-emerald-300 focus:border-emerald-400 focus:ring-emerald-100'
                      : 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                }`}
                data-testid="confirm-password-input"
                autoComplete="new-password"
                required
              />
              <button type="button" onClick={() => setShowCnf(!showCnf)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-[#F4F4F5] text-[#71717A]">
                {showCnf ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirm.length > 0 && !confirmMatches && (
              <p className="mt-1 text-[12px] text-rose-600 flex items-center gap-1">
                <Warning size={12} weight="fill" /> Passwords don’t match.
              </p>
            )}
          </div>

          {error && (
            <div data-testid="change-password-error"
              className="text-[13px] text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3 flex items-start gap-2">
              <Warning size={14} weight="fill" className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div data-testid="change-password-success"
              className="text-[13px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-start gap-2">
              <ShieldCheck size={16} weight="fill" className="mt-0.5 flex-shrink-0" />
              <span>Password updated successfully. Use the new password on your next login.</span>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={!canSubmit} data-testid="change-password-submit"
              className="inline-flex items-center gap-2 px-5 h-11 rounded-lg bg-[#18181B] text-white font-semibold hover:bg-[#27272A] disabled:opacity-40 disabled:cursor-not-allowed">
              {busy ? 'Updating…' : 'Update password'}
            </button>
            <button type="button" onClick={back} data-testid="change-password-back"
              className="px-4 h-11 rounded-lg bg-white border border-[#E4E4E7] text-[#52525B] hover:bg-[#FAFAFA]">
              Back
            </button>
          </div>
        </form>
      </div>

      <div className="text-[12px] text-[#71717A] leading-relaxed">
        <strong className="text-[#52525B]">Policy:</strong>{' '}
        {policy?.rules?.join(' · ') || 'Loaded from server on mount.'}
      </div>
    </motion.div>
  );
};

export default ChangePasswordPage;
