/**
 * PhoneInput — country-aware international phone input
 * =====================================================
 *
 * Used in CRM forms (leads, customers) so phone numbers always land in the
 * DB with E.164-friendly formatting. We don't ship `libphonenumber` (too
 * heavy for a single field) — instead we maintain a curated list of the
 * countries this car-import business actually serves, validate against
 * per-country digit-length ranges, and let the admin override with raw
 * paste-in if they really need to.
 *
 * Props:
 *   value          — string (the phone as currently displayed in the input)
 *   country        — string (2-letter country code, controlled)
 *   onChange       — ({phone, country, isValid}) => void
 *   error          — string or null (forces red border + helper text)
 *   testId         — string (data-testid prefix)
 *
 * Output value contract:
 *   • `phone`   = the full international number with leading `+` (e.g. "+359888123456")
 *   • `country` = 2-letter ISO (e.g. "BG")
 *   • `isValid` = boolean (true when digit count is inside the country range)
 *
 * The parent can safely persist `{phone, phoneCountry: country}` as-is.
 */
import React from 'react';
import { CaretDown } from '@phosphor-icons/react';

// Countries the ECO platform serves. Order matters — most common first so
// operators find them fast in the dropdown. Ukraine is the default.
export const PHONE_COUNTRIES = [
  { code: 'UA', name: 'Ukraine',        dial: '+380', flag: '🇺🇦', minLen: 9, maxLen: 9 },
  { code: 'PL', name: 'Poland',         dial: '+48',  flag: '🇵🇱', minLen: 9, maxLen: 9 },
  { code: 'RO', name: 'Romania',        dial: '+40',  flag: '🇷🇴', minLen: 9, maxLen: 9 },
  { code: 'DE', name: 'Germany',        dial: '+49',  flag: '🇩🇪', minLen: 10, maxLen: 11 },
  { code: 'MD', name: 'Moldova',        dial: '+373', flag: '🇲🇩', minLen: 8, maxLen: 8 },
  { code: 'LT', name: 'Lithuania',      dial: '+370', flag: '🇱🇹', minLen: 8, maxLen: 8 },
  { code: 'LV', name: 'Latvia',         dial: '+371', flag: '🇱🇻', minLen: 8, maxLen: 8 },
  { code: 'GE', name: 'Georgia',        dial: '+995', flag: '🇬🇪', minLen: 9, maxLen: 9 },
  { code: 'NL', name: 'Netherlands',    dial: '+31',  flag: '🇳🇱', minLen: 9, maxLen: 9 },
  { code: 'US', name: 'United States',  dial: '+1',   flag: '🇺🇸', minLen: 10, maxLen: 10 },
  { code: 'GB', name: 'United Kingdom', dial: '+44',  flag: '🇬🇧', minLen: 10, maxLen: 10 },
];

const countryByCode = (code) =>
  PHONE_COUNTRIES.find((c) => c.code === code) || PHONE_COUNTRIES[0];

/**
 * Try to detect a country from a free-form phone string. Returns null when
 * the prefix doesn't match any known dial code — caller should keep the
 * existing country and just store the digits.
 */
export const detectCountry = (phone) => {
  const trimmed = String(phone || '').replace(/[^\d+]/g, '');
  if (!trimmed.startsWith('+')) return null;
  // Match longest prefix first (so +380 wins over +38 in case we ever add a +38 variant).
  const sorted = [...PHONE_COUNTRIES].sort((a, b) => b.dial.length - a.dial.length);
  return sorted.find((c) => trimmed.startsWith(c.dial)) || null;
};

/** Strip the dial code, returns just the local digits. */
export const localDigits = (phone, country) => {
  const c = countryByCode(country);
  const trimmed = String(phone || '').replace(/[^\d+]/g, '');
  if (trimmed.startsWith(c.dial)) return trimmed.slice(c.dial.length);
  if (trimmed.startsWith('+')) return trimmed.slice(1); // unknown prefix, keep raw
  return trimmed;
};

/** True when the local digit count fits the country range. */
export const isValidForCountry = (phone, country) => {
  const c = countryByCode(country);
  const digits = localDigits(phone, country).replace(/\D/g, '');
  return digits.length >= c.minLen && digits.length <= c.maxLen;
};

const PhoneInput = ({
  value,
  country,
  onChange,
  error,
  disabled,
  required,
  testId = 'phone-input',
  placeholder,
}) => {
  const [open, setOpen] = React.useState(false);
  const rootRef = React.useRef(null);

  // Click-outside to close the country menu.
  React.useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const c = countryByCode(country);
  const digits = localDigits(value, country);
  const valid = isValidForCountry(value || `${c.dial}${digits}`, country);

  const emit = (newDigits, newCountry) => {
    const cc = countryByCode(newCountry || country);
    const cleaned = String(newDigits || '').replace(/\D/g, '');
    const fullPhone = cleaned ? `${cc.dial}${cleaned}` : '';
    onChange({
      phone: fullPhone,
      country: cc.code,
      isValid: isValidForCountry(fullPhone, cc.code),
    });
  };

  const handleDigits = (e) => emit(e.target.value, country);
  const handleCountry = (newCode) => {
    setOpen(false);
    emit(digits, newCode);
  };

  return (
    <div ref={rootRef} className="relative">
      <div
        className={
          'flex items-stretch rounded-xl border bg-white overflow-hidden transition-colors ' +
          (error
            ? 'border-[#DC2626] focus-within:ring-2 focus-within:ring-[#DC2626]/30'
            : 'border-[#E4E4E7] focus-within:border-[#18181B] focus-within:ring-2 focus-within:ring-[#18181B]/20')
        }
      >
        <button
          type="button"
          onClick={() => !disabled && setOpen((v) => !v)}
          disabled={disabled}
          className="flex items-center gap-1.5 px-3 border-r border-[#E4E4E7] bg-[#FAFAFA] hover:bg-[#F4F4F5] text-[13px] font-medium text-[#18181B] disabled:opacity-60"
          data-testid={`${testId}-country`}
          aria-label="Select country dial code"
        >
          <span className="text-base leading-none">{c.flag}</span>
          <span className="font-mono text-[12px] text-[#71717A]">{c.dial}</span>
          <CaretDown size={12} weight="bold" className="text-[#A1A1AA]" />
        </button>
        <input
          type="tel"
          inputMode="numeric"
          value={digits}
          onChange={handleDigits}
          disabled={disabled}
          required={required}
          placeholder={placeholder || `${c.minLen}-${c.maxLen} digits`}
          className="flex-1 min-w-0 px-3 py-2.5 text-[14px] bg-transparent focus:outline-none placeholder:text-[#A1A1AA]"
          data-testid={`${testId}-digits`}
        />
      </div>
      {open ? (
        <div className="absolute z-50 top-full mt-1 left-0 right-0 sm:w-72 max-h-72 overflow-y-auto bg-white border border-[#E4E4E7] rounded-xl shadow-lg py-1">
          {PHONE_COUNTRIES.map((cc) => (
            <button
              key={cc.code}
              type="button"
              onClick={() => handleCountry(cc.code)}
              className={
                'w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] hover:bg-[#FAFAFA] ' +
                (cc.code === country ? 'bg-[#F4F4F5]' : '')
              }
              data-testid={`${testId}-option-${cc.code}`}
            >
              <span className="text-base leading-none">{cc.flag}</span>
              <span className="flex-1 text-[#18181B]">{cc.name}</span>
              <span className="font-mono text-[12px] text-[#71717A]">{cc.dial}</span>
            </button>
          ))}
        </div>
      ) : null}
      {error ? (
        <p className="mt-1.5 text-[11px] text-[#DC2626]">{error}</p>
      ) : digits && !valid ? (
        <p className="mt-1.5 text-[11px] text-[#D97706]">
          Expected {c.minLen}{c.minLen !== c.maxLen ? `–${c.maxLen}` : ''} digits for {c.name}
        </p>
      ) : null}
    </div>
  );
};

export default PhoneInput;
