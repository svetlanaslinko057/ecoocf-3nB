import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import { useClientAuth } from "@/context/ClientAuthContext";
import GoogleSignIn from "@/components/GoogleSignIn";
import PasswordField from "@/components/PasswordField";
import AuthAside from "@/components/AuthAside";
import CompanyAutocomplete from "@/components/CompanyAutocomplete";
import PhoneField from "@/components/PhoneField";
import LeafFall from "@/components/LeafFall";
import { passwordScore } from "@/lib/passwordUtils";
import { validatePhone, validateEmail } from "@/lib/validators";
import { useLang } from "@/i18n";
import "./client-auth.css";

const TXT = {
  uk: {
    errGoogle: "Не вдалося увійти через Google. Спробуйте ще раз.",
    errCredsReq: "Введіть email та пароль.",
    err2fa: "Для цього акаунта увімкнено двофакторну автентифікацію. Скористайтесь Google-входом або зверніться до менеджера.",
    errInvalid: "Невірний email або пароль.",
    errNameReq: "Вкажіть прізвище та ім'я.",
    errEmailReq: "Вкажіть email.",
    errPwWeak: "Пароль має містити щонайменше 8 символів і відповідати вимогам нижче.",
    errPwMismatch: "Паролі не співпадають.",
    errRegister: "Не вдалося створити акаунт. Можливо, email вже зареєстровано.",
    errOtpLen: "Введіть 6-значний код.",
    errOtpInvalid: "Невірний код. Спробуйте ще раз.",
    okResent: "Новий код надіслано.",
    errResend: "Не вдалося надіслати код. Спробуйте пізніше.",
    okForgot: "Якщо такий email існує — ми надіслали посилання для відновлення паролю.",
    errForgot: "Не вдалося надіслати посилання. Спробуйте пізніше.",
    hForgotEye: "Відновлення доступу", hForgotTitle: "Забули пароль?", hForgotSub: "Введіть email — ми надішлемо безпечне посилання для створення нового паролю.",
    hOtpEye: "Підтвердження", hOtpTitle: "Перевірте пошту", hOtpSub: (em) => `Ми надіслали 6-значний код на ${em}. Введіть його, щоб активувати акаунт.`,
    hRegEye: "Новий акаунт", hRegTitle: "Реєстрація клієнта", hRegSub: "Створіть кабінет, щоб керувати заявками, договорами й актами утилізації в одному місці.",
    hSignEye: "Кабінет клієнта", hSignTitle: "Вхід у кабінет", hSignSub: "Увійдіть, щоб бачити статуси заявок, повторювати замовлення та спілкуватися з вашим менеджером.",
    brandAria: "ECO.NOVA — на головну", tabsAria: "Вхід або реєстрація", tabSignin: "Вхід", tabRegister: "Реєстрація",
    orEmail: "або через email", password: "Пароль", forgotQ: "Забули пароль?", signIn: "Увійти",
    surname: "Прізвище", surnamePh: "Петренко", name: "Ім'я", namePh: "Олег",
    middle: "По батькові", optional: "(необов'язково)", middlePh: "Іванович",
    phone: "Телефон", phonePh: "+380 50 123 45 67", company: "Назва компанії", companyPh: "ТОВ «Клініка Здоров'я»",
    repeatPw: "Повторіть пароль", pwMismatch: "Паролі не співпадають", createAccount: "Створити акаунт",
    regConsent: "Реєструючись, ви погоджуєтесь з умовами надання послуг та обробкою даних.",
    step2: "Крок 2 з 2", devOtp1: "Режим попереднього перегляду (пошта не налаштована). Ваш код:",
    confirmLogin: "Підтвердити та увійти", resend: "Надіслати новий код", resendCd: (c) => `Надіслати новий код (${c}с)`,
    changeData: "← Змінити дані", devForgot: "Режим попереднього перегляду:", openResetLink: "відкрити посилання для відновлення →",
    sendLink: "Надіслати посилання", backToLogin: "← Повернутися до входу", toMainSite: "← На головний сайт",
    digit: (n) => `Цифра ${n}`,
  },
  en: {
    errGoogle: "Couldn't sign in with Google. Please try again.",
    errCredsReq: "Enter email and password.",
    err2fa: "Two-factor authentication is enabled for this account. Use Google sign-in or contact your manager.",
    errInvalid: "Invalid email or password.",
    errNameReq: "Enter your surname and first name.",
    errEmailReq: "Enter your email.",
    errPwWeak: "The password must be at least 8 characters and meet the requirements below.",
    errPwMismatch: "Passwords don't match.",
    errRegister: "Couldn't create the account. The email may already be registered.",
    errOtpLen: "Enter the 6-digit code.",
    errOtpInvalid: "Invalid code. Please try again.",
    okResent: "A new code has been sent.",
    errResend: "Couldn't send the code. Please try later.",
    okForgot: "If that email exists — we've sent a password reset link.",
    errForgot: "Couldn't send the link. Please try later.",
    hForgotEye: "Account recovery", hForgotTitle: "Forgot password?", hForgotSub: "Enter your email — we'll send a secure link to create a new password.",
    hOtpEye: "Confirmation", hOtpTitle: "Check your inbox", hOtpSub: (em) => `We sent a 6-digit code to ${em}. Enter it to activate your account.`,
    hRegEye: "New account", hRegTitle: "Client registration", hRegSub: "Create a cabinet to manage requests, contracts and disposal acts in one place.",
    hSignEye: "Client cabinet", hSignTitle: "Sign in to the cabinet", hSignSub: "Sign in to see request statuses, reorder and chat with your manager.",
    brandAria: "ECO.NOVA — home", tabsAria: "Sign in or register", tabSignin: "Sign in", tabRegister: "Register",
    orEmail: "or with email", password: "Password", forgotQ: "Forgot password?", signIn: "Sign in",
    surname: "Surname", surnamePh: "Petrenko", name: "First name", namePh: "Oleh",
    middle: "Patronymic", optional: "(optional)", middlePh: "Ivanovych",
    phone: "Phone", phonePh: "+380 50 123 45 67", company: "Company name", companyPh: "Health Clinic LLC",
    repeatPw: "Repeat password", pwMismatch: "Passwords don't match", createAccount: "Create account",
    regConsent: "By registering, you agree to the terms of service and data processing.",
    step2: "Step 2 of 2", devOtp1: "Preview mode (email not configured). Your code:",
    confirmLogin: "Confirm and sign in", resend: "Send a new code", resendCd: (c) => `Send a new code (${c}s)`,
    changeData: "← Edit details", devForgot: "Preview mode:", openResetLink: "open the recovery link →",
    sendLink: "Send link", backToLogin: "← Back to sign in", toMainSite: "← To the main site",
    digit: (n) => `Digit ${n}`,
  },
};

const AlertIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);
const OkIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);
const GoogleGlyph = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0012 23z" />
    <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 010-4.2V7.06H2.18a11 11 0 000 9.88l3.66-2.84z" />
    <path fill="#EA4335" d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.46 14.97.5 12 .5A11 11 0 002.18 7.06l3.66 2.84C6.71 7.3 9.14 4.75 12 4.75z" />
  </svg>
);

const RESEND_COOLDOWN = 30;
const OTP_LEN = 6;

export default function ClientLogin() {
  const navigate = useNavigate();
  const { login, isAuthed, loading } = useClientAuth();
  const { lang, changeLang } = useLang();
  const TT = TXT[lang] || TXT.uk;

  const [mode, setMode] = useState("signin"); // signin | register | forgot
  const [step, setStep] = useState("form"); // form | otp (register only)
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  // shared
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // register
  const [surname, setSurname] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [password2, setPassword2] = useState("");

  // otp
  const [otp, setOtp] = useState(Array(OTP_LEN).fill(""));
  const [devCode, setDevCode] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const otpRefs = useRef([]);

  // forgot result (dev)
  const [devResetLink, setDevResetLink] = useState("");

  useEffect(() => {
    if (!loading && isAuthed) navigate("/client", { replace: true });
  }, [loading, isAuthed, navigate]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const resetMsgs = () => { setErr(""); setOk(""); };

  const switchMode = (m) => {
    resetMsgs();
    setMode(m);
    setStep("form");
    setDevResetLink("");
  };

  const apiErr = (e, fallback) =>
    (e && e.response && e.response.data && e.response.data.detail) || fallback;

  // ── Google (fast) ──────────────────────────────────────────────────
  const handleCredential = async (credential) => {
    resetMsgs(); setBusy(true);
    try {
      const data = await ClientAPI.googleVerify(credential);
      const token = data.sessionToken || data.token || data.accessToken;
      if (!token) throw new Error("no token");
      login(token);
      navigate("/client", { replace: true });
    } catch (e) {
      setErr(TT.errGoogle);
      setBusy(false);
    }
  };

  // ── Sign in (email + password) ─────────────────────────────────────
  const submitSignin = async (e) => {
    e.preventDefault();
    resetMsgs();
    if (!email || !password) { setErr(TT.errCredsReq); return; }
    setBusy(true);
    try {
      const data = await ClientAPI.loginEmail(email.trim(), password);
      const token = data.sessionToken || data.token || data.accessToken;
      if (data.requires2FA || data.twoFactorRequired || data.challenge) {
        setErr(TT.err2fa);
        setBusy(false); return;
      }
      if (!token) throw new Error("no token");
      login(token);
      navigate("/client", { replace: true });
    } catch (e2) {
      setErr(apiErr(e2, TT.errInvalid));
      setBusy(false);
    }
  };

  // ── Register step 1 → send OTP ─────────────────────────────────────
  const submitRegister = async (e) => {
    e.preventDefault();
    resetMsgs();
    if (!firstName.trim() || !surname.trim()) { setErr(TT.errNameReq); return; }
    if (!email.trim()) { setErr(TT.errEmailReq); return; }
    const emCheck = validateEmail(email, { required: true, lang });
    if (!emCheck.ok) { setErr(emCheck.error); return; }
    if (phone.trim()) {
      const phCheck = validatePhone(phone, lang);
      if (!phCheck.ok) { setErr(phCheck.error); return; }
    }
    if (passwordScore(password) < 3 || password.length < 8) {
      setErr(TT.errPwWeak); return;
    }
    if (password !== password2) { setErr(TT.errPwMismatch); return; }
    setBusy(true);
    try {
      const data = await ClientAPI.registerEmail({
        email: email.trim(),
        password,
        name: firstName.trim(),
        surname: surname.trim(),
        middle_name: middleName.trim(),
        company_name: company.trim(),
        phone: phone.trim(),
      });
      setDevCode(data.devCode || "");
      setOtp(Array(OTP_LEN).fill(""));
      setCooldown(data.resendCooldown || RESEND_COOLDOWN);
      setStep("otp");
      setOk("");
      setBusy(false);
      setTimeout(() => otpRefs.current[0] && otpRefs.current[0].focus(), 60);
    } catch (e2) {
      setErr(apiErr(e2, TT.errRegister));
      setBusy(false);
    }
  };

  // ── OTP handling ───────────────────────────────────────────────────
  const otpValue = otp.join("");
  const setOtpAt = (i, v) => {
    const clean = v.replace(/\D/g, "");
    setOtp((prev) => {
      const next = [...prev];
      if (clean.length > 1) {
        // paste
        const chars = clean.slice(0, OTP_LEN).split("");
        for (let k = 0; k < OTP_LEN; k++) next[k] = chars[k] || "";
        setTimeout(() => {
          const last = Math.min(chars.length, OTP_LEN) - 1;
          if (otpRefs.current[last]) otpRefs.current[last].focus();
        }, 0);
        return next;
      }
      next[i] = clean;
      if (clean && i < OTP_LEN - 1 && otpRefs.current[i + 1]) otpRefs.current[i + 1].focus();
      return next;
    });
  };
  const otpKey = (i, e) => {
    if (e.key === "Backspace" && !otp[i] && i > 0 && otpRefs.current[i - 1]) {
      otpRefs.current[i - 1].focus();
    }
  };

  const submitOtp = async (e) => {
    if (e) e.preventDefault();
    resetMsgs();
    if (otpValue.length !== OTP_LEN) { setErr(TT.errOtpLen); return; }
    setBusy(true);
    try {
      const data = await ClientAPI.verifyEmail(email.trim(), otpValue);
      const token = data.sessionToken || data.token || data.accessToken;
      if (!token) throw new Error("no token");
      login(token);
      navigate("/client", { replace: true });
    } catch (e2) {
      setErr(apiErr(e2, TT.errOtpInvalid));
      setBusy(false);
    }
  };

  const resendOtp = async () => {
    if (cooldown > 0) return;
    resetMsgs(); setBusy(true);
    try {
      const data = await ClientAPI.resendCode(email.trim());
      setDevCode(data.devCode || devCode);
      setCooldown(data.resendCooldown || RESEND_COOLDOWN);
      setOk(TT.okResent);
    } catch (e2) {
      setErr(apiErr(e2, TT.errResend));
    } finally {
      setBusy(false);
    }
  };

  // ── Forgot password ────────────────────────────────────────────────
  const submitForgot = async (e) => {
    e.preventDefault();
    resetMsgs(); setDevResetLink("");
    if (!email.trim()) { setErr(TT.errEmailReq); return; }
    setBusy(true);
    try {
      const data = await ClientAPI.forgotPassword(email.trim());
      setOk(TT.okForgot);
      if (data && data.reset_link) {
        // dev/preview convenience — surface the link locally
        const m = String(data.reset_link).match(/token=([^&]+)/);
        if (m) setDevResetLink(`/cabinet/reset-password?token=${m[1]}`);
      }
    } catch (e2) {
      setErr(apiErr(e2, TT.errForgot));
    } finally {
      setBusy(false);
    }
  };

  // ── headings ───────────────────────────────────────────────────────
  const heading = useMemo(() => {
    if (mode === "forgot") return { eyebrow: TT.hForgotEye, title: TT.hForgotTitle, sub: TT.hForgotSub };
    if (mode === "register" && step === "otp") return { eyebrow: TT.hOtpEye, title: TT.hOtpTitle, sub: TT.hOtpSub(email) };
    if (mode === "register") return { eyebrow: TT.hRegEye, title: TT.hRegTitle, sub: TT.hRegSub };
    return { eyebrow: TT.hSignEye, title: TT.hSignTitle, sub: TT.hSignSub };
  }, [mode, step, email, TT]);

  return (
    <div className="client-auth" data-testid="client-auth">
      <div className="client-auth__grid">
        <div className="client-auth__left">
          <LeafFall />
          <div className="client-auth__container auth-enter" key={`${mode}-${step}`}>
            <div className="client-auth__topbar">
              <Link to="/" className="client-auth__brand" aria-label={TT.brandAria}>
                <span className="eco-wordmark">ECO<span className="eco-wordmark__dot" /><span className="eco-wordmark__nova">NOVA</span></span>
                <span className="client-auth__brand-sub">Utilization Platform</span>
              </Link>
              <div className="cl-lang" role="group" aria-label="Language" data-testid="login-lang-switch">
                {[{ code: "uk", label: "UA" }, { code: "en", label: "EN" }].map((c) => (
                  <button key={c.code} type="button"
                    className={`cl-lang__btn ${lang === c.code ? "is-active" : ""}`}
                    onClick={() => changeLang(c.code)} data-testid={`login-lang-${c.code}`}>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <p className="auth-eyebrow">{heading.eyebrow}</p>
            <h1 className="auth-title">{heading.title}</h1>
            <p className="auth-subtitle">{heading.sub}</p>

            {/* Tabs (only on the main forms) */}
            {mode !== "forgot" && step === "form" && (
              <div className="segmented" role="tablist" aria-label={TT.tabsAria}>
                <button role="tab" aria-selected={mode === "signin"} className="segmented__tab"
                  onClick={() => switchMode("signin")} data-testid="tab-signin">{TT.tabSignin}</button>
                <button role="tab" aria-selected={mode === "register"} className="segmented__tab"
                  onClick={() => switchMode("register")} data-testid="tab-register">{TT.tabRegister}</button>
              </div>
            )}

            {/* Google (fast) — on the main forms */}
            {mode !== "forgot" && step === "form" && (
              <>
                <div className="auth-gsi-host" data-testid="google-host">
                  <GoogleSignIn onCredential={handleCredential} />
                </div>
                <div className="divider"><span className="divider__label">{TT.orEmail}</span></div>
              </>
            )}

            {/* Alerts */}
            {err && (
              <div className="auth-alert auth-alert--err" data-testid="auth-error" role="alert">
                <AlertIcon /><span>{err}</span>
              </div>
            )}
            {ok && (
              <div className="auth-alert auth-alert--ok" data-testid="auth-ok">
                <OkIcon /><span>{ok}</span>
              </div>
            )}

            {/* ── SIGN IN ── */}
            {mode === "signin" && step === "form" && (
              <form className="auth-form" onSubmit={submitSignin} data-testid="signin-form">
                <div className="auth-field auth-field--full">
                  <label className="auth-label" htmlFor="si-email">Email</label>
                  <input id="si-email" data-testid="signin-email" type="email" className="auth-input"
                    value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.ua" autoComplete="email" />
                </div>
                <PasswordField label={TT.password} value={password} onChange={setPassword}
                  autoComplete="current-password" testid="signin-password" />
                <div className="auth-meta">
                  <span />
                  <button type="button" className="link" onClick={() => switchMode("forgot")} data-testid="to-forgot">{TT.forgotQ}</button>
                </div>
                <div className="auth-actions">
                  <button type="submit" className="btn-primary" disabled={busy} data-testid="signin-submit">
                    {busy ? <span className="auth-spinner" /> : TT.signIn}
                  </button>
                </div>
              </form>
            )}

            {/* ── REGISTER (step 1) ── */}
            {mode === "register" && step === "form" && (
              <form className="auth-form" onSubmit={submitRegister} data-testid="register-form">
                <div className="auth-row">
                  <div className="auth-field">
                    <label className="auth-label" htmlFor="r-surname">{TT.surname}</label>
                    <input id="r-surname" data-testid="reg-surname" className="auth-input" value={surname}
                      onChange={(e) => setSurname(e.target.value)} placeholder={TT.surnamePh} autoComplete="family-name" />
                  </div>
                  <div className="auth-field">
                    <label className="auth-label" htmlFor="r-name">{TT.name}</label>
                    <input id="r-name" data-testid="reg-name" className="auth-input" value={firstName}
                      onChange={(e) => setFirstName(e.target.value)} placeholder={TT.namePh} autoComplete="given-name" />
                  </div>
                </div>
                <div className="auth-row">
                  <div className="auth-field">
                    <label className="auth-label" htmlFor="r-middle">{TT.middle} <span>{TT.optional}</span></label>
                    <input id="r-middle" data-testid="reg-middle" className="auth-input" value={middleName}
                      onChange={(e) => setMiddleName(e.target.value)} placeholder={TT.middlePh} />
                  </div>
                  <div className="auth-field">
                    <label className="auth-label" htmlFor="r-phone">{TT.phone} <span>{TT.optional}</span></label>
                    <PhoneField value={phone} onChange={setPhone} international={lang === "en"} testId="reg-phone" />
                  </div>
                </div>
                <div className="auth-field auth-field--full">
                  <label className="auth-label" htmlFor="r-company">{TT.company} <span>{TT.optional}</span></label>
                  <CompanyAutocomplete
                    value={company}
                    onChange={setCompany}
                    onSelect={(it) => setCompany(it.name)}
                    placeholder={TT.companyPh}
                    testId="reg-company"
                    lang={lang}
                    inputClassName="auth-input"
                  />
                </div>
                <div className="auth-field auth-field--full">
                  <label className="auth-label" htmlFor="r-email">Email</label>
                  <input id="r-email" data-testid="reg-email" type="email" className="auth-input" value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="name@company.ua" autoComplete="email" />
                </div>
                <PasswordField label={TT.password} value={password} onChange={setPassword}
                  showStrength showGenerator testid="reg-password" />
                <div className="auth-field auth-field--full">
                  <label className="auth-label" htmlFor="reg-password2">{TT.repeatPw}</label>
                  <div className="auth-pass">
                    <input id="reg-password2" data-testid="reg-password2" type="password" className="auth-input"
                      value={password2} onChange={(e) => setPassword2(e.target.value)} placeholder="••••••••"
                      autoComplete="new-password"
                      aria-invalid={password2 && password2 !== password ? "true" : "false"} />
                  </div>
                  {password2 && password2 !== password && (
                    <span className="auth-strength__label" style={{ color: "#B4231F" }}>{TT.pwMismatch}</span>
                  )}
                </div>
                <div className="auth-actions">
                  <button type="submit" className="btn-primary" disabled={busy} data-testid="register-submit">
                    {busy ? <span className="auth-spinner" /> : TT.createAccount}
                  </button>
                </div>
                <p className="auth-subtitle" style={{ fontSize: 12, marginTop: 12 }}>
                  {TT.regConsent}
                </p>
              </form>
            )}

            {/* ── REGISTER (step 2 — OTP) ── */}
            {mode === "register" && step === "otp" && (
              <form className="auth-form" onSubmit={submitOtp} data-testid="otp-form">
                <div className="auth-stepper">
                  <span className="auth-stepper__pill">{TT.step2}</span>
                  <div className="auth-stepper__bar"><div className="auth-stepper__fill" style={{ width: "100%" }} /></div>
                </div>
                <div className="auth-otp" data-testid="otp-inputs">
                  {otp.map((d, i) => (
                    <input key={i} ref={(el) => (otpRefs.current[i] = el)} inputMode="numeric"
                      maxLength={i === 0 ? OTP_LEN : 1} value={d}
                      onChange={(e) => setOtpAt(i, e.target.value)} onKeyDown={(e) => otpKey(i, e)}
                      data-testid={`otp-${i}`} aria-label={TT.digit(i + 1)} />
                  ))}
                </div>
                {devCode && (
                  <div className="auth-dev" data-testid="otp-devcode">
                    {TT.devOtp1} <b>{devCode}</b>
                  </div>
                )}
                <div className="auth-actions">
                  <button type="submit" className="btn-primary" disabled={busy} data-testid="otp-submit">
                    {busy ? <span className="auth-spinner" /> : TT.confirmLogin}
                  </button>
                  <button type="button" className="btn-ghost" onClick={resendOtp} disabled={cooldown > 0 || busy} data-testid="otp-resend">
                    {cooldown > 0 ? TT.resendCd(cooldown) : TT.resend}
                  </button>
                </div>
                <div className="auth-meta">
                  <button type="button" className="link" onClick={() => { setStep("form"); resetMsgs(); }} data-testid="otp-back">{TT.changeData}</button>
                  <span />
                </div>
              </form>
            )}

            {/* ── FORGOT ── */}
            {mode === "forgot" && (
              <form className="auth-form" onSubmit={submitForgot} data-testid="forgot-form">
                <div className="auth-field auth-field--full">
                  <label className="auth-label" htmlFor="f-email">Email</label>
                  <input id="f-email" data-testid="forgot-email" type="email" className="auth-input" value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="name@company.ua" autoComplete="email" />
                </div>
                {devResetLink && (
                  <div className="auth-dev" data-testid="forgot-devlink">
                    {TT.devForgot}{" "}
                    <Link className="link" to={devResetLink}>{TT.openResetLink}</Link>
                  </div>
                )}
                <div className="auth-actions">
                  <button type="submit" className="btn-primary" disabled={busy} data-testid="forgot-submit">
                    {busy ? <span className="auth-spinner" /> : TT.sendLink}
                  </button>
                  <button type="button" className="btn-ghost" onClick={() => switchMode("signin")} data-testid="forgot-back">
                    {TT.backToLogin}
                  </button>
                </div>
              </form>
            )}

            <div className="auth-foot">
              <Link to="/">{TT.toMainSite}</Link>
              <a href="tel:+380667880445">+380 66 788 04 45</a>
            </div>
          </div>
        </div>

        <AuthAside />
      </div>
    </div>
  );
}
