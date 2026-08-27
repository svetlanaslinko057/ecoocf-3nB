// Phone input with a country flag + dial-code selector.
// Built on react-phone-number-input (libphonenumber-js under the hood).
//
// Language-adaptive modes:
//   • Ukrainian (default)  → defaultCountry "UA": shows the 🇺🇦 flag + "+380",
//     the user types the national part. Country can still be changed.
//   • International (en)    → no forced country: the field starts in pure
//     international mode ("+"), the user enters a full international number and
//     the country is auto-detected (true E.164 / international standard).
//
// The emitted value is always normalized to E.164 (e.g. "+380671234567").
import React from "react";
import PhoneInput, { isValidPhoneNumber } from "react-phone-number-input";
import "react-phone-number-input/style.css";
import "./PhoneField.css";
import CountrySelect from "./CountrySelect";

export { isValidPhoneNumber };

// Clean single-glyph globe used for the "International" (no country) state,
// replacing the library's default phone-over-globe icon that read as TWO icons.
function GlobeIcon({ title }) {
  return (
    <svg
      className="phf-globe"
      viewBox="0 0 24 24"
      width="100%"
      height="100%"
      role="img"
      aria-label={title || "International"}
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18M4.5 7.5c4.7 2.2 10.3 2.2 15 0M4.5 16.5c4.7-2.2 10.3-2.2 15 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function PhoneField({
  value,
  onChange,
  invalid = false,
  testId = "phone",
  international = false,
  defaultCountry = "UA",
  placeholder,
}) {
  // International mode → no defaultCountry, no forced calling code.
  const dc = international ? undefined : (defaultCountry || "UA");
  const ph = placeholder ?? (international ? "+1 555 123 4567" : "67 123 45 67");

  return (
    <div className={`phf ${invalid ? "phf--err" : ""}`} data-testid={`${testId}-wrap`}>
      <PhoneInput
        international
        withCountryCallingCode={!international}
        defaultCountry={dc}
        countryCallingCodeEditable={false}
        countrySelectComponent={CountrySelect}
        internationalIcon={GlobeIcon}
        value={value || undefined}
        onChange={(v) => onChange(v || "")}
        placeholder={ph}
        numberInputProps={{ "data-testid": testId, inputMode: "tel" }}
      />
    </div>
  );
}
