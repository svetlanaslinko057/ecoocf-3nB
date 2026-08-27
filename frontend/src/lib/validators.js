// Shared client-side validation for contact fields.
// Phone: Ukraine-first, but accepts any valid international number (E.164),
// powered by libphonenumber-js (Google's libphonenumber port).
import { parsePhoneNumberFromString } from "libphonenumber-js";

const MSG = {
  uk: {
    phoneRequired: "Вкажіть номер телефону",
    phoneInvalid: "Некоректний номер. Приклад: +380 67 123 45 67",
    phoneNotUA: "Вкажіть український номер: +380 67 123 45 67",
    emailRequired: "Вкажіть email",
    emailInvalid: "Некоректний email. Приклад: name@company.ua",
  },
  en: {
    phoneRequired: "Enter a phone number",
    phoneInvalid: "Invalid phone number. Use international format, e.g. +1 555 123 4567",
    phoneNotUA: "Enter a valid Ukrainian number: +380 67 123 45 67",
    emailRequired: "Enter an email",
    emailInvalid: "Invalid email. Example: name@company.ua",
  },
};

/**
 * Validate & normalize a phone number — language-adaptive.
 *
 *  • lang === "uk"  → Ukrainian standard. The number MUST be a valid
 *    Ukrainian (+380) number; a bare local number is interpreted with the
 *    "UA" region.
 *  • lang === "en"  → International standard (E.164). Any valid number from
 *    any country is accepted; a "+" country code is expected (no UA region
 *    assumption).
 *
 * @returns {{ok:boolean, e164?:string, formatted?:string, country?:string, error?:string}}
 */
export function validatePhone(raw, lang = "uk") {
  const m = MSG[lang] || MSG.uk;
  const v = (raw || "").trim();
  if (!v) return { ok: false, error: m.phoneRequired };

  const intl = lang === "en";
  // EN → pure international (region undefined). UK → assume UA when no "+".
  const region = v.startsWith("+") ? undefined : (intl ? undefined : "UA");
  let pn;
  try {
    pn = parsePhoneNumberFromString(v, region);
  } catch (e) {
    pn = null;
  }
  if (!pn || !pn.isValid()) return { ok: false, error: m.phoneInvalid };

  // Ukrainian mode enforces a Ukrainian number specifically.
  if (!intl && pn.country !== "UA") {
    return { ok: false, error: m.phoneNotUA };
  }
  return { ok: true, e164: pn.number, formatted: pn.formatInternational(), country: pn.country };
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/**
 * Validate an email address.
 * @returns {{ok:boolean, value?:string, error?:string}}
 */
export function validateEmail(raw, { required = false, lang = "uk" } = {}) {
  const m = MSG[lang] || MSG.uk;
  const v = (raw || "").trim();
  if (!v) return required ? { ok: false, error: m.emailRequired } : { ok: true, value: "" };
  if (!EMAIL_RE.test(v)) return { ok: false, error: m.emailInvalid };
  return { ok: true, value: v.toLowerCase() };
}
