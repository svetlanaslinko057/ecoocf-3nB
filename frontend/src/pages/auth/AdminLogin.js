/**
 * AdminLogin — dedicated admin/staff entrance at /admin (separate from /login).
 *
 * Visual differentiation: dark panel (security/control room feel) vs the public
 * /login (light cabinet). Same /api/auth/login endpoint underneath, but routes
 * the user through a screen optimized for staff awareness (warning banner,
 * role hint, no «На головну» public link in primary position).
 */
import React, { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { ShieldCheck, Loader2, LogIn, AlertTriangle, KeyRound, Lock, Mail, EyeOff, Eye } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";

// Where each role lands after a successful /admin login:
//   • manager → personal manager cabinet
//   • admin (and any other staff) → operations console dashboard
const roleHome = (role) => (String(role || "").toLowerCase() === "manager" ? "/app/cabinet" : "/app");

export default function AdminLogin() {
  useSeo("Адмін-панель · ECO.NOVA", "Робочий вхід для співробітників: оператори, менеджери, адміністратори.");
  const { login, verify2fa, user, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // 2FA (TOTP) second-factor step — handled inline so /admin is fully self-contained.
  const [challenge, setChallenge] = useState(null); // { user_id, user_email }
  const [code, setCode] = useState("");

  if (!loading && user) return <Navigate to={roleHome(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setSubmitting(true);
    try {
      const u = await login(email.trim(), password.trim());
      if (u && u.challenge === "totp") {
        setChallenge({ user_id: u.user_id, user_email: u.user_email });
        return;
      }
      navigate(roleHome(u && u.role));
    } catch {
      setErr("Невірні облікові дані. Перевірте email та пароль або зверніться до адміністратора.");
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
    <div
      className="relative min-h-screen overflow-hidden"
      style={{ background: "linear-gradient(135deg, #0B1A14 0%, #0E2B1E 100%)", color: "rgba(255,255,255,0.9)" }}
      data-testid="admin-login-page"
    >
      {/* Ambient glows */}
      <div className="pointer-events-none absolute inset-0">
        <div aria-hidden="true" className="absolute -top-40 right-[-200px] h-[520px] w-[520px] rounded-full" style={{ background: "radial-gradient(closest-side, rgba(91, 196, 122,0.10), transparent 70%)" }} />
        <div aria-hidden="true" className="absolute -bottom-40 left-[-200px] h-[460px] w-[460px] rounded-full" style={{ background: "radial-gradient(closest-side, rgba(14,94,58,0.30), transparent 70%)" }} />
      </div>
      {/* Top hairline */}
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(91, 196, 122,0.32) 30%, rgba(91, 196, 122,0.32) 70%, transparent)" }} />
      {/* Mono grid background pattern */}
      <div aria-hidden="true" className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: "linear-gradient(rgba(91, 196, 122,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(91, 196, 122,0.5) 1px, transparent 1px)", backgroundSize: "44px 44px" }} />

      <div className="relative grid min-h-screen grid-cols-1 lg:grid-cols-2">
        {/* LEFT — branding / info */}
        <div className="hidden flex-col justify-between p-12 lg:flex">
          <div>
            <div className="inline-flex items-center gap-3" data-testid="admin-brand">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl" style={{ background: "linear-gradient(135deg, #0E5E3A 0%, #0F8A4D 100%)", boxShadow: "0 12px 28px -10px rgba(91, 196, 122,0.30)" }}>
                <ShieldCheck className="h-6 w-6 text-white" />
              </span>
              <div className="leading-none">
                <div className="text-[24px] font-extrabold tracking-tight text-white" style={{ fontFamily: "Mazzard, Inter, system-ui, sans-serif" }}>
                  ECO<span style={{ color: "#5BC47A" }}>.</span><span className="text-white/55">NOVA</span> <span className="ml-1 text-white/40 text-[14px] font-bold uppercase tracking-[0.22em] align-middle">Admin</span>
                </div>
                <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.26em] text-white/40">Internal Operations Console</div>
              </div>
            </div>

            <div className="mt-16 max-w-md">
              <div className="inline-flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.22em] text-[#5BC47A]">
                <span className="inline-block h-px w-8 bg-[#5BC47A]" /> Доступ обмежено
              </div>
              <h1 className="mt-5 font-extrabold uppercase tracking-[-0.02em] text-white" style={{ fontFamily: "Mazzard, Inter, system-ui, sans-serif", fontSize: "clamp(28px, 2.8vw, 44px)", lineHeight: 1.08 }}>
                Робоча консоль <span className="text-[#5BC47A]">оператора</span>
              </h1>
              <p className="mt-6 max-w-[44ch] text-[15px] leading-[1.7] text-white/55">
                Цей вхід — лише для співробітників ECO.NOVA Utilization Platform: операторів,
                менеджерів та адміністраторів. Усі дії логуються та можуть
                переглядатись керівництвом.
              </p>

              <ul className="mt-8 space-y-3 text-[13px] text-white/65">
                <li className="flex items-center gap-3"><span className="h-1.5 w-1.5 rounded-full bg-[#5BC47A]" /> CRM: заявки, договори, акти, рахунки</li>
                <li className="flex items-center gap-3"><span className="h-1.5 w-1.5 rounded-full bg-[#5BC47A]" /> Каталог 80+ кодів відходів, ціноутворення</li>
                <li className="flex items-center gap-3"><span className="h-1.5 w-1.5 rounded-full bg-[#5BC47A]" /> Файли, генерація PDF, архів актів</li>
                <li className="flex items-center gap-3"><span className="h-1.5 w-1.5 rounded-full bg-[#5BC47A]" /> Завдання, дзвінки, документи команди</li>
              </ul>
            </div>
          </div>

          <div className="text-[11px] text-white/35">
            © {new Date().getFullYear()} ECO.NOVA Utilization Platform · Internal Use Only
          </div>
        </div>

        {/* RIGHT — form */}
        <div className="flex items-center justify-center px-6 py-12 lg:px-12">
          <div className="w-full max-w-md">
            {/* Mobile-only brand */}
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl" style={{ background: "linear-gradient(135deg, #0E5E3A 0%, #0F8A4D 100%)" }}>
                <ShieldCheck className="h-5 w-5 text-white" />
              </span>
              <div className="leading-none">
                <div className="text-[20px] font-extrabold tracking-tight text-white">ECO<span style={{ color: "#5BC47A" }}>.</span><span className="text-white/55">NOVA</span> Admin</div>
                <div className="mt-1 text-[9px] font-bold uppercase tracking-[0.26em] text-white/40">Internal Operations</div>
              </div>
            </div>

            <div className="rounded-[18px] border border-white/12 bg-white/[0.03] p-8 backdrop-blur-md" style={{ boxShadow: "0 30px 80px -40px rgba(0,0,0,0.5)" }}>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#5BC47A]/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#5BC47A]" style={{ background: "rgba(91, 196, 122,0.06)" }}>
                <Lock className="h-3 w-3" /> Захищений вхід
              </div>

              <h2 className="mt-5 text-[26px] font-extrabold tracking-tight text-white" style={{ fontFamily: "Mazzard, Inter, system-ui, sans-serif" }}>
                {challenge ? "Двофакторна перевірка" : "Вхід у CRM"}
              </h2>
              {challenge ? (
                <p className="mt-2 text-[13.5px] leading-[1.6] text-white/55">
                  Введіть 6-значний код з Google Authenticator для
                  <span className="ml-1 font-medium text-white/80">{challenge.user_email}</span>.
                </p>
              ) : (
                <p className="mt-2 text-[13.5px] leading-[1.6] text-white/55">
                  Введіть робочі облікові дані (адміністратор або менеджер). Якщо ви — клієнт компанії, перейдіть до
                  <a href="/client/login" className="ml-1 text-[#5BC47A] hover:underline" data-testid="admin-to-client-login">кабінету клієнта</a>.
                </p>
              )}

              {err && (
                <div className="mt-6 flex items-start gap-3 rounded-[10px] border border-red-400/30 bg-red-400/8 p-3.5 text-[13px] text-red-200" data-testid="admin-login-error">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-red-300" />
                  <span>{err}</span>
                </div>
              )}

              {challenge ? (
                <form onSubmit={submitCode} className="mt-7 space-y-5" data-testid="admin-2fa-form">
                  <div>
                    <label htmlFor="admin-2fa-code" className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/55">Код підтвердження</label>
                    <div className="relative mt-2">
                      <KeyRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/55" />
                      <input
                        id="admin-2fa-code"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={6}
                        required
                        autoFocus
                        value={code}
                        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                        placeholder="000000"
                        className="h-12 w-full rounded-[10px] border border-white/12 bg-white/[0.03] pl-11 pr-4 text-center text-[18px] font-semibold tracking-[0.5em] text-white placeholder:text-white/30 focus:border-[#5BC47A]/60 focus:outline-none focus:ring-2 focus:ring-[#5BC47A]/20"
                        data-testid="admin-2fa-code-input"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={submitting || code.length < 6}
                    className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-[10px] text-[12px] font-bold uppercase tracking-[0.16em] text-[#0B1410] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5BC47A]/40 disabled:opacity-60"
                    style={{ background: "#5BC47A", transition: "background-color 200ms ease-out, opacity 200ms ease-out" }}
                    data-testid="admin-2fa-submit"
                  >
                    {submitting ? (<><Loader2 className="h-4 w-4 animate-spin" /> Перевірка…</>) : (<><ShieldCheck className="h-4 w-4" /> Підтвердити</>)}
                  </button>
                  <button type="button" onClick={() => { setChallenge(null); setCode(""); setErr(""); }} className="w-full text-center text-[12px] text-white/40 hover:text-white/70" data-testid="admin-2fa-back">
                    ← Інший акаунт
                  </button>
                </form>
              ) : (
              <form onSubmit={submit} className="mt-7 space-y-5" data-testid="admin-login-form">
                <div>
                  <label htmlFor="admin-email" className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/55">Email</label>
                  <div className="relative mt-2">
                    <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/55" />
                    <input
                      id="admin-email"
                      type="email"
                      required
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="admin@eco.ua"
                      className="h-12 w-full rounded-[10px] border border-white/12 bg-white/[0.03] pl-11 pr-4 text-[14px] text-white placeholder:text-white/30 focus:border-[#5BC47A]/60 focus:outline-none focus:ring-2 focus:ring-[#5BC47A]/20"
                      style={{ transition: "border-color 200ms ease-out, box-shadow 200ms ease-out" }}
                      data-testid="admin-login-email"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="admin-password" className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/55">Пароль</label>
                  <div className="relative mt-2">
                    <KeyRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/55" />
                    <input
                      id="admin-password"
                      type={show ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="h-12 w-full rounded-[10px] border border-white/12 bg-white/[0.03] pl-11 pr-12 text-[14px] text-white placeholder:text-white/30 focus:border-[#5BC47A]/60 focus:outline-none focus:ring-2 focus:ring-[#5BC47A]/20"
                      style={{ transition: "border-color 200ms ease-out, box-shadow 200ms ease-out" }}
                      data-testid="admin-login-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShow((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex h-8 w-8 items-center justify-center rounded-md text-white/80 hover:bg-white/10 hover:text-[#5BC47A]"
                      style={{ transition: "color 180ms ease-out" }}
                      aria-label={show ? "Сховати пароль" : "Показати пароль"}
                      data-testid="admin-login-toggle-password"
                    >
                      {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-[10px] text-[12px] font-bold uppercase tracking-[0.16em] text-[#0B1410] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5BC47A]/40 disabled:opacity-60"
                  style={{ background: "#5BC47A", transition: "background-color 200ms ease-out, opacity 200ms ease-out" }}
                  data-testid="admin-login-submit"
                >
                  {submitting ? (<><Loader2 className="h-4 w-4 animate-spin" /> Перевіряємо…</>) : (<><LogIn className="h-4 w-4" /> Увійти в CRM</>)}
                </button>
              </form>
              )}

              <div className="mt-7 border-t border-white/10 pt-5 text-[11.5px] text-white/40">
                Усі дії в адмін-панелі логуються (audit log). Не передавайте облікові дані
                третім особам. У разі компрометації — негайно повідомте адміністратора.
              </div>
            </div>

            <div className="mt-6 text-center text-[11px] text-white/30">
              <a href="/" className="hover:text-white/60" style={{ transition: "color 180ms ease-out" }} data-testid="admin-login-home-link">← На публічний сайт</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
