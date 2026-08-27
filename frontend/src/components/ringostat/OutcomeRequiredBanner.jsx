/**
 * Outcome Required Banner
 * 
 * Persistent banner для звонков > 30s без outcome
 * Блокирует navigation и требует заполнения результата
 */

import React, { useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, X } from 'lucide-react';
import { useLang } from '../../i18n';

export const OutcomeRequiredBanner = ({ calls, onFillOutcome, dismissible = false }) => {
  const { t } = useLang();
  const [dismissed, setDismissed] = useState(false);
  const callsNeedingOutcome = calls.filter(call =>
    !call.outcome &&
    call.duration > 30 &&
    call.status === 'ANSWERED'
  );

  if (callsNeedingOutcome.length === 0) return null;
  if (dismissible && dismissed) return null;

  // When dismissible (admin / team lead override), use a softer "info"
  // styling instead of pulsing red.  Managers always see the red banner.
  const containerCls = dismissible
    ? "fixed bottom-0 left-0 right-0 z-50 p-3 bg-slate-700 text-white shadow-xl"
    : "fixed bottom-0 left-0 right-0 z-50 p-4 bg-red-600 text-white shadow-2xl animate-pulse";
  const alertCls = dismissible
    ? "border-0 bg-slate-800 text-white"
    : "border-0 bg-red-700 text-white";

  return (
    <div className={containerCls} data-testid="outcome-required-banner">
      <div className="container mx-auto max-w-4xl">
        <Alert className={alertCls}>
          <AlertCircle className="h-5 w-5 text-white" />
          <AlertTitle className="text-lg font-bold">
            {dismissible
              ? `${callsNeedingOutcome.length} calls awaiting outcome (team)`
              : t('cmp_fill_in_the_call_result')}
          </AlertTitle>
          <AlertDescription className="mt-2 flex items-center justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm">
                {t('r9_you_have')}{callsNeedingOutcome.length}{t('r9_calls_no_outcome_long')}
              </p>
              {!dismissible && (
                <p className="text-xs text-red-200 mt-1">
                  {t('cmp_required_for_all_conversations')}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="secondary"
                size="lg"
                onClick={() => onFillOutcome(callsNeedingOutcome[0])}
                className={dismissible
                  ? "bg-white text-slate-700 hover:bg-slate-50 font-bold"
                  : "bg-white text-red-600 hover:bg-red-50 font-bold"}
                data-testid="btn-fill-outcome"
              >
                {dismissible ? 'Review' : t('cmp_fill_now')}
              </Button>
              {dismissible && (
                <button
                  onClick={() => setDismissed(true)}
                  className="p-1.5 hover:bg-slate-600 rounded transition"
                  title="Dismiss (admin/team_lead)"
                  data-testid="btn-dismiss-outcome-banner"
                >
                  <X className="h-5 w-5" />
                </button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
};

export default OutcomeRequiredBanner;
