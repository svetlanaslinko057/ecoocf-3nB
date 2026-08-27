/**
 * Root ESLint 9 flat config.
 *
 * CRA/craco's build pipeline uses its OWN eslint configuration (see
 * craco.config.js -> eslint.configure with react-hooks rules) and does NOT
 * read this file. This flat config exists so that standalone `eslint` (v9+)
 * invocations — editors, CI checkers — have a valid configuration and can
 * parse the JSX codebase without the "no eslint.config.js found" engine error.
 *
 * The i18n-specific standalone linter lives in eslint-i18n.config.js
 * (run via `yarn i18n:lint`).
 */
const globals = require("globals");
const reactHooks = require("eslint-plugin-react-hooks");

module.exports = [
  {
    ignores: [
      "node_modules/**",
      "build/**",
      "dist/**",
      "coverage/**",
      "public/**",
    ],
  },
  {
    files: ["**/*.{js,jsx}"],
    plugins: {
      "react-hooks": reactHooks,
    },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.jest,
      },
    },
    rules: {
      /* Real lint gates run inside the CRA/craco webpack pipeline
         (react-hooks/rules-of-hooks = error, exhaustive-deps = warn).
         Keep the standalone pass syntax-only to avoid double-reporting. */
      "no-dupe-keys": "error",
      "no-undef": "off",
      "no-unused-vars": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
