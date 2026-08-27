/**
 * Login page — two-step authentication.
 * ─────────────────────────────────────
 * Step 1: email + password (all roles).
 * Step 2 (conditional, returned by backend as `challenge`):
 *   - 'totp'      → ADMIN with Google Authenticator enabled.
 *   - 'email_otp' → TEAM_LEAD: code goes to the master-admin who
 *                   forwards it to the team-lead by phone/messenger.
 *
 * Manager has no step 2 but his session is reset daily at 12:00
 * Europe/Sofia (handled server-side + a global axios interceptor).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../App';
import { toast } from 'sonner';
import {
  Eye,
  EyeSlash,
  ArrowRight,
  ShieldCheck,
  EnvelopeSimple,
  ArrowLeft,
  ArrowsClockwise,
} from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLang } from '../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const Login = () => {
  const { t } = useLang();
  const { login, completeChallenge } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  /* ── step 1: credentials ─────────────────────────────────────────── */
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  /* ── step 2: challenge ───────────────────────────────────────────── */
  // Active challenge payload from backend (null until step 1 succeeds).
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Inform the user if they were bounced here by the daily-reset interceptor.
  useEffect(() => {
    if (params.get('reason') === 'daily_reset') {
      toast.info(
        'Your daily session has reset (12:00 Europe/Sofia). Please log in again.',
        { duration: 5000 },
      );
    }
  }, [params]);

  // Resend cooldown countdown.
  useEffect(() => {
    if (!cooldown) return undefined;
    const id = setTimeout(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  /* ── helpers ─────────────────────────────────────────────────────── */
  const routeForRole = (role) => {
    if (role === 'manager') return '/manager';
    if (role === 'team_lead') return '/team';
    return '/admin';
  };

  /* ── step 1: submit credentials ──────────────────────────────────── */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result && result.__challenge) {
        // Second step required.
        setChallenge(result);
        setCode('');
        setCooldown(60);
        return;
      }
      // No second step → straight in.
      toast.success(t('loginSuccess'));
      navigate(routeForRole(result?.role));
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        toast.error(t('i18n_too_many_attempts_try_again_in_92a703') || 'Too many attempts');
      } else if (status === 401) {
        toast.error(t('i18n_invalid_email_or_password_a04dee') || 'Invalid email or password');
      } else {
        toast.error(err.response?.data?.detail || err.response?.data?.message || t('loginError'));
      }
    } finally {
      setLoading(false);
    }
  };

  /* ── step 2: verify TOTP or email-OTP ────────────────────────────── */
  const handleVerify = async (e) => {
    e?.preventDefault?.();
    if (!code.trim()) {
      toast.error('Enter the 6-digit code');
      return;
    }
    setVerifying(true);
    try {
      let user;
      if (challenge.challenge === 'totp') {
        user = await completeChallenge('/api/auth/2fa/verify', {
          user_id: challenge.user_id,
          code: code.trim(),
        });
      } else if (challenge.challenge === 'email_otp') {
        user = await completeChallenge('/api/auth/email-otp/verify', {
          challenge_token: challenge.challenge_token,
          code: code.trim(),
        });
      }
      toast.success(t('loginSuccess') || 'Welcome back');
      navigate(routeForRole(user?.role));
    } catch (err) {
      const detail = err.response?.data?.detail || '';
      if (detail.includes('expired')) {
        toast.error('Code expired. Request a new one.');
      } else if (detail.includes('too_many_attempts')) {
        toast.error('Too many attempts. Restart the login.');
        setChallenge(null);
      } else if (detail.includes('invalid')) {
        toast.error('Wrong code — try again.');
      } else {
        toast.error(detail || 'Verification failed');
      }
    } finally {
      setVerifying(false);
    }
  };

  /* ── step 2: resend email-OTP ────────────────────────────────────── */
  const handleResend = async () => {
    if (cooldown > 0 || challenge?.challenge !== 'email_otp') return;
    setResending(true);
    try {
      const { data } = await axios.post(`${API_URL}/api/auth/email-otp/request`, {
        user_id: challenge.user_id,
      });
      setChallenge({ ...challenge, challenge_token: data.challenge_token });
      setCode('');
      setCooldown(60);
      toast.success('New code issued. Ask the master-admin for it.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to issue a new code');
    } finally {
      setResending(false);
    }
  };

  /* ── render ──────────────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-[#F7F7F8] flex items-center justify-center p-4">
      <motion.div
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-8 shadow-sm">
          <div className="flex items-center justify-center mb-6">
            <img src="/images/logo.svg" alt="Logo" className="h-12 w-auto" />
          </div>

          <AnimatePresence mode="wait">
            {!challenge && (
              <motion.form
                key="step1"
                onSubmit={handleSubmit}
                data-testid="login-form"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
              >
                <div className="space-y-5">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                      {t('email')}
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="input w-full"
                      placeholder="email@example.com"
                      required
                      data-testid="login-email-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                      {t('password')}
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="input w-full pr-12"
                        placeholder="••••••••"
                        required
                        data-testid="login-password-input"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-[#18181B]"
                        data-testid="toggle-password-btn"
                      >
                        {showPassword ? <EyeSlash size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="btn-primary w-full py-3 mt-2"
                    data-testid="login-submit-btn"
                  >
                    {loading ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        {t('loading')}
                      </span>
                    ) : (
                      <span className="flex items-center justify-center gap-2">
                        {t('loginButton')}
                        <ArrowRight size={18} />
                      </span>
                    )}
                  </button>
                </div>
              </motion.form>
            )}

            {challenge && (
              <motion.form
                key="step2"
                onSubmit={handleVerify}
                data-testid="login-challenge-form"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.2 }}
                className="space-y-5"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center flex-shrink-0">
                    {challenge.challenge === 'totp' ? (
                      <ShieldCheck size={22} className="text-amber-600" weight="duotone" />
                    ) : (
                      <EnvelopeSimple size={22} className="text-amber-600" weight="duotone" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-[#18181B]">
                      {challenge.challenge === 'totp'
                        ? 'Two-factor authentication'
                        : 'Verification required'}
                    </div>
                    <div className="text-xs text-[#71717A] mt-0.5">
                      {challenge.challenge === 'totp' ? (
                        <>Open Google Authenticator and enter the 6-digit code for <strong>{challenge.user_email}</strong>.</>
                      ) : (
                        <>A code was issued for <strong>{challenge.user_email}</strong>. Ask the master-admin (<code className="bg-[#F4F4F5] px-1 rounded">{challenge.recipient_masked}</code>) for the 6-digit code.</>
                      )}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                    Code
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    className="input w-full text-center tracking-[0.5em] text-2xl font-bold"
                    placeholder="000000"
                    data-testid="login-otp-input"
                    autoFocus
                  />
                </div>

                <button
                  type="submit"
                  disabled={verifying || code.length !== 6}
                  data-testid="login-otp-verify"
                  className="btn-primary w-full py-3"
                >
                  {verifying ? 'Verifying…' : 'Verify and continue'}
                </button>

                <div className="flex items-center justify-between text-xs">
                  <button
                    type="button"
                    onClick={() => { setChallenge(null); setCode(''); }}
                    className="inline-flex items-center gap-1 text-[#71717A] hover:text-[#18181B]"
                    data-testid="login-otp-back"
                  >
                    <ArrowLeft size={14} /> Back
                  </button>
                  {challenge.challenge === 'email_otp' && (
                    <button
                      type="button"
                      onClick={handleResend}
                      disabled={cooldown > 0 || resending}
                      className="inline-flex items-center gap-1 text-amber-700 hover:text-amber-800 disabled:opacity-50 disabled:cursor-not-allowed"
                      data-testid="login-otp-resend"
                    >
                      <ArrowsClockwise size={14} />
                      {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
                    </button>
                  )}
                </div>
              </motion.form>
            )}
          </AnimatePresence>

          <p className="text-center text-xs text-[#71717A] mt-6">
            BIBI Cars CRM · Production mode
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
