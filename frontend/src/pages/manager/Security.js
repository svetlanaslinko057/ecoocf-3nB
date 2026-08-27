import React, { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, Smartphone, QrCode, Loader2, KeyRound, Lock } from "lucide-react";
import { AccountAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, TableSkeleton } from "@/components/portal/PortalUI";
import { SectionCard, StatusPill } from "@/components/manager/ManagerUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

export default function Security() {
  useSeo("Безпека · 2FA", "Двофакторна автентифікація Google Authenticator.");
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [setup, setSetup] = useState(null);   // {secret, qrCode, ...}
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);
  const [disableCode, setDisableCode] = useState("");

  const load = () => {
    setLoading(true);
    AccountAPI.twofaStatus().then(setStatus).catch(() => toast.error("Не вдалося завантажити статус")).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const startSetup = async () => {
    setBusy(true);
    try { const s = await AccountAPI.twofaSetup(); setSetup(s); setCode(""); }
    catch { toast.error("Не вдалося розпочати налаштування"); }
    finally { setBusy(false); }
  };

  const verify = async () => {
    if (code.length < 6) return toast.error("Введіть 6-значний код");
    setBusy(true);
    try {
      await AccountAPI.twofaVerify(code);
      toast.success("2FA увімкнено — наступний вхід вимагатиме код");
      setSetup(null); setCode(""); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Невірний код"); }
    finally { setBusy(false); }
  };

  const disable = async () => {
    setBusy(true);
    try {
      await AccountAPI.twofaDisable(disableCode);
      toast.success("2FA вимкнено");
      setDisableOpen(false); setDisableCode(""); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Невірний код"); }
    finally { setBusy(false); }
  };

  const enabled = status?.enabled;

  return (
    <div data-testid="security-page">
      <PageHeader title="Безпека акаунта" subtitle="Двофакторна автентифікація (Google Authenticator)" />

      {loading ? <TableSkeleton rows={3} /> : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Status card */}
          <SectionCard className="lg:col-span-1" testid="twofa-status-card">
            <div className="flex flex-col items-center text-center">
              <span className={`flex h-16 w-16 items-center justify-center rounded-2xl ${enabled ? "bg-[#ECFDF5] text-[#0E5E3A]" : "bg-[#FFFBEB] text-[#B45309]"}`}>
                {enabled ? <ShieldCheck className="h-8 w-8" /> : <ShieldAlert className="h-8 w-8" />}
              </span>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">Двофакторна автентифікація</h3>
              <div className="mt-2">
                {enabled
                  ? <StatusPill tone="pos" testid="twofa-enabled-badge">Увімкнено</StatusPill>
                  : <StatusPill tone="warn" testid="twofa-disabled-badge">Вимкнено</StatusPill>}
              </div>
              <p className="mt-3 text-sm text-slate-500">{user?.email}</p>
              <p className="mt-1 text-xs text-slate-400">
                {enabled ? "При вході потрібен код із застосунку." : "Захистіть кабінет одноразовим кодом."}
              </p>
              {enabled ? (
                <Button variant="outline" className="mt-5 w-full" onClick={() => setDisableOpen(true)} data-testid="twofa-disable-button">
                  <Lock className="mr-2 h-4 w-4" /> Вимкнути 2FA
                </Button>
              ) : (
                <Button className="mt-5 w-full" onClick={startSetup} disabled={busy} data-testid="twofa-enable-button">
                  {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />} Увімкнути 2FA
                </Button>
              )}
            </div>
          </SectionCard>

          {/* Setup / Info card */}
          <SectionCard className="lg:col-span-2" title={setup ? "Налаштування Google Authenticator" : "Як це працює"} testid="twofa-setup-card">
            {!setup ? (
              <ol className="space-y-4">
                {[
                  ["Встановіть застосунок", "Google Authenticator, Microsoft Authenticator або Authy на телефон."],
                  ["Відскануйте QR-код", "Натисніть «Увімкнути 2FA» — зʼявиться QR-код для сканування."],
                  ["Вводьте код при вході", "Після пароля система запитає 6-значний код із застосунку."],
                ].map(([t, d], i) => (
                  <li key={i} className="flex gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0E5E3A] text-sm font-semibold text-[#5BC47A]">{i + 1}</span>
                    <div><div className="text-sm font-medium text-slate-800">{t}</div><div className="text-sm text-slate-500">{d}</div></div>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2">
                <div className="flex flex-col items-center">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <img src={setup.qrCode} alt="QR" className="h-44 w-44" data-testid="twofa-qr" />
                  </div>
                  <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-400"><QrCode className="h-3.5 w-3.5" /> Скануйте у застосунку</div>
                  <div className="mt-3 w-full rounded-lg bg-slate-50 p-2 text-center">
                    <div className="text-[10px] uppercase tracking-wide text-slate-400">Ключ вручну</div>
                    <code className="break-all text-xs font-medium text-slate-700">{setup.secret}</code>
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-700"><Smartphone className="h-4 w-4" /> Підтвердьте код</div>
                  <p className="mt-1 text-sm text-slate-500">Введіть 6-значний код, який показує застосунок.</p>
                  <div className="relative mt-4">
                    <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <Input
                      inputMode="numeric" maxLength={6} value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                      placeholder="000000" className="pl-9 text-center text-lg font-semibold tracking-[0.4em]"
                      data-testid="twofa-verify-input"
                    />
                  </div>
                  <Button className="mt-4 w-full" onClick={verify} disabled={busy || code.length < 6} data-testid="twofa-verify-button">
                    {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />} Підтвердити та увімкнути
                  </Button>
                  <Button variant="ghost" className="mt-2 w-full" onClick={() => { setSetup(null); setCode(""); }}>Скасувати</Button>
                </div>
              </div>
            )}
          </SectionCard>
        </div>
      )}

      <Dialog open={disableOpen} onOpenChange={setDisableOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Вимкнути 2FA</DialogTitle>
            <DialogDescription>Введіть поточний код із Google Authenticator, щоб підтвердити.</DialogDescription>
          </DialogHeader>
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input inputMode="numeric" maxLength={6} value={disableCode} onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" className="pl-9 text-center tracking-[0.4em]" data-testid="twofa-disable-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDisableOpen(false)}>Скасувати</Button>
            <Button onClick={disable} disabled={busy || disableCode.length < 6} className="bg-[#B91C1C] hover:bg-[#991B1B]" data-testid="twofa-disable-confirm">Вимкнути</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
