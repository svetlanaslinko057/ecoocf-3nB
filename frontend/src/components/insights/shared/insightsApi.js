/**
 * insightsApi.js
 * Shared API helpers + role-aware fetch utilities for /insights hub.
 *
 * Every helper:
 *  - returns { data, error } (never throws)
 *  - automatically scopes by role on the BACKEND (which already filters by actor)
 *  - logs nothing in production (keep DevTools clean)
 */
import axios from 'axios';
import { API_URL } from '../../../App';

/** Safely call an endpoint, returning a normalised tuple. */
export async function safeGet(path, params) {
  try {
    const res = await axios.get(`${API_URL}${path}`, { params });
    return { data: res.data, error: null };
  } catch (err) {
    return { data: null, error: err?.response?.data?.detail || err?.message || 'error' };
  }
}

/** Resolve the user's effective scope label for /insights pages. */
export function scopeForRole(role) {
  if (role === 'master_admin' || role === 'admin' || role === 'moderator') return 'company';
  if (role === 'team_lead') return 'team';
  return 'personal';
}

/** Tabs available to each role. */
export function tabsForRole(role) {
  const all = ['traffic', 'pipeline', 'revenue', 'team', 'risk'];
  if (role === 'manager') return ['traffic', 'pipeline', 'revenue', 'risk'];
  return all;
}

/** Format big numbers in compact form (12345 → 12.3K). */
export function fmtCompact(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const num = Number(n);
  if (Math.abs(num) >= 1_000_000) return (num / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (Math.abs(num) >= 1_000) return (num / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  if (Number.isInteger(num)) return String(num);
  return num.toFixed(1);
}

/** Format currency without trailing zeros. */
export function fmtMoney(n, currency = 'USD') {
  if (n === null || n === undefined || isNaN(n)) return '—';
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `$${fmtCompact(n)}`;
  }
}

/** Format percent. */
export function fmtPct(n, digits = 0) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return `${Number(n).toFixed(digits)}%`;
}

/** Days → "Xd" or "Xh" if < 1d. */
export function fmtDuration(days) {
  if (days === null || days === undefined || isNaN(days)) return '—';
  const d = Number(days);
  if (d >= 1) return `${d.toFixed(d >= 10 ? 0 : 1)}d`;
  return `${Math.max(0, Math.round(d * 24))}h`;
}

/** Risk-band color helper (returns Tailwind utility classes). */
export function riskBandClass(score) {
  if (score === null || score === undefined || isNaN(score)) return { text: 'text-zinc-600', bg: 'bg-zinc-100', border: 'border-zinc-300' };
  const s = Number(score);
  if (s < 40) return { text: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-300' };
  if (s < 70) return { text: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-300' };
  return { text: 'text-red-700', bg: 'bg-red-50', border: 'border-red-300' };
}

/** Delta visual helper. */
export function deltaClass(delta) {
  if (delta === null || delta === undefined || isNaN(delta)) return 'text-zinc-500';
  const d = Number(delta);
  if (d > 0) return 'text-emerald-700';
  if (d < 0) return 'text-red-700';
  return 'text-zinc-500';
}
