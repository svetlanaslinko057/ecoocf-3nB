import React, { useEffect, useState, useCallback } from "react";
import { KeyRound, ShieldCheck, CheckCircle2, AlertTriangle, Globe, Copy, Save, Mail, Send, Inbox } from "lucide-react";
import { SettingsAPI, IntegrationsAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/sonner";
import BillingRequisites from "@/components/admin/BillingRequisites";

export default function Settings() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Deep-link: /app/settings?section=requisites → scroll to & highlight the
  // IBAN requisites block (used by the "Налаштувати реквізити" CTA shown when
  // an IBAN invoice cannot be issued because requisites are missing).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("section") === "requisites") {
      const t = setTimeout(() => {
        const el = document.getElementById("requisites");
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
          el.style.boxShadow = "0 0 0 3px rgba(91,196,122,0.55)";
          setTimeout(() => { el.style.boxShadow = ""; }, 2600);
        }
      }, 400);
      return () => clearTimeout(t);
    }
  }, []);
  const [clientId, setClientId] = useState("");
  const [allowedDomains, setAllowedDomains] = useState("");
  const [googleEnabled, setGoogleEnabled] = useState(true);
  const [resolved, setResolved] = useState({});

  // ── Email / Resend ──
  const [resendKey, setResendKey] = useState("");
  const [resendKeyMasked, setResendKeyMasked] = useState(false); // a stored key exists
  const [resendFrom, setResendFrom] = useState("");
  const [resendReplyTo, setResendReplyTo] = useState("");
  const [resendEnabled, setResendEnabled] = useState(false);
  const [notifyEmail, setNotifyEmail] = useState("");
  const [savingEmail, setSavingEmail] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, integrations] = await Promise.all([
        SettingsAPI.getAuth(),
        IntegrationsAPI.list().catch(() => []),
      ]);
      const g = d.google || {};
      setClientId(g.clientId || "");
      setAllowedDomains(Array.isArray(g.allowedDomains) ? g.allowedDomains.join(", ") : (g.allowedDomains || ""));
      setGoogleEnabled(d.features?.googleEnabled !== false);
      setResolved(d._resolved || {});
      setNotifyEmail((d.notifications || {}).notifyEmail || "");
      // Resend
      const resend = (Array.isArray(integrations) ? integrations : []).find((i) => i.provider === "resend") || {};
      const creds = resend.credentials || {};
      const masked = typeof creds.apiKey === "string" && creds.apiKey.startsWith("…");
      setResendKeyMasked(masked || (!!creds.apiKey && !creds.apiKey.includes("@")));
      setResendKey(masked ? "" : (creds.apiKey || ""));
      setResendFrom(creds.from || (resend.settings || {}).from || "");
      setResendReplyTo(creds.replyTo || (resend.settings || {}).replyTo || "");
      setResendEnabled(!!resend.isEnabled);
    } catch (e) {
      if (e?.response?.status === 403) toast.error("Доступ лише для адміністратора");
      else toast.error("Не вдалося завантажити налаштування");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const domains = allowedDomains
        .split(/[,\n]/)
        .map((d) => d.trim().replace(/^@/, "").toLowerCase())
        .filter(Boolean);
      await SettingsAPI.patchAuth({
        google: { clientId: clientId.trim(), allowedDomains: domains },
        features: { googleEnabled },
      });
      toast.success("Налаштування збережено");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти");
    } finally {
      setSaving(false);
    }
  };

  const saveEmail = async () => {
    setSavingEmail(true);
    try {
      // If the field is empty AND a stored key exists, keep the stored one (send masked sentinel).
      const credentials = { from: resendFrom.trim(), replyTo: resendReplyTo.trim() };
      if (resendKey.trim()) credentials.apiKey = resendKey.trim();
      else if (resendKeyMasked) credentials.apiKey = "…keep"; // backend preserves stored secret on "…" prefix
      await IntegrationsAPI.patch("resend", {
        credentials,
        settings: { from: resendFrom.trim(), replyTo: resendReplyTo.trim() },
        isEnabled: resendEnabled,
        mode: resendEnabled ? "live" : "disabled",
      });
      await SettingsAPI.patchAuth({ notifications: { notifyEmail: notifyEmail.trim() } });
      toast.success("Налаштування email збережено");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти email-налаштування");
    } finally {
      setSavingEmail(false);
    }
  };

  const sendTest = async () => {
    if (!testTo.trim()) return toast.error("Вкажіть email для тесту");
    setTesting(true);
    try {
      const r = await IntegrationsAPI.test("resend", { to: testTo.trim() });
      if (r.success) toast.success(r.message || "Тестовий лист надіслано");
      else toast.warning(r.message || "Resend ще не активний (режим попереднього перегляду)");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Помилка тесту");
    } finally {
      setTesting(false);
    }
  };

  const copyOrigin = () => {
    try { navigator.clipboard.writeText(origin); toast.success("Скопійовано"); } catch { /* noop */ }
  };

  if (user && user.role !== "admin") {
    return (
      <div data-testid="settings-page">
        <PageHeader title="Налаштування" subtitle="Системні налаштування платформи" testid="settings-header" />
        <EmptyState icon={ShieldCheck} title="Доступ обмежено" hint="Розділ налаштувань доступний лише адміністратору." />
      </div>
    );
  }

  const effectiveOk = !!resolved.googleClientId;
  const emailLive = resendEnabled && (resendKeyMasked || resendKey.trim());

  return (
    <div className="max-w-5xl mx-auto" data-testid="settings-page">
      <PageHeader
        title="Налаштування"
        subtitle="Авторизація клієнтів та email-сповіщення (Resend)"
        testid="settings-header"
        actions={<Button onClick={save} disabled={saving || loading} data-testid="settings-save"><Save className="mr-2 h-4 w-4" />{saving ? "Збереження…" : "Зберегти Google"}</Button>}
      />

      {/* Effective status banner */}
      <div className="mb-5 flex items-center gap-3 rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-4 shadow-[0_1px_3px_rgba(11,26,20,0.06)]" data-testid="settings-effective">
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${effectiveOk ? "bg-[#ECFDF5] text-[#065F46]" : "bg-[#FFFBEB] text-[#92400E]"}`}>
          {effectiveOk ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Google Sign-In: {effectiveOk ? "налаштовано" : "не налаштовано"}
          </div>
          <div className="truncate text-xs text-slate-500">
            {effectiveOk ? `Активний Client ID: ${resolved.googleClientId}` : "Вкажіть Client ID нижче, щоб увімкнути вхід клієнтів через Google."}
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Google config card */}
        <div className="lg:col-span-2 rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-6 shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0E5E3A] text-[#5BC47A]"><KeyRound className="h-5 w-5" /></span>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Google OAuth Client ID</h2>
              <p className="text-xs text-slate-500">Класична авторизація Google Identity Services (без секрету, без Emergent).</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-1.5">
              <Label>Client ID</Label>
              <Input
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="123456789-xxxx.apps.googleusercontent.com"
                data-testid="settings-clientId"
              />
              <p className="text-xs text-slate-400">Береться з Google Cloud Console → Credentials → OAuth 2.0 Client ID.</p>
            </div>

            <div className="grid gap-1.5">
              <Label>Дозволені домени (необов'язково)</Label>
              <Input
                value={allowedDomains}
                onChange={(e) => setAllowedDomains(e.target.value)}
                placeholder="hospital.ua, clinic.com"
                data-testid="settings-allowedDomains"
              />
              <p className="text-xs text-slate-400">Через кому. Порожньо = будь-який підтверджений Google-акаунт.</p>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[#FAFCFA] px-4 py-3">
              <div>
                <div className="text-sm font-medium text-slate-800">Увімкнути Google-вхід</div>
                <div className="text-xs text-slate-500">Якщо вимкнено — кнопка Google ховається на сторінці входу клієнта.</div>
              </div>
              <Switch checked={googleEnabled} onCheckedChange={setGoogleEnabled} data-testid="settings-googleEnabled" />
            </div>
          </div>
        </div>

        {/* Origins helper card */}
        <div className="rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-6 shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[hsl(var(--accent))] text-[#0E5E3A]"><Globe className="h-5 w-5" /></span>
            <h2 className="text-base font-semibold text-slate-900">Authorized origin</h2>
          </div>
          <p className="text-sm text-slate-500">Додайте цей домен у Google Cloud Console → OAuth Client → «Authorized JavaScript origins»:</p>
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-[hsl(var(--border))] bg-[#FAFCFA] px-3 py-2">
            <code className="min-w-0 flex-1 truncate text-xs text-slate-700">{origin}</code>
            <button type="button" onClick={copyOrigin} className="shrink-0 text-slate-400 hover:text-slate-700" aria-label="Копіювати"><Copy className="h-4 w-4" /></button>
          </div>
          <p className="mt-3 text-xs text-slate-400">Без цього кроку Google-попап не ініціалізується (помилка origin).</p>
        </div>
      </div>

      {/* ── Email / Resend ─────────────────────────────────────────── */}
      <div className="mt-6 flex items-center gap-3 rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-4 shadow-[0_1px_3px_rgba(11,26,20,0.06)]" data-testid="email-status">
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${emailLive ? "bg-[#ECFDF5] text-[#065F46]" : "bg-[#FFFBEB] text-[#92400E]"}`}>
          {emailLive ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Email (Resend): {emailLive ? "активний" : "режим попереднього перегляду (dry-run)"}
          </div>
          <div className="truncate text-xs text-slate-500">
            {emailLive
              ? "Листи підтвердження, відновлення паролю та сповіщення надсилаються через Resend."
              : "Без API-ключа коди підтвердження показуються на екрані. Ключ додається після підключення реального домену."}
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Resend config card */}
        <div className="lg:col-span-2 rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-6 shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0E5E3A] text-[#5BC47A]"><Mail className="h-5 w-5" /></span>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Resend — транзакційна пошта</h2>
              <p className="text-xs text-slate-500">Верифікація email, відновлення паролю та сповіщення менеджерам.</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-1.5">
              <Label>Resend API Key</Label>
              <Input
                type="password"
                value={resendKey}
                onChange={(e) => setResendKey(e.target.value)}
                placeholder={resendKeyMasked ? "•••••••• (збережено — залиште порожнім, щоб не змінювати)" : "re_xxxxxxxxxxxxxxxx"}
                data-testid="settings-resendKey"
              />
              <p className="text-xs text-slate-400">resend.com → API Keys. Ключ зберігається в зашифрованому вигляді й маскується.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label>From (відправник)</Label>
                <Input value={resendFrom} onChange={(e) => setResendFrom(e.target.value)} placeholder="no-reply@eco-utyl.ua" data-testid="settings-resendFrom" />
              </div>
              <div className="grid gap-1.5">
                <Label>Reply-To (необов'язково)</Label>
                <Input value={resendReplyTo} onChange={(e) => setResendReplyTo(e.target.value)} placeholder="support@eco-utyl.ua" data-testid="settings-resendReplyTo" />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[#FAFCFA] px-4 py-3">
              <div>
                <div className="text-sm font-medium text-slate-800">Увімкнути надсилання через Resend</div>
                <div className="text-xs text-slate-500">Вимкнено — система працює в dry-run (коди на екрані).</div>
              </div>
              <Switch checked={resendEnabled} onCheckedChange={setResendEnabled} data-testid="settings-resendEnabled" />
            </div>

            <div className="flex flex-wrap items-end gap-3 border-t border-[hsl(var(--border))] pt-4">
              <div className="grid flex-1 gap-1.5 min-w-[200px]">
                <Label>Перевірка доставки</Label>
                <Input value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="ваш@email.ua" data-testid="settings-testTo" />
              </div>
              <Button variant="secondary" onClick={sendTest} disabled={testing} data-testid="settings-test-email">
                <Send className="mr-2 h-4 w-4" />{testing ? "Надсилання…" : "Надіслати тест"}
              </Button>
              <Button onClick={saveEmail} disabled={savingEmail || loading} data-testid="settings-save-email">
                <Save className="mr-2 h-4 w-4" />{savingEmail ? "Збереження…" : "Зберегти Email"}
              </Button>
            </div>
          </div>
        </div>

        {/* Notify mailbox card */}
        <div className="rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-6 shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[hsl(var(--accent))] text-[#0E5E3A]"><Inbox className="h-5 w-5" /></span>
            <h2 className="text-base font-semibold text-slate-900">Пошта для сповіщень</h2>
          </div>
          <p className="text-sm text-slate-500">Скринька, що отримує листи про нові заявки та звернення клієнтів.</p>
          <div className="mt-3 grid gap-1.5">
            <Label>Email для сповіщень</Label>
            <Input value={notifyEmail} onChange={(e) => setNotifyEmail(e.target.value)} placeholder="office@eco-utyl.ua" data-testid="settings-notifyEmail" />
          </div>
          <p className="mt-3 text-xs text-slate-400">Зберігається кнопкою «Зберегти Email». Надсилання активне лише при увімкненому Resend.</p>
        </div>
      </div>

      {/* Реквізити для оплати (IBAN) */}
      <div className="mt-8 scroll-mt-24 rounded-2xl transition-shadow duration-500" id="requisites" data-testid="settings-requisites-section">
        <div className="mb-4 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[hsl(var(--accent))] text-[#0E5E3A]"><KeyRound className="h-5 w-5" /></span>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Реквізити для оплати (IBAN)</h2>
            <p className="text-sm text-slate-500">Юридична особа та банківські рахунки за валютою. Використовуються при виставленні рахунків клієнтам.</p>
          </div>
        </div>
        <BillingRequisites />
      </div>
    </div>
  );
}
