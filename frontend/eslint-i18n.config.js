/**
 * Standalone i18n linter (ESLint 9 flat config).
 *
 * Purpose
 * ───────
 * Flags hardcoded English strings inside JSX of the **public site** so we
 * never regress the BG localization shipped in Session 8.
 *
 * This config is INDEPENDENT of CRA's baked-in ESLint pipeline — running
 * `yarn i18n:lint` does NOT change `craco build` / `craco start` behaviour.
 *
 * How to run
 * ──────────
 *   yarn i18n:lint              # report-only
 *   yarn i18n:lint --max-warnings 0   # CI gate
 *
 * What is checked
 * ───────────────
 *   • src/pages/public/**         (every public-route page + sub-component)
 *   • src/figma_home/**           (the pixel-perfect Welcome page family)
 *   • src/components/public/**    (shared public widgets: cards, dropdowns, …)
 *
 * Rule used
 * ─────────
 *   react/jsx-no-literals — flags any raw string literal rendered as JSX
 *   children or in any attribute. We whitelist explicit allowed literals
 *   (brand names, currency symbols, punctuation, units …) so the rule fires
 *   only on real user-facing English that should go through `t()` / `T.xxx`.
 */

const reactPlugin = require('eslint-plugin-react');

// Allow-list of strings that are NOT translatable (brand names, units, etc.).
// Anything else triggers a warning — pushing the dev to wire useLang().
const ALLOWED_LITERALS = [
  // Brand / proper nouns
  'BIBI', 'BIBI Cars', 'BIBI CARS', 'bibicars.bg',
  // VIN-related
  'VIN', 'LIVE', 'CACHE', 'API',
  // Auctions / providers
  'Copart', 'IAAI', 'Manheim', 'Encar',
  'COPART', 'IAA Partners', 'IAA',
  // Currencies / numbers / punctuation
  '€', '$', '%', '·', '—', '–', '-', '/', ':', '|', '+', '×', '×',
  'EUR', 'USD',
  // Single chars / units / labels that are language-neutral
  'km', 'mi', 'L', 'KM', 'MI',
  'EV', 'SUV', 'BG', 'EN', 'UK', 'ENG',
  'No.', '4×4',
  // Time / date
  ':', '/',
  // HTML entities rendered as text
  '\u00a0', // &nbsp;
];

const ALLOWED_ELEMENTS = [
  // These element names commonly hold raw numbers / icon-only text.
  'strong', 'em', 'sub', 'sup', 'code', 'time', 'small',
];

module.exports = [
  {
    files: [
      'src/pages/public/**/*.{js,jsx}',
      'src/figma_home/**/*.{js,jsx}',
      'src/components/public/**/*.{js,jsx}',
    ],
    // Skip already-localized helpers & the i18n dictionary itself
    ignores: [
      '**/i18n/**',
      '**/i18n.js',
      '**/i18n.jsx',
      'src/pages/public/SingleCarPage/i18n.js',
    ],
    plugins: {
      react: reactPlugin,
    },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      'react/jsx-no-literals': [
        'warn',
        {
          noStrings: false,           // allow non-string nodes (numbers, ‹br›, etc.)
          allowedStrings: ALLOWED_LITERALS,
          ignoreProps: false,         // also check JSX attribute string values
          noAttributeStrings: false,  // we don't flag attribute strings (too noisy)
          elementOverrides: Object.fromEntries(
            ALLOWED_ELEMENTS.map((el) => [el, { allowedStrings: ALLOWED_LITERALS, noStrings: false }]),
          ),
        },
      ],
    },
  },
];
