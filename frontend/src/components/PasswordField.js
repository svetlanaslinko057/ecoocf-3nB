import React, { useState } from "react";
import { PWD_RULES, passwordScore, STRENGTH, generatePassword } from "@/lib/passwordUtils";
import { useLang } from "@/i18n";

const EyeIcon = ({ off }) =>
  off ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 10 8 10 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
      <path d="M6.61 6.61A18.5 18.5 0 002 12s3 8 10 8a9.12 9.12 0 005.39-1.61" />
      <line x1="2" y1="2" x2="22" y2="22" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );

const SparkIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
  </svg>
);

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

/**
 * PasswordField — input with eye-toggle, optional strength meter, rule
 * checklist and a one-click strong-password generator.
 */
export default function PasswordField({
  value,
  onChange,
  label,
  placeholder = "••••••••",
  autoComplete = "new-password",
  showStrength = false,
  showGenerator = false,
  testid = "password",
}) {
  const { lang } = useLang();
  const en = lang === "en";
  const tx = (o) => (o && typeof o === "object" ? (o[en ? "en" : "uk"] || o.uk) : o);
  const C = en
    ? { label: "Password", hide: "Hide password", show: "Show password", strength: "Strength:", generate: "Generate" }
    : { label: "Пароль", hide: "Сховати пароль", show: "Показати пароль", strength: "Надійність:", generate: "Згенерувати" };
  const fieldLabel = label || C.label;
  const [show, setShow] = useState(false);
  const score = passwordScore(value);
  const strength = STRENGTH[score];

  const gen = () => {
    const p = generatePassword(14);
    onChange(p);
    setShow(true);
  };

  return (
    <div className="auth-field auth-field--full">
      <label className="auth-label" htmlFor={testid}>{fieldLabel}</label>
      <div className="auth-pass">
        <input
          id={testid}
          data-testid={testid}
          type={show ? "text" : "password"}
          className="auth-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          className="auth-pass__eye"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? C.hide : C.show}
          data-testid={`${testid}-toggle`}
          tabIndex={-1}
        >
          <EyeIcon off={show} />
        </button>
      </div>

      {(showStrength || showGenerator) && (
        <div className="auth-pass__tools">
          {showStrength ? (
            <span className="auth-strength__label" data-testid={`${testid}-strength`}>
              {C.strength} <b style={{ color: strength.color }}>{tx(strength.label)}</b>
            </span>
          ) : <span />}
          {showGenerator && (
            <button type="button" className="auth-gen" onClick={gen} data-testid={`${testid}-generate`}>
              <SparkIcon /> {C.generate}
            </button>
          )}
        </div>
      )}

      {showStrength && (
        <>
          <div className="auth-strength">
            <div className="auth-strength__bar">
              <div
                className="auth-strength__fill"
                style={{ width: `${strength.pct}%`, background: strength.color }}
              />
            </div>
          </div>
          <ul className="auth-checklist">
            {PWD_RULES.map((r) => {
              const ok = r.test(value || "");
              return (
                <li key={r.key} className={ok ? "ok" : ""}>
                  <CheckIcon /> {tx(r.label)}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
