/**
 * CabinetJourney — premium customer-facing vehicle journey timeline.
 * ------------------------------------------------------------------
 * The cabinet is DARK-ONLY. To avoid the "white card on dark" bug that
 * the legacy `.section-card` class caused (it hard-codes background:white
 * and is NOT flipped by the dark-theme overrides), every surface here uses
 * EXPLICIT dark colour tokens — nothing relies on a CSS override.
 *
 * Read-only. The editable/compact stepper used by the back-office lives in
 * components/roadmap/RoadmapStepper.jsx and is intentionally left intact.
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Car, CheckCircle, Circle } from '@phosphor-icons/react';
import { ICON_BY_KEY, pickLabel, pickDescription } from '../roadmap/RoadmapStepper';
import { HelpTooltip } from '../ui/HelpTooltip';

// Brand tokens, hand-tuned for the dark cabinet surface (#17171A card).
const AMBER = '#FEAE00';
const EMERALD = '#10B981';
const TRACK = '#2A2A30';

const STATUS_LABELS = {
  done: { en: 'Done', bg: 'Готово', uk: 'Готово' },
  completed: { en: 'Done', bg: 'Готово', uk: 'Готово' },
  in_progress: { en: 'In progress', bg: 'В процес', uk: 'В роботі' },
  pending: { en: 'Upcoming', bg: 'Очаква', uk: 'Очікує' },
  blocked: { en: 'Blocked', bg: 'Блокирано', uk: 'Заблоковано' },
  skipped: { en: 'Skipped', bg: 'Пропуснат', uk: 'Пропуснато' },
};

// Plain-language explanation for each stage status — shown on hover so the
// customer always understands what a status means for their order.
const STATUS_DESC = {
  done: {
    en: 'This stage is complete.',
    bg: 'Този етап е завършен.',
    uk: 'Цей етап завершено.',
  },
  completed: {
    en: 'This stage is complete.',
    bg: 'Този етап е завършен.',
    uk: 'Цей етап завершено.',
  },
  in_progress: {
    en: 'We are working on this stage right now.',
    bg: 'В момента работим по този етап.',
    uk: 'Зараз ми працюємо над цим етапом.',
  },
  pending: {
    en: 'This stage is still ahead — not started yet.',
    bg: 'Този етап предстои — все още не е започнат.',
    uk: 'Цей етап ще попереду — поки не розпочато.',
  },
  blocked: {
    en: 'This stage is on hold — our team is resolving something and will keep you posted.',
    bg: 'Етапът е спрян — екипът ни решава въпрос и ще ви уведоми.',
    uk: 'Етап призупинено — наша команда вирішує питання й повідомить вас.',
  },
  skipped: {
    en: 'This stage was skipped — it is not needed for your order.',
    bg: 'Този етап е пропуснат — не е необходим за вашата поръчка.',
    uk: 'Цей етап пропущено — він не потрібен для вашого замовлення.',
  },
};

const fmtDate = (iso, lang) => {
  if (!iso) return '';
  try {
    const loc = lang === 'uk' ? 'uk-UA' : 'en-US';
    return new Date(iso).toLocaleDateString(loc, { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return ''; }
};

const norm = (s) => (s || 'pending').toLowerCase();

// ── Circular progress ring (SVG, explicit dark colours) ──────────────────
const ProgressRing = ({ pct = 0 }) => {
  const r = 30;
  const circ = 2 * Math.PI * r;
  const off = circ - (Math.max(0, Math.min(100, pct)) / 100) * circ;
  return (
    <div className="relative w-[78px] h-[78px] shrink-0" data-testid="journey-progress-ring">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={r} fill="none" stroke={TRACK} strokeWidth="6" />
        <defs>
          <linearGradient id="bibiJourneyGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={AMBER} />
            <stop offset="100%" stopColor={EMERALD} />
          </linearGradient>
        </defs>
        <motion.circle
          cx="38" cy="38" r={r} fill="none" stroke="url(#bibiJourneyGrad)"
          strokeWidth="6" strokeLinecap="round" strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: off }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[17px] font-bold text-zinc-100 tabular-nums leading-none">{pct}%</span>
      </div>
    </div>
  );
};

// ── Single timeline stage ────────────────────────────────────────────────
const StageRow = ({ stage, lang, isLast, index }) => {
  const status = norm(stage.status);
  const isDone = status === 'done' || status === 'completed';
  const isCurrent = status === 'in_progress';
  const isBlocked = status === 'blocked';
  const Icon = ICON_BY_KEY[stage.icon] || Circle;
  const label = pickLabel(stage, lang);
  const desc = pickDescription(stage, lang);
  const sLabel = (STATUS_LABELS[status] || STATUS_LABELS.pending)[lang]
    || (STATUS_LABELS[status] || STATUS_LABELS.pending).en;
  const sDesc = (STATUS_DESC[status] || STATUS_DESC.pending)[lang]
    || (STATUS_DESC[status] || STATUS_DESC.pending).en;
  const date = stage.completed_at || stage.started_at;

  let node = 'bg-[#222227] border border-[#34343A] text-zinc-500';
  let pill = 'bg-[#222227] text-zinc-400 border border-[#34343A]';
  if (isDone) {
    node = 'bg-emerald-500 border border-emerald-400 text-white shadow-[0_4px_14px_rgba(16,185,129,0.35)]';
    pill = 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
  } else if (isCurrent) {
    node = 'bg-[#FEAE00]/15 border-2 border-[#FEAE00] text-[#FEAE00]';
    pill = 'bg-[#FEAE00]/15 text-[#FEAE00] border border-[#FEAE00]/40';
  } else if (isBlocked) {
    node = 'bg-red-500/15 border-2 border-red-500 text-red-400';
    pill = 'bg-red-500/15 text-red-400 border border-red-500/30';
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.05 * index, duration: 0.3 }}
      className="flex gap-4"
      data-testid={`journey-stage-${stage.key}`}
    >
      {/* Rail: node + connector */}
      <div className="flex flex-col items-center">
        <div className={`relative w-11 h-11 rounded-2xl flex items-center justify-center transition-colors ${node}`}>
          {isDone
            ? <CheckCircle size={22} weight="fill" />
            : <Icon size={20} weight="duotone" />}
          {isCurrent && (
            <span className="absolute inset-0 rounded-2xl border-2 border-[#FEAE00] animate-ping opacity-40" />
          )}
        </div>
        {!isLast && (
          <div className="w-[2px] flex-1 min-h-[34px] my-1 rounded-full"
            style={{ background: isDone ? EMERALD : TRACK }} />
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${isLast ? 'pb-0' : 'pb-6'}`}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className={`text-[15px] font-semibold leading-tight ${isCurrent ? 'text-[#FEAE00]' : 'text-zinc-100'}`}>
            {label}
          </h3>
          <HelpTooltip text={sDesc}>
            <span className={`text-[10.5px] px-2 py-0.5 rounded-full font-medium cursor-help ${pill}`} data-testid={`journey-status-${stage.key}`}>
              {sLabel}
            </span>
          </HelpTooltip>
          {stage.sla_breached && !isDone && (
            <span className="text-[10.5px] px-2 py-0.5 rounded-full font-medium bg-red-500/15 text-red-400 border border-red-500/30">
              SLA
            </span>
          )}
        </div>

        {date && (
          <p className="text-xs text-zinc-500 mt-1 tabular-nums">{fmtDate(date, lang)}</p>
        )}

        {/* Current stage — rich description panel */}
        {isCurrent && desc && (
          <div className="mt-3 rounded-xl border border-[#FEAE00]/25 bg-[#FEAE00]/[0.07] px-4 py-3">
            <p className="text-sm text-zinc-100 leading-relaxed">{desc}</p>
            {stage.eta && (
              <p className="text-xs text-zinc-400 mt-2">
                {lang === 'uk' ? 'Очікуваний термін' : 'Expected'}:{' '}
                <span className="font-semibold text-[#FEAE00]">{fmtDate(stage.eta, lang) || stage.eta}</span>
              </p>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};

const L = {
  completed: { en: 'completed', bg: 'завършено', uk: 'завершено' },
  done_banner: {
    en: 'Congratulations — your vehicle has been handed over. Enjoy the road!',
    bg: 'Честито — вашият автомобил вече е във ваши ръце. Приятно каране!',
    uk: 'Вітаємо — ваш автомобіль передано вам. Гарної дороги!',
  },
  vehicle: { en: 'My vehicle', bg: 'Моят автомобил', uk: 'Мій автомобіль' },
};
const pick = (m, lang) => m[lang] || m.en;

// ── Main card ─────────────────────────────────────────────────────────────
const CabinetJourney = ({ roadmap, stageTemplate = [], lang = 'en' }) => {
  const stages = useMemo(() => {
    const tplByKey = Object.fromEntries((stageTemplate || []).map((s) => [s.key, s]));
    return (roadmap?.stages || []).map((s) => ({ ...(tplByKey[s.key] || {}), ...s }));
  }, [roadmap, stageTemplate]);

  if (!roadmap || stages.length === 0) return null;

  const pct = roadmap.progress_pct || 0;
  const completed = roadmap.status === 'completed';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="bg-[#17171A] border border-[#27272A] rounded-2xl overflow-hidden"
      data-testid={`cabinet-journey-${roadmap.id}`}
    >
      {/* Header with subtle amber accent line */}
      <div className="relative p-5 sm:p-6 border-b border-[#27272A]">
        <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-[#FEAE00] via-[#FEAE00]/50 to-transparent" />
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-2xl bg-[#FEAE00]/15 border border-[#FEAE00]/30 flex items-center justify-center shrink-0">
              <Car size={22} weight="duotone" className="text-[#FEAE00]" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-bold text-zinc-100 truncate">
                {roadmap.title || (roadmap.vehicle && roadmap.vehicle.name) || pick(L.vehicle, lang)}
              </h2>
              {roadmap.vehicle && roadmap.vehicle.vin && (
                <p className="text-xs font-mono text-zinc-500 truncate mt-0.5">VIN: {roadmap.vehicle.vin}</p>
              )}
            </div>
          </div>
          <div className="flex flex-col items-center shrink-0">
            <ProgressRing pct={pct} />
            <span className="text-[10px] uppercase tracking-[0.14em] text-zinc-500 mt-1.5 font-semibold">
              {pick(L.completed, lang)}
            </span>
          </div>
        </div>
      </div>

      {/* Vertical timeline */}
      <div className="p-5 sm:p-6">
        {stages.map((st, i) => (
          <StageRow
            key={st.key}
            stage={st}
            lang={lang}
            index={i}
            isLast={i === stages.length - 1}
          />
        ))}
      </div>

      {completed && (
        <div className="mx-5 sm:mx-6 mb-5 sm:mb-6 -mt-1 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center gap-3">
          <CheckCircle size={22} weight="fill" className="text-emerald-400 shrink-0" />
          <p className="text-sm text-zinc-100 font-medium">{pick(L.done_banner, lang)}</p>
        </div>
      )}
    </motion.div>
  );
};

export default CabinetJourney;
