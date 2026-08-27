import React, { useState } from "react";
import { useNavigate, Navigate, Link } from "react-router-dom";
import { Leaf, Loader2, LogIn, ArrowLeft, ShieldCheck, KeyRound } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

const roleHome = (role) => (String(role || "").toLowerCase() === "manager" ? "/app/cabinet" : "/app");

export default function Login() {
  useSeo("Вхід у кабінет", "Робочий кабінет оператора утилізації небезпечних відходів.");
  const { login, verify2fa, user, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // 2FA step
  const [challenge, setChallenge] = useState(null); // {user_id, user_email}
  const [code, setCode] = useState("");

  if (!loading && user) return <Navigate to={roleHome(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setSubmitting(true);
    try {
      const res = await login(email.trim(), password);
      if (res && res.challenge === "totp") {
        setChallenge({ user_id: res.user_id, user_email: res.user_email });
      } else {
        navigate(roleHome(res && res.role));
      }
    } catch {
      setErr("Невірний email або пароль. Спробуйте ще раз.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setErr(""); setSubmitting(true);
    try {
      const u = await verify2fa(challenge.user_id, code.trim());
      navigate(roleHome(u && u.role));
    } catch {
      setErr("Невірний код підтвердження. Спробуйте ще раз.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[hsl(var(--background))] px-4 py-12">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: "radial-gradient(900px 420px at 15% 10%, rgba(132,204,22,0.14), transparent 55%), radial-gradient(900px 420px at 85% 0%, rgba(5,150,105,0.12), transparent 55%)" }}
      />
      <div className="relative w-full max-w-md">
        <Link to="/" className="mb-6 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-[hsl(var(--primary))]" data-testid="login-back-link">
          <ArrowLeft className="h-4 w-4" /> На головну
        </Link>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-8 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[hsl(var(--primary))] text-white"><Leaf className="h-5 w-5" /></span>
            <span className="text-xl font-bold tracking-tight text-[hsl(var(--primary))]">ECO<span className="text-[#5BC47A]">.</span><span className="opacity-60">NOVA</span></span>
          </div>

          {!challenge ? (
            <>
              <h1 className="mt-6 text-2xl font-semibold tracking-tight text-slate-900">Вхід у кабінет</h1>
              <p className="mt-1 text-sm text-slate-500">Робочий простір оператора утилізації.</p>
              <form className="mt-6 space-y-4" onSubmit={submit}>
                {err && (<Alert variant="destructive" data-testid="login-error"><AlertDescription>{err}</AlertDescription></Alert>)}
                <div className="grid gap-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.ua" required data-testid="login-email-input" />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="password">Пароль</Label>
                  <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required data-testid="login-password-input" />
                </div>
                <Button type="submit" className="w-full gap-2" size="lg" disabled={submitting} data-testid="login-submit-button">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                  {submitting ? "Вхід…" : "Увійти"}
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="mt-6 flex items-center gap-2 text-[hsl(var(--primary))]">
                <ShieldCheck className="h-5 w-5" />
                <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Двофакторна перевірка</h1>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Відкрийте Google Authenticator і введіть 6-значний код для <span className="font-medium text-slate-700">{challenge.user_email}</span>.
              </p>
              <form className="mt-6 space-y-4" onSubmit={submitCode}>
                {err && (<Alert variant="destructive" data-testid="twofa-error"><AlertDescription>{err}</AlertDescription></Alert>)}
                <div className="grid gap-1.5">
                  <Label htmlFor="code">Код підтвердження</Label>
                  <div className="relative">
                    <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <Input
                      id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                      value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                      placeholder="000000" required autoFocus
                      className="pl-9 tracking-[0.5em] text-center text-lg font-semibold"
                      data-testid="twofa-code-input"
                    />
                  </div>
                </div>
                <Button type="submit" className="w-full gap-2" size="lg" disabled={submitting || code.length < 6} data-testid="twofa-submit-button">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                  {submitting ? "Перевірка…" : "Підтвердити"}
                </Button>
                <button type="button" onClick={() => { setChallenge(null); setCode(""); setErr(""); }} className="w-full text-center text-sm text-slate-400 hover:text-slate-600" data-testid="twofa-back">
                  ← Інший акаунт
                </button>
              </form>
            </>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-slate-400">Доступ для співробітників та партнерів ECO.NOVA.</p>
      </div>
    </div>
  );
}
