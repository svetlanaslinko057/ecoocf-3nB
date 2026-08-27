/**
 * RoadmapStepper — Sprint 3.5
 * ---------------------------
 * Reusable presentational component that renders a single roadmap as a
 * 7-stage stepper. Used by the Customer Cabinet (read-only), the
 * Customer360 admin tab (editable), and the Team / Admin analytics
 * tables (compact mode).
 *
 * Props:
 *   roadmap            — roadmap doc from the API
 *   stageTemplate      — list of `{key, label_en, label_uk, label_bg, ...}`
 *   lang               — currently-active language code (en/bg/uk)
 *   onStageClick(stage) optional click handler (used by Customer360 editor)
 *   compact            — if true, render in a single horizontal strip with no notes
 */
import React, { useMemo } from 'react';
import {
  MagnifyingGlass,
  Coins,
  Boat,
  MapPin,
  Wrench,
  Stamp,
  Key,
  CheckCircle,
  WarningCircle,
  CircleNotch,
  Circle,
  CaretRight,
} from '@phosphor-icons/react';

const ICON_BY_KEY = {
  MagnifyingGlass,
  Coins,
  Boat,
  MapPin,
  Wrench,
  Stamp,
  Key,
};

const STATUS_META = {
  pending: {
    pill: 'bg-zinc-100 text-zinc-600 border-zinc-200',
    ring: 'border-zinc-200 bg-zinc-50',
    icon: Circle,
    iconClass: 'text-zinc-400',
    label: { en: 'Pending', uk: 'Очікує', bg: 'Очаква' },
  },
  in_progress: {
    pill: 'bg-amber-100 text-amber-700 border-amber-200',
    ring: 'border-amber-300 bg-amber-50',
    icon: CircleNotch,
    iconClass: 'text-amber-500 animate-spin',
    label: { en: 'In progress', uk: 'В роботі', bg: 'В процес' },
  },
  done: {
    pill: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    ring: 'border-emerald-300 bg-emerald-50',
    icon: CheckCircle,
    iconClass: 'text-emerald-500',
    label: { en: 'Done', uk: 'Готово', bg: 'Готово' },
  },
  completed: {
    pill: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    ring: 'border-emerald-300 bg-emerald-50',
    icon: CheckCircle,
    iconClass: 'text-emerald-500',
    label: { en: 'Done', uk: 'Готово', bg: 'Готово' },
  },
  blocked: {
    pill: 'bg-red-100 text-red-700 border-red-200',
    ring: 'border-red-300 bg-red-50',
    icon: WarningCircle,
    iconClass: 'text-red-500',
    label: { en: 'Blocked', uk: 'Заблоковано', bg: 'Блокирано' },
  },
  skipped: {
    pill: 'bg-zinc-100 text-zinc-500 border-zinc-200',
    ring: 'border-zinc-200 bg-zinc-50',
    icon: CaretRight,
    iconClass: 'text-zinc-400',
    label: { en: 'Skipped', uk: 'Пропущено', bg: 'Пропуснат' },
  },
};

const pickLabel = (stage, lang) => {
  if (!stage) return '';
  const order = [lang, 'en', 'uk', 'bg'];
  for (const code of order) {
    const v = stage[`label_${code}`];
    if (v) return v;
  }
  return stage.label || stage.key;
};
const pickDescription = (stage, lang) => {
  if (!stage) return '';
  const order = [lang, 'en', 'uk', 'bg'];
  for (const code of order) {
    const v = stage[`description_${code}`];
    if (v) return v;
  }
  return '';
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString(); } catch { return ''; }
};

const RoadmapStepper = ({
  roadmap,
  stageTemplate = [],
  lang = 'en',
  onStageClick,
  compact = false,
}) => {
  const stages = useMemo(() => {
    const tplByKey = Object.fromEntries((stageTemplate || []).map((s) => [s.key, s]));
    return (roadmap?.stages || []).map((s) => ({
      ...(tplByKey[s.key] || {}),
      ...s,
    }));
  }, [roadmap, stageTemplate]);

  if (!roadmap || stages.length === 0) return null;

  if (compact) {
    return (
      <div className="flex items-center gap-1 overflow-x-auto" data-testid={`roadmap-compact-${roadmap.id}`}>
        {stages.map((st) => {
          const meta = STATUS_META[(st.status || 'pending').toLowerCase()] || STATUS_META.pending;
          const Icon = ICON_BY_KEY[st.icon] || Circle;
          return (
            <div
              key={st.key}
              className={`shrink-0 w-7 h-7 rounded-full border flex items-center justify-center ${meta.ring}`}
              title={pickLabel(st, lang)}
            >
              <Icon size={14} className={meta.iconClass.replace('animate-spin', '')} />
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid={`roadmap-stepper-${roadmap.id}`}>
      {/* Connector line + dots row */}
      <div className="relative">
        <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[2px] bg-zinc-200" />
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-[2px] bg-emerald-500 transition-all"
          style={{ width: `${roadmap.progress_pct || 0}%` }}
        />
        <div className="relative grid" style={{ gridTemplateColumns: `repeat(${stages.length}, 1fr)` }}>
          {stages.map((st) => {
            const meta = STATUS_META[(st.status || 'pending').toLowerCase()] || STATUS_META.pending;
            const Icon = ICON_BY_KEY[st.icon] || Circle;
            const breached = st.sla_breached;
            return (
              <div key={st.key} className="flex justify-center">
                <button
                  type="button"
                  onClick={onStageClick ? () => onStageClick(st) : undefined}
                  disabled={!onStageClick}
                  className={`relative w-10 h-10 rounded-full border-2 bg-white flex items-center justify-center transition-transform ${meta.ring} ${onStageClick ? 'hover:scale-110 cursor-pointer' : 'cursor-default'}`}
                  data-testid={`stage-dot-${st.key}`}
                  title={pickLabel(st, lang)}
                >
                  <Icon size={18} className={meta.iconClass} weight="duotone" />
                  {breached && (
                    <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full ring-2 ring-white" />
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Labels row */}
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${stages.length}, 1fr)` }}>
        {stages.map((st) => {
          const label = pickLabel(st, lang);
          const meta = STATUS_META[(st.status || 'pending').toLowerCase()] || STATUS_META.pending;
          const sLabel = meta.label[lang] || meta.label.en;
          return (
            <div key={st.key} className="text-center px-1">
              <p className="text-[10.5px] sm:text-xs font-semibold text-zinc-800 leading-tight">
                {label}
              </p>
              <p className={`text-[10px] mt-0.5 inline-block px-1.5 py-0.5 rounded-full border ${meta.pill}`}>
                {sLabel}
              </p>
              {st.completed_at && (
                <p className="text-[9.5px] text-zinc-400 mt-0.5">{fmtDate(st.completed_at)}</p>
              )}
              {st.sla_breached && !st.completed_at && (
                <p className="text-[9.5px] text-red-500 mt-0.5 font-medium">SLA ❕</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Current stage card */}
      {roadmap.current_stage && (() => {
        const cur = stages.find((s) => s.key === roadmap.current_stage);
        if (!cur) return null;
        const desc = pickDescription(cur, lang);
        return (
          <div className="mt-4 p-4 rounded-xl bg-gradient-to-br from-amber-50 to-white border border-amber-200">
            <div className="flex items-start gap-3">
              <div className="shrink-0 w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                {(() => { const I = ICON_BY_KEY[cur.icon] || Circle; return <I size={20} className="text-amber-600" weight="duotone" />; })()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] uppercase tracking-wider font-bold text-amber-700">
                  {lang === 'uk' ? 'Поточний етап' : 'Current stage'}
                </p>
                <p className="font-semibold text-zinc-900 mt-0.5">{pickLabel(cur, lang)}</p>
                {desc && <p className="text-sm text-zinc-700 mt-1">{desc}</p>}
                {cur.eta && (
                  <p className="text-xs text-zinc-600 mt-2">
                    {lang === 'uk' ? 'Очікуваний термін' : 'Expected'}: <span className="font-medium text-zinc-900">{fmtDate(cur.eta) || cur.eta}</span>
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default RoadmapStepper;
export { STATUS_META, ICON_BY_KEY, pickLabel, pickDescription };
