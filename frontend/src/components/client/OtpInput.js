import React, { useRef } from "react";

/** Simple 6-box OTP input with auto-advance + paste support. */
export default function OtpInput({ value, onChange, length = 6, testid = "register-otp-input" }) {
  const refs = useRef([]);
  const chars = value.padEnd(length, " ").slice(0, length).split("");

  const setAt = (i, ch) => {
    const arr = value.padEnd(length, " ").split("");
    arr[i] = ch || " ";
    onChange(arr.join("").replace(/\s+$/g, "").slice(0, length));
  };

  const onKey = (i, e) => {
    if (e.key === "Backspace" && !chars[i].trim() && i > 0) {
      refs.current[i - 1]?.focus();
    }
  };

  const onInput = (i, e) => {
    const d = (e.target.value || "").replace(/\D/g, "");
    if (!d) { setAt(i, ""); return; }
    if (d.length > 1) {
      // paste
      const next = (value.slice(0, i) + d).replace(/\D/g, "").slice(0, length);
      onChange(next);
      const focusIdx = Math.min(next.length, length - 1);
      refs.current[focusIdx]?.focus();
      return;
    }
    setAt(i, d);
    if (i < length - 1) refs.current[i + 1]?.focus();
  };

  return (
    <div className="auth-otp" data-testid={testid}>
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          inputMode="numeric"
          maxLength={1}
          value={chars[i].trim()}
          onChange={(e) => onInput(i, e)}
          onKeyDown={(e) => onKey(i, e)}
          aria-label={`Цифра ${i + 1}`}
          data-testid={`${testid}-${i}`}
        />
      ))}
    </div>
  );
}
