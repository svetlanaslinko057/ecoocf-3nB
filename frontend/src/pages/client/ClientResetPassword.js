import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ClientAPI } from "@/lib/clientApi";
import { useClientAuth } from "@/context/ClientAuthContext";
import PasswordField from "@/components/PasswordField";
import AuthAside from "@/components/AuthAside";
import LeafFall from "@/components/LeafFall";
import { passwordScore } from "@/lib/passwordUtils";
import { useClientCopy } from "./clientCopy";
import "./client-auth.css";

const AlertIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

export default function ClientResetPassword() {
  const navigate = useNavigate();
  const { login } = useClientAuth();
  const { L } = useClientCopy();
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const [checking, setChecking] = useState(true);
  const [valid, setValid] = useState(false);
  const [maskedEmail, setMaskedEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) { setChecking(false); setValid(false); return; }
      try {
        const d = await ClientAPI.validateResetToken(token);
        if (cancelled) return;
        setValid(!!d.valid);
        setMaskedEmail(d.email || "");
      } catch (e) {
        if (!cancelled) setValid(false);
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (passwordScore(password) < 3 || password.length < 8) {
      setErr(L.rpErrWeak); return;
    }
    if (password !== password2) { setErr(L.rpErrMismatch); return; }
    setBusy(true);
    try {
      const data = await ClientAPI.resetPassword(token, password);
      const tk = data.sessionToken || data.token || data.accessToken;
      if (tk) {
        login(tk);
        navigate("/client", { replace: true });
      } else {
        navigate("/client/login", { replace: true });
      }
    } catch (e2) {
      setErr((e2 && e2.response && e2.response.data && e2.response.data.detail) || L.rpErrFail);
      setBusy(false);
    }
  };

  return (
    <div className="client-auth" data-testid="client-reset">
      <div className="client-auth__grid">
        <div className="client-auth__left">
          <LeafFall />
          <div className="client-auth__container auth-enter">
            <Link to="/" className="client-auth__brand" aria-label="ECO">
              <span className="eco-wordmark">ECO<span className="eco-wordmark__dot" /><span className="eco-wordmark__nova">NOVA</span></span>
              <span className="client-auth__brand-sub">Utilization Platform</span>
            </Link>

            <p className="auth-eyebrow">{L.rpEyebrow}</p>
            <h1 className="auth-title">{L.rpTitle}</h1>

            {checking && <p className="auth-subtitle">{L.rpChecking}</p>}

            {!checking && !valid && (
              <>
                <p className="auth-subtitle">{L.rpInvalid}</p>
                <div className="auth-actions">
                  <Link to="/client/login" className="btn-primary" style={{ textDecoration: "none" }}>{L.rpToLogin}</Link>
                </div>
              </>
            )}

            {!checking && valid && (
              <>
                <p className="auth-subtitle">
                  {maskedEmail ? L.rpCreateFor(maskedEmail) : L.rpCreateGeneric}
                </p>
                {err && (
                  <div className="auth-alert auth-alert--err" data-testid="reset-error" role="alert">
                    <AlertIcon /><span>{err}</span>
                  </div>
                )}
                <form className="auth-form" onSubmit={submit} data-testid="reset-form">
                  <PasswordField label={L.rpNewPass} value={password} onChange={setPassword}
                    showStrength showGenerator testid="reset-password" />
                  <div className="auth-field auth-field--full">
                    <label className="auth-label" htmlFor="reset-password2">{L.rpRepeat}</label>
                    <div className="auth-pass">
                      <input id="reset-password2" data-testid="reset-password2" type="password" className="auth-input"
                        value={password2} onChange={(e) => setPassword2(e.target.value)} placeholder="••••••••"
                        autoComplete="new-password"
                        aria-invalid={password2 && password2 !== password ? "true" : "false"} />
                    </div>
                  </div>
                  <div className="auth-actions">
                    <button type="submit" className="btn-primary" disabled={busy} data-testid="reset-submit">
                      {busy ? <span className="auth-spinner" /> : L.rpSaveLogin}
                    </button>
                  </div>
                </form>
              </>
            )}

            <div className="auth-foot">
              <Link to="/client/login">{L.rpBackLogin}</Link>
              <a href="tel:+380667880445">+380 66 788 04 45</a>
            </div>
          </div>
        </div>
        <AuthAside />
      </div>
    </div>
  );
}
