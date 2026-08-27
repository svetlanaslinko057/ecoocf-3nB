import React, { useState } from "react";
import { Eye, EyeOff, Wand2, Check } from "lucide-react";
import { toast } from "@/components/ui/sonner";

export function scorePassword(pw) {
  const checks = {
    len: (pw || "").length >= 8,
    upper: /[A-ZА-ЯЇІЄ]/.test(pw || ""),
    lower: /[a-zа-яїіє]/.test(pw || ""),
    num: /[0-9]/.test(pw || ""),
    sym: /[^A-Za-zА-Яа-я0-9]/.test(pw || ""),
  };
  const passed = Object.values(checks).filter(Boolean).length;
  return { checks, passed, pct: Math.round((passed / 5) * 100) };
}

function genStrongPassword(len = 16) {
  const U = "ABCDEFGHJKLMNPQRSTUVWXYZ"; // no I/O
  const L = "abcdefghijkmnpqrstuvwxyz"; // no l/o
  const N = "23456789"; // no 0/1
  const S = "!@#$%^&*-_=+?";
  const all = U + L + N + S;
  const rand = (set) => set[Math.floor((window.crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32) * set.length)];
  let out = [rand(U), rand(L), rand(N), rand(S)];
  for (let i = out.length; i < len; i++) out.push(rand(all));
  // shuffle (Fisher-Yates with crypto)
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor((window.crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32) * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out.join("");
}

const CHECK_LABELS = [
  ["len", "≥ 8 символів"],
  ["upper", "Велика літера"],
  ["lower", "Мала літера"],
  ["num", "Цифра"],
  ["sym", "Символ"],
];

export default function PasswordField({
  value, onChange, label = "Пароль", placeholder = "••••••••", testid,
  showMeter = false, showGenerator = false, autoComplete = "current-password", invalid = false,
}) {
  const [show, setShow] = useState(false);
  const { checks, pct } = scorePassword(value);
  const color = pct < 40 ? "rgba(220,38,38,0.9)" : pct < 80 ? "rgba(217,119,6,0.95)" : "#2F5D3D";
  const label_ = pct < 40 ? "Слабкий" : pct < 80 ? "Помірний" : "Надійний";

  const generate = () => {
    const pw = genStrongPassword(16);
    onChange(pw);
    setShow(true);
    try { navigator.clipboard.writeText(pw); toast.success("Пароль згенеровано та скопійовано"); } catch { /* noop */ }
  };

  return (
    <div className="auth-field">
      <label className="auth-label" htmlFor={testid}>{label}</label>
      <div className="auth-pass">
        <input
          id={testid}
          data-testid={testid}
          className="auth-input"
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          aria-invalid={invalid ? "true" : undefined}
        />
        <button type="button" className="auth-pass__eye" onClick={() => setShow((v) => !v)}
          aria-label={show ? "Сховати пароль" : "Показати пароль"} data-testid="password-visibility-toggle">
          {show ? <EyeOff /> : <Eye />}
        </button>
      </div>

      {showGenerator && (
        <div className="auth-pass__tools">
          <button type="button" className="auth-gen" onClick={generate} data-testid="password-generate-button">
            <Wand2 /> Згенерувати надійний
          </button>
        </div>
      )}

      {showMeter && value && (
        <div className="auth-strength" data-testid="password-strength-meter">
          <div className="auth-strength__bar"><div className="auth-strength__fill" style={{ width: `${pct}%`, background: color }} /></div>
          <div className="auth-strength__label">Надійність пароля: <strong style={{ color }}>{label_}</strong></div>
          <ul className="auth-checklist">
            {CHECK_LABELS.map(([key, text]) => (
              <li key={key} className={checks[key] ? "ok" : ""}>
                <Check style={{ opacity: checks[key] ? 1 : 0.3 }} /> {text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
