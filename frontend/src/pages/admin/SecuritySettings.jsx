import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShieldCheck, LockKey, CheckCircle, XCircle, Eye, EyeSlash, Copy, ArrowClockwise } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function SecuritySettings() {
  const { t } = useLang();
  const [twoFAEnabled, setTwoFAEnabled] = useState(false);
  const [setupData, setSetupData] = useState(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [setupLoading, setSetupLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [step, setStep] = useState('check');

  useEffect(() => { checkStatus(); }, []);

  const checkStatus = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/admin/security/2fa/status`);
      setTwoFAEnabled(res.data.enabled);
      setStep(res.data.enabled ? 'done' : 'check');
    } catch (err) {
      console.error('Failed to check 2FA status:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSetup2FA = async () => {
    setSetupLoading(true);
    try {
      const res = await axios.post(`${API_URL}/api/admin/security/2fa/setup`);
      setSetupData(res.data);
      setStep('setup');
    } catch (err) {
      toast.error(t('adm_error_setting_up_2fa'));
    } finally {
      setSetupLoading(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      toast.error(t('adm_enter_6digit_code'));
      return;
    }
    setSetupLoading(true);
    try {
      await axios.post(`${API_URL}/api/admin/security/2fa/verify`, { token: verifyCode });
      setTwoFAEnabled(true);
      setStep('done');
      toast.success(t('adm_2fa_enabled'));
    } catch (err) {
      toast.error(t('adm_invalid_code'));
    } finally {
      setSetupLoading(false);
    }
  };

  const handleDisable2FA = async () => {
    if (!confirm('Disable 2FA? This will lower account security.')) return;
    setSetupLoading(true);
    try {
      await axios.post(`${API_URL}/api/admin/security/2fa/disable`);
      setTwoFAEnabled(false);
      setStep('check');
      setSetupData(null);
      toast.success(t('adm_2fa_disabled'));
    } catch (err) {
      toast.error(t('adm_error_disabling_2fa'));
    } finally {
      setSetupLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(t('copiedToast'));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-zinc-900 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6" data-testid="security-settings">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <ShieldCheck size={20} weight="bold" />
        </div>
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-[#18181B] leading-tight">{t('security')}</h1>
          <p className="text-[12px] text-[#71717A] mt-0.5">{t('settings')}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 p-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className={`p-4 rounded-2xl ${twoFAEnabled ? 'bg-emerald-100' : 'bg-amber-100'}`}>
              <LockKey size={32} className={twoFAEnabled ? 'text-emerald-600' : 'text-amber-600'} weight="fill" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900">{t('twoFactorAuthentication')}</h2>
              <p className="text-zinc-500">{twoFAEnabled ? t('yourAccountIsProtected') : t('addExtraSecurityLayer')}</p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${twoFAEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            {twoFAEnabled ? t('enabledStatus') : t('disabledStatus')}
          </span>
        </div>

        {step === 'check' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-blue-50 border border-blue-100">
              <h3 className="font-medium text-blue-900 mb-2">{t('howItWorks')}</h3>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>{t('installGoogleAuthenticator')}</li>
                <li>{t('scanQrToAddAccount')}</li>
                <li>{t('enter2faCodeEachLogin')}</li>
              </ul>
            </div>
            <button onClick={handleSetup2FA} disabled={setupLoading} className="w-full py-3 rounded-xl bg-zinc-900 text-white font-medium hover:bg-zinc-800 disabled:opacity-50" data-testid="setup-2fa-btn">
              {setupLoading ? <ArrowClockwise size={20} className="inline animate-spin mr-2" /> : <ShieldCheck size={20} className="inline mr-2" />}
              {t('setup2FA')}
            </button>
          </div>
        )}

        {step === 'setup' && setupData && (
          <div className="space-y-6">
            <div className="flex flex-col items-center p-6 bg-zinc-50 rounded-xl">
              <p className="text-sm text-zinc-500 mb-4">{t('scanQrInAuthenticator')}</p>
              <div className="p-4 bg-white rounded-xl border border-zinc-200">
                <img src={setupData.qrCode} alt={t('adm_2fa_qr_code')} className="w-48 h-48" data-testid="qr-code-img" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-amber-50 border border-amber-100">
              <p className="text-sm text-amber-800 mb-2">{t('orEnterManuallyColon')}</p>
              <div className="flex items-center gap-2">
                <code className={`flex-1 px-3 py-2 rounded-lg bg-white border border-amber-200 font-mono text-sm ${showSecret ? '' : 'filter blur-sm'}`}>
                  {setupData.secret}
                </code>
                <button onClick={() => setShowSecret(!showSecret)} className="p-2 rounded-lg border border-amber-200 text-amber-700 hover:bg-amber-100">
                  {showSecret ? <EyeSlash size={20} /> : <Eye size={20} />}
                </button>
                <button onClick={() => copyToClipboard(setupData.secret)} className="p-2 rounded-lg border border-amber-200 text-amber-700 hover:bg-amber-100">
                  <Copy size={20} />
                </button>
              </div>
              <p className="text-xs text-amber-600 mt-2">{t('saveCodeSecurelyRecovery')}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-2">{t('enter6DigitCode')}</label>
              <input type="text" value={verifyCode} onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000000" className="w-full px-4 py-3 rounded-xl border border-zinc-200 text-center text-2xl font-mono tracking-widest focus:border-zinc-400 outline-none" maxLength={6} data-testid="verify-code-input" />
            </div>

            <div className="flex gap-3">
              <button onClick={() => setStep('check')} className="flex-1 py-3 rounded-xl border border-zinc-200 text-zinc-700 font-medium hover:bg-zinc-50">{t('cancelAction')}</button>
              <button onClick={handleVerify2FA} disabled={verifyCode.length !== 6 || setupLoading} className="flex-1 py-3 rounded-xl bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50" data-testid="verify-2fa-btn">
                {setupLoading ? <ArrowClockwise size={20} className="inline animate-spin mr-2" /> : <CheckCircle size={20} className="inline mr-2" />}
                {t('verify2FA')}
              </button>
            </div>
          </div>
        )}

        {step === 'done' && twoFAEnabled && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100 flex items-start gap-3">
              <CheckCircle size={24} className="text-emerald-600 flex-shrink-0" weight="fill" />
              <div>
                <h3 className="font-medium text-emerald-900">{t('twoFAActive')}</h3>
                <p className="text-sm text-emerald-700">{t('accountProtectedCodeRequired')}</p>
              </div>
            </div>
            <button onClick={handleDisable2FA} disabled={setupLoading} className="w-full py-3 rounded-xl border border-red-200 text-red-600 font-medium hover:bg-red-50 disabled:opacity-50" data-testid="disable-2fa-btn">
              <XCircle size={20} className="inline mr-2" />
              {t('disable2FA')}
            </button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 p-6">
        <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
          <ShieldCheck size={20} /> {t('securityTipsTitle')}
        </h2>
        <ul className="space-y-3 text-sm text-zinc-600">
          <li className="flex items-start gap-2"><CheckCircle size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />{t('useUniqueComplexPassword')}</li>
          <li className="flex items-start gap-2"><CheckCircle size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />{t('neverShare2FACodes')}</li>
          <li className="flex items-start gap-2"><CheckCircle size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />{t('storeBackupCodeSecurely')}</li>
          <li className="flex items-start gap-2"><CheckCircle size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />{t('reviewActiveSessionsRegularly')}</li>
        </ul>
      </div>
    </div>
  );
}
