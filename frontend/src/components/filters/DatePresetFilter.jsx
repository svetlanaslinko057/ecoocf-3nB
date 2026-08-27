/**
 * DatePresetFilter — reusable date-preset selector (Доопр #15).
 *
 * Presets: today, yesterday, last_7d, this_month, last_month, last_3m, all, custom.
 * On change calls `onChange({ preset, dateFrom, dateTo })` with ISO datetimes.
 */
import React, { useMemo, useState, useEffect } from 'react';
import { Calendar } from 'lucide-react';

const PRESETS = [
  { id: 'all',         labelKey: 'dateAll',        fallback: 'All time' },
  { id: 'today',       labelKey: 'dateToday',      fallback: 'Today' },
  { id: 'yesterday',   labelKey: 'dateYesterday',  fallback: 'Yesterday' },
  { id: 'last_7d',     labelKey: 'dateLast7d',     fallback: 'Last 7 days' },
  { id: 'this_month',  labelKey: 'dateThisMonth',  fallback: 'This month' },
  { id: 'last_month',  labelKey: 'dateLastMonth',  fallback: 'Last month' },
  { id: 'last_3m',     labelKey: 'dateLast3m',     fallback: 'Last 3 months' },
  { id: 'custom',      labelKey: 'dateCustom',     fallback: 'Custom…' },
];

function resolveRange(preset, customFrom, customTo) {
  const now = new Date();
  const startOfDay = (d) => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
  const endOfDay   = (d) => { const x = new Date(d); x.setHours(23,59,59,999); return x; };
  switch (preset) {
    case 'today':      return { from: startOfDay(now),  to: endOfDay(now) };
    case 'yesterday': {
      const y = new Date(now); y.setDate(y.getDate() - 1);
      return { from: startOfDay(y), to: endOfDay(y) };
    }
    case 'last_7d': {
      const f = new Date(now); f.setDate(f.getDate() - 7);
      return { from: startOfDay(f), to: endOfDay(now) };
    }
    case 'this_month': {
      const f = new Date(now.getFullYear(), now.getMonth(), 1);
      return { from: startOfDay(f), to: endOfDay(now) };
    }
    case 'last_month': {
      const f = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const t = new Date(now.getFullYear(), now.getMonth(), 0);
      return { from: startOfDay(f), to: endOfDay(t) };
    }
    case 'last_3m': {
      const f = new Date(now); f.setMonth(f.getMonth() - 3);
      return { from: startOfDay(f), to: endOfDay(now) };
    }
    case 'custom':
      return {
        from: customFrom ? startOfDay(new Date(customFrom)) : null,
        to:   customTo   ? endOfDay(new Date(customTo))   : null,
      };
    default: return { from: null, to: null };
  }
}

export default function DatePresetFilter({ value, onChange, t, testId = 'date-preset' }) {
  const tt = (key, fallback) => {
    if (!t) return fallback;
    const v = t(key);
    return (!v || v === key) ? fallback : v;
  };
  const [preset, setPreset] = useState(value?.preset || 'all');
  const [customFrom, setCustomFrom] = useState(value?.dateFrom?.slice(0,10) || '');
  const [customTo,   setCustomTo]   = useState(value?.dateTo?.slice(0,10) || '');

  const compute = useMemo(() => resolveRange(preset, customFrom, customTo), [preset, customFrom, customTo]);

  useEffect(() => {
    if (onChange) {
      onChange({
        preset,
        dateFrom: compute.from ? compute.from.toISOString() : '',
        dateTo:   compute.to   ? compute.to.toISOString()   : '',
      });
    }
    // eslint-disable-next-line
  }, [preset, customFrom, customTo]);

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={testId}>
      <Calendar className="w-3.5 h-3.5 text-[#71717A] shrink-0" />
      <select
        value={preset}
        onChange={(e) => setPreset(e.target.value)}
        className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
        data-testid={`${testId}-select`}
      >
        {PRESETS.map((p) => (
          <option key={p.id} value={p.id}>{tt(p.labelKey, p.fallback)}</option>
        ))}
      </select>
      {preset === 'custom' && (
        <>
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
            data-testid={`${testId}-from`}
          />
          <span className="text-[12px] text-[#71717A]">—</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
            data-testid={`${testId}-to`}
          />
        </>
      )}
    </div>
  );
}
