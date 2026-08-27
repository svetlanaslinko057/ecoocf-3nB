import React from 'react';
import { Check, Warning } from '@phosphor-icons/react';

/**
 * Wave 11 — linear pipeline progress bar for the Deal360 hero.
 * Renders the 9 non-cancelled stages plus a small chip listing blockers.
 */
const DealStagePipeline = ({ progress }) => {
  if (!progress) return null;
  const { stages = [], percent = 0, current_stage, is_cancelled, blockers = [], advice } = progress;

  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal-stage-pipeline">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Pipeline progress</div>
        <div className="text-[12px] font-semibold text-[#18181B] tabular-nums">
          {is_cancelled ? 'Cancelled' : `${percent}%`}
        </div>
      </div>

      {/* Progress rail */}
      <div className="relative h-2 bg-[#F4F4F5] rounded-full overflow-hidden mb-4">
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${is_cancelled ? 'bg-zinc-400' : 'bg-emerald-500'}`}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>

      {/* Stage dots */}
      <div className="flex items-center justify-between gap-1 overflow-x-auto">
        {stages.map((s) => (
          <div key={s.id} className="flex-1 min-w-[72px] flex flex-col items-center text-center">
            <div
              className={
                'w-7 h-7 rounded-full flex items-center justify-center border-2 ' +
                (s.current
                  ? 'bg-emerald-500 border-emerald-500 text-white'
                  : s.passed
                    ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                    : 'bg-white border-[#E4E4E7] text-[#A1A1AA]')
              }
              data-testid={`stage-dot-${s.id}`}
              data-current={s.current ? 'true' : 'false'}
              data-passed={s.passed ? 'true' : 'false'}
            >
              {s.passed ? <Check size={14} weight="bold" /> : null}
            </div>
            <div className={`mt-1 text-[10px] leading-tight uppercase tracking-wider font-semibold ${s.current ? 'text-emerald-700' : 'text-[#71717A]'}`}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Advice / blockers */}
      {(blockers.length || advice) ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {blockers.map((b, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
              <Warning size={12} weight="bold" /> {b}
            </span>
          ))}
          {advice ? (
            <span className="text-[12px] text-[#52525B]">{advice}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default DealStagePipeline;
