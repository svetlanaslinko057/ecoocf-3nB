import React, { useEffect, useRef, useState } from "react";
import { ClientAPI } from "@/lib/clientApi";
import { useLang } from "@/i18n";

// Classic Google Identity Services (GIS) sign-in — uses ONLY the public OAuth
// Client ID (no secret). The browser receives a Google ID token (credential)
// which the backend verifies at /api/customer-auth/google/verify.
//
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
// THIS BREAKS THE AUTH. (GIS uses the page origin; the origin must be added to
// the OAuth client's "Authorized JavaScript origins" in Google Cloud Console.)
const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGsi() {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.accounts && window.google.accounts.id) return resolve();
    const existing = document.querySelector(`script[src="${GSI_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", reject);
      // if already loaded
      if (window.google && window.google.accounts) resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

export default function GoogleSignIn({ onCredential, onError }) {
  const { lang } = useLang();
  const G = lang === "en"
    ? {
        loading: "Loading Google…",
        disabled: "Google sign-in is temporarily unavailable. Please contact your manager.",
        error: "Couldn't initialize Google sign-in. Make sure the domain is added to \u201cAuthorized JavaScript origins\u201d in Google Cloud Console.",
      }
    : {
        loading: "Завантаження Google…",
        disabled: "Google-вхід тимчасово недоступний. Зверніться до менеджера.",
        error: "Не вдалося ініціалізувати Google-вхід. Перевірте, що домен додано до «Authorized JavaScript origins» у Google Cloud Console.",
      };
  const ref = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | ready | disabled | error

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await ClientAPI.googleClientId();
        if (cancelled) return;
        if (!cfg.enabled || !cfg.clientId) {
          setStatus("disabled");
          return;
        }
        await loadGsi();
        if (cancelled || !(window.google && window.google.accounts && window.google.accounts.id)) {
          setStatus("error");
          return;
        }
        window.google.accounts.id.initialize({
          client_id: cfg.clientId,
          callback: (resp) => {
            if (resp && resp.credential) onCredential(resp.credential);
          },
          ux_mode: "popup",
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        if (ref.current) {
          ref.current.innerHTML = "";
          window.google.accounts.id.renderButton(ref.current, {
            theme: "outline",
            size: "large",
            shape: "pill",
            text: "continue_with",
            logo_alignment: "center",
            width: 300,
          });
        }
        try {
          window.google.accounts.id.prompt();
        } catch (e) {
          /* One Tap optional */
        }
        setStatus("ready");
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          if (onError) onError(e);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="gsi-wrap" data-testid="google-signin">
      <div ref={ref} className="gsi-btn" />
      {status === "loading" && <p className="gsi-note">{G.loading}</p>}
      {status === "disabled" && (
        <p className="gsi-note">{G.disabled}</p>
      )}
      {status === "error" && (
        <p className="gsi-note gsi-note--err">
          {G.error}
        </p>
      )}
    </div>
  );
}
