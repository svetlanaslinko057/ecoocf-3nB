/**
 * <Overview360 /> — переиспользуемый Customer-Dashboard layout.
 *
 * Используется в:
 *   Customer360 → Overview tab        (W1, сейчас)
 *   Deal360   → Overview tab          (W4+, тот же компонент)
 *   Manager360 / TeamLead360          (W2+, тот же компонент)
 *
 * Принцип: компонент чистый view-only, ничего не fetch'ит. Все данные
 * приходят через props. Это даёт одинаковый UX поверх разных backend-
 * агрегаторов.
 *
 * Секции (фиксированный порядок):
 *   1. Health     — большой чип + breakdown
 *   2. Last/Next  — последний контакт + AI-предложение
 *   3. Risks      — список текстовых рисков
 *   4. OpenItems  — открытые задачи и сделки
 *   5. Recent     — компактный feed последних 5 событий
 */
import React from 'react';
import HealthChip from '../health/HealthChip';
import { useLang } from '../../i18n';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';

const HoverTip = ({ text, children, side = 'top' }) => {
  if (!text) return children;
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side} className="max-w-xs bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const fmtDate = (v) => {
  if (!v) return '—';
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
};

function SectionCard({ title, titleTip, icon: Icon, children, testId }) {
  const { t } = useLang();
  void t;
  return (
    <section
      data-testid={testId}
      className="bg-white border border-[#E4E4E7] rounded-2xl p-5 shadow-sm"
    >
      <header className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="w-4 h-4 text-[#52525B]" />}
        <HoverTip text={titleTip}>
          <h3 className="text-[13px] font-semibold uppercase tracking-wider text-[#52525B] cursor-default">
            {title}
          </h3>
        </HoverTip>
      </header>
      <div>{children}</div>
    </section>
  );
}

/**
 * Props:
 *   health         : { score, segment, breakdown, risks } | null
 *   lastContact    : { at, channel, manager, outcome } | null
 *   nextAction     : { text, source } | null      ← source = 'ai' | 'rule'
 *   openTasks      : Array<{ id, title, due_at, priority }>
 *   openDeals      : Array<{ id, title, stage, amount, currency }>
 *   recentActivity : Array<{ at, type, title, meta? }>
 */
export default function Overview360({
  health,
  lastContact,
  nextAction,
  openTasks = [],
  openDeals = [],
  recentActivity = [],
}) {
  const { t } = useLang();

  return (
    <div className="space-y-4" data-testid="overview-360">
      {/* 1. Health */}
      <SectionCard
        title={t('overview_health_title')}
        titleTip={t('overview_health_tooltip')}
        testId="overview-section-health"
      >
        {health ? (
          <div className="flex flex-wrap items-center gap-4">
            <HealthChip
              size="lg"
              score={health.score}
              segment={health.segment}
              risks={health.risks}
              breakdown={health.breakdown}
            />
            {health.breakdown && (
              <div className="flex-1 min-w-[260px] grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {[
                  ['activity',      t('health_sub_activity')],
                  ['engagement',    t('health_sub_engagement')],
                  ['financial',     t('health_sub_financial')],
                  ['deal_progress', t('health_sub_deal_progress')],
                  ['documents',     t('health_sub_documents')],
                ].map(([k, label]) => {
                  const v = Math.max(0, Math.min(100, Number(health.breakdown[k] || 0)));
                  return (
                    <HoverTip key={k} text={`${label}: ${v}/100`}>
                      <div className="px-2 py-1.5 bg-zinc-50 border border-[#E4E4E7] rounded-lg cursor-default">
                        <div className="text-[9.5px] uppercase tracking-wider text-[#71717A]">{label}</div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-xs font-bold tabular-nums text-[#18181B]">{v}</span>
                          <span className="flex-1 h-1.5 rounded-full bg-zinc-200 overflow-hidden">
                            <span className="block h-full bg-[#18181B]" style={{ width: `${v}%` }} />
                          </span>
                        </div>
                      </div>
                    </HoverTip>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-zinc-400">{t('overview_health_loading')}</p>
        )}
      </SectionCard>

      {/* 2 & 3 row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard
          title={t('overview_last_contact_title')}
          titleTip={t('overview_last_contact_tooltip')}
          testId="overview-section-last-contact"
        >
          {lastContact ? (
            <div className="text-sm space-y-1">
              <div className="font-medium text-[#18181B]">{fmtDate(lastContact.at)}</div>
              <div className="text-xs text-[#71717A]">
                {lastContact.channel && <span>{lastContact.channel} · </span>}
                {lastContact.manager && <span>{lastContact.manager} · </span>}
                {lastContact.outcome && <span className="font-medium text-[#18181B]">{lastContact.outcome}</span>}
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-400">{t('overview_no_contact')}</p>
          )}
        </SectionCard>

        <SectionCard
          title={t('overview_next_action_title')}
          titleTip={t('overview_next_action_tooltip')}
          testId="overview-section-next-action"
        >
          {nextAction ? (
            <div className="space-y-1">
              <p className="text-sm text-[#18181B]">{nextAction.text}</p>
              {nextAction.source === 'ai' && (
                <p className="text-[10.5px] uppercase tracking-wider text-[#7C3AED] font-semibold">
                  {t('overview_next_action_ai')}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-zinc-400">{t('overview_next_action_none')}</p>
          )}
        </SectionCard>
      </div>

      {/* 4. Risks + Open items */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard
          title={t('overview_risks_title')}
          titleTip={t('overview_risks_tooltip')}
          testId="overview-section-risks"
        >
          {health?.risks?.length ? (
            <ul className="space-y-1.5">
              {health.risks.map((r, i) => (
                <li key={i} className="text-sm text-[#18181B] flex items-start gap-2">
                  <span aria-hidden className="text-amber-600">⚠</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-emerald-600 font-medium">{t('overview_no_risks')}</p>
          )}
        </SectionCard>

        <SectionCard
          title={t('overview_open_items_title')}
          titleTip={t('overview_open_items_tooltip')}
          testId="overview-section-open-items"
        >
          <div className="space-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-[#71717A] mb-1 font-semibold">
                {t('overview_open_tasks')} ({openTasks.length})
              </div>
              {openTasks.length ? (
                <ul className="space-y-1">
                  {openTasks.slice(0, 4).map((task) => (
                    <li key={task.id} className="text-sm flex justify-between gap-2">
                      <span className="text-[#18181B] truncate">{task.title}</span>
                      <span className="text-xs text-[#71717A] shrink-0">{fmtDate(task.due_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-400">{t('overview_no_tasks')}</p>
              )}
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-[#71717A] mb-1 font-semibold">
                {t('overview_open_deals')} ({openDeals.length})
              </div>
              {openDeals.length ? (
                <ul className="space-y-1">
                  {openDeals.slice(0, 4).map((deal) => (
                    <li key={deal.id} className="text-sm flex justify-between gap-2">
                      <span className="text-[#18181B] truncate">{deal.title}</span>
                      <span className="text-xs text-[#71717A] tabular-nums shrink-0">
                        {deal.amount ? `${Number(deal.amount).toLocaleString()} ${deal.currency || ''}` : deal.stage || '—'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-400">{t('overview_no_deals')}</p>
              )}
            </div>
          </div>
        </SectionCard>
      </div>

      {/* 5. Recent activity */}
      <SectionCard
        title={t('overview_recent_title')}
        titleTip={t('overview_recent_tooltip')}
        testId="overview-section-recent"
      >
        {recentActivity.length ? (
          <ul className="divide-y divide-[#F4F4F5]">
            {recentActivity.slice(0, 5).map((ev, i) => (
              <li key={i} className="py-2 flex items-start justify-between gap-3 text-sm">
                <div className="min-w-0">
                  <p className="text-[#18181B] truncate">{ev.title}</p>
                  {ev.meta && <p className="text-xs text-[#71717A] truncate">{ev.meta}</p>}
                </div>
                <span className="text-xs text-[#71717A] shrink-0 whitespace-nowrap">{fmtDate(ev.at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-400">{t('overview_recent_empty')}</p>
        )}
      </SectionCard>
    </div>
  );
}
