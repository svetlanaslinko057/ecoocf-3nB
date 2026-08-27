/**
 * <HealthChip /> — переиспользуемая бейдж-«пилюля» Health Score.
 *
 * Где живёт:
 *   • Customer360 — большой вариант в шапке с breakdown
 *   • Customers list — компактная колонка
 *   • Team Lead Dashboard — md вариант рядом с именем клиента
 *
 * AC#11: одно и то же значение `score` отдают все три экрана из одной
 * backend-функции `CustomerHealthService.full()/bulk()`.
 *
 * Сегменты:
 *   hot   80-100  🔥 emerald
 *   warm  60-79   ☀️ amber
 *   cold  30-59   ❄️ blue
 *   lost  0-29    ⚫ zinc
 */
import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { useLang } from '../../i18n';

const SEGMENT_CFG = {
  hot:  { emoji: '🔥', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', ring: '#10B981', labelKey: 'health_seg_hot'  },
  warm: { emoji: '☀️', cls: 'bg-amber-50   text-amber-700   border-amber-200',   ring: '#F59E0B', labelKey: 'health_seg_warm' },
  cold: { emoji: '❄️', cls: 'bg-sky-50     text-sky-700     border-sky-200',     ring: '#0EA5E9', labelKey: 'health_seg_cold' },
  lost: { emoji: '⚫', cls: 'bg-zinc-100   text-zinc-600   border-zinc-200',     ring: '#71717A', labelKey: 'health_seg_lost' },
};

const SIZE = {
  xs: { px: 'px-1.5 py-0.5',  text: 'text-[10px]', emoji: 'text-[10px]' },
  sm: { px: 'px-2 py-0.5',    text: 'text-[11px]', emoji: 'text-xs' },
  md: { px: 'px-2.5 py-1',    text: 'text-xs',     emoji: 'text-sm' },
  lg: { px: 'px-3 py-1.5',    text: 'text-sm',     emoji: 'text-base' },
};

function HealthChipInner({ score, segment, size, t }) {
  const seg = SEGMENT_CFG[segment] || SEGMENT_CFG.lost;
  const s = SIZE[size] || SIZE.sm;
  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold border rounded-full whitespace-nowrap tabular-nums ${seg.cls} ${s.px} ${s.text}`}
      data-testid="health-chip"
      data-score={score}
      data-segment={segment}
    >
      <span className={s.emoji} aria-hidden>{seg.emoji}</span>
      <span>{score}</span>
      <span className="opacity-70 uppercase tracking-wider">{t(seg.labelKey)}</span>
    </span>
  );
}

/**
 * Props:
 *   score    : number 0..100
 *   segment  : 'hot' | 'warm' | 'cold' | 'lost'
 *   size     : 'xs' | 'sm' | 'md' | 'lg'  (default 'sm')
 *   risks    : optional string[] — shown as hover tooltip
 *   breakdown: optional { activity, engagement, financial, deal_progress, documents, risk_penalty }
 *              — when present the tooltip shows a mini bar-chart
 */
export default function HealthChip({
  score = 0,
  segment = 'lost',
  size = 'sm',
  risks = [],
  breakdown = null,
  withTooltip = true,
}) {
  const { t } = useLang();
  const chip = <HealthChipInner score={score} segment={segment} size={size} t={t} />;
  if (!withTooltip) return chip;

  // Tooltip body — без иконок, появляется при наведении на сам чип.
  const tip = (
    <div className="space-y-1.5 min-w-[180px]">
      <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
        {t('health_tooltip_title')}
      </div>
      {breakdown ? (
        <div className="space-y-1">
          {[
            ['activity',      t('health_sub_activity')],
            ['engagement',    t('health_sub_engagement')],
            ['financial',     t('health_sub_financial')],
            ['deal_progress', t('health_sub_deal_progress')],
            ['documents',     t('health_sub_documents')],
          ].map(([k, label]) => {
            const v = Math.max(0, Math.min(100, Number(breakdown[k] || 0)));
            return (
              <div key={k} className="flex items-center gap-2">
                <span className="text-[10.5px] w-20 opacity-80">{label}</span>
                <span className="flex-1 h-1.5 rounded-full bg-white/15 overflow-hidden">
                  <span className="block h-full bg-white" style={{ width: `${v}%` }} />
                </span>
                <span className="text-[10.5px] tabular-nums w-7 text-right">{v}</span>
              </div>
            );
          })}
          {breakdown.risk_penalty != null && (
            <div className="flex items-center gap-2 pt-1 mt-1 border-t border-white/15">
              <span className="text-[10.5px] w-20 opacity-80">{t('health_sub_risk_penalty')}</span>
              <span className="text-[10.5px] tabular-nums w-7 text-right">{breakdown.risk_penalty}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="text-[11px] opacity-80">{t('health_tooltip_no_data')}</div>
      )}
      {risks && risks.length > 0 && (
        <div className="pt-1.5 mt-1.5 border-t border-white/15 space-y-0.5">
          {risks.slice(0, 4).map((r, i) => (
            <div key={i} className="text-[11px]">⚠ {r}</div>
          ))}
          {risks.length > 4 && (
            <div className="text-[10.5px] opacity-70">+{risks.length - 4} {t('health_more')}</div>
          )}
        </div>
      )}
    </div>
  );

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>{chip}</TooltipTrigger>
        <TooltipContent
          side="top"
          className="max-w-sm bg-[#18181B] text-white px-3 py-2 rounded-lg shadow-lg"
        >
          {tip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
