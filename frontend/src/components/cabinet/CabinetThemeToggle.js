import React from 'react';
import { Sun, Moon } from '@phosphor-icons/react';
import { useCabinetTheme } from '../../context/CabinetThemeContext';

/**
 * CabinetThemeToggle — Sun / Moon segmented pill.
 *
 * Used inside the cabinet to switch between `light` and `dark` visuals.
 * Purely decorative wrapper — all state lives in CabinetThemeContext,
 * and dark overrides are applied via CSS on [data-theme="dark"].
 *
 * Variants:
 *   • full (default) — shows both icons side-by-side (segmented control)
 *   • compact        — single button that swaps its icon
 */
const CabinetThemeToggle = ({ variant = 'full', className = '' }) => {
  const { theme, setTheme, toggleTheme } = useCabinetTheme();

  if (variant === 'compact') {
    const isDark = theme === 'dark';
    return (
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
        title={isDark ? 'Light mode' : 'Dark mode'}
        className={`inline-flex items-center justify-center w-9 h-9 rounded-full border transition-colors
          ${isDark
            ? 'border-[#2C2C30] bg-[#141416] text-[#FEAE00] hover:border-[#FEAE00]/60'
            : 'border-[#E4E4E7] bg-white text-[#71717A] hover:text-[#18181B]'}
          ${className}`}
        data-testid="cabinet-theme-toggle-compact"
      >
        {isDark ? <Sun size={16} weight="fill" /> : <Moon size={16} weight="fill" />}
      </button>
    );
  }

  return (
    <div
      className={`cabinet-theme-toggle ${className}`}
      role="group"
      aria-label="Theme"
      data-testid="cabinet-theme-toggle"
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        data-active={theme === 'light'}
        aria-pressed={theme === 'light'}
        aria-label="Light theme"
        title="Light"
        data-testid="cabinet-theme-light"
      >
        <Sun size={14} weight="fill" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('dark')}
        data-active={theme === 'dark'}
        aria-pressed={theme === 'dark'}
        aria-label="Dark theme"
        title="Dark"
        data-testid="cabinet-theme-dark"
      >
        <Moon size={14} weight="fill" />
      </button>
    </div>
  );
};

export default CabinetThemeToggle;
