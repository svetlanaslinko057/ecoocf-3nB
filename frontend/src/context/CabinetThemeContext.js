/**
 * CabinetThemeContext — DARK-ONLY (Phase B3.1 hardening)
 *
 * Previous build had a `light` / `dark` toggle. Per stakeholder directive
 * 2026-05-24: "By default we remove the white version and the version
 * picker. The dark one is the default and that's it — there is no other
 * logic." The provider is preserved (so consumers don't blow up) but it
 * now always reports `dark` and ignores any historical
 * `localStorage.bibi_cabinet_theme = 'light'` value.
 */

import React, { createContext, useContext, useEffect } from 'react';

const STORAGE_KEY = 'bibi_cabinet_theme';
const FIXED_THEME = 'dark';

const CabinetThemeContext = createContext(null);

export const CabinetThemeProvider = ({ children }) => {
  useEffect(() => {
    // Migration: wipe any legacy stored value so user history doesn't
    // surface the white theme through a stale key.
    try { localStorage.setItem(STORAGE_KEY, FIXED_THEME); } catch { /* ignore */ }
  }, []);

  // Hard-coded surface. `setTheme` / `toggleTheme` are kept for backwards
  // compatibility but they are no-ops on purpose — there is no other theme.
  const value = {
    theme: FIXED_THEME,
    isDark: true,
    setTheme: () => {},
    toggleTheme: () => {},
  };

  return (
    <CabinetThemeContext.Provider value={value}>
      {children}
    </CabinetThemeContext.Provider>
  );
};

export const useCabinetTheme = () => {
  const ctx = useContext(CabinetThemeContext);
  if (!ctx) {
    return { theme: FIXED_THEME, setTheme: () => {}, toggleTheme: () => {}, isDark: true };
  }
  return ctx;
};

export default CabinetThemeContext;
