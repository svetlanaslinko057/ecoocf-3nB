/**
 * Ringostat Real-time Manager
 * 
 * Handles real-time call events and shows:
 * 1. Toast notifications for incoming calls
 * 2. Slide-in panel with lead/deal context
 * 3. Outcome form after call ends
 */

import React, { useState, useEffect } from 'react';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Phone, PhoneIncoming, PhoneOff, User, Building2, Clock, Thermometer } from 'lucide-react';
import { toast } from 'sonner';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMissedCallAlerts } from '@/hooks/useMissedCallAlerts';
import OutcomeRequiredBanner from './OutcomeRequiredBanner';
import AiOutcomeSuggester from './AiOutcomeSuggester';
import { useLang } from '../../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const RingostatManager = ({ prefs = null } = {}) => {
  const { t } = useLang();
  const { subscribe } = useWebSocket();
  const { missedCallCount } = useMissedCallAlerts(); // Enable aggressive alerts
  const [incomingCall, setIncomingCall] = useState(null);
  const [showIncomingPanel, setShowIncomingPanel] = useState(false);
  const [showOutcomePanel, setShowOutcomePanel] = useState(false);
  const [outcomeCall, setOutcomeCall] = useState(null);
  const [outcome, setOutcome] = useState('');
  const [outcomeNote, setOutcomeNote] = useState('');
  const [callbackAt, setCallbackAt] = useState('');
  const [callsWithoutOutcome, setCallsWithoutOutcome] = useState([]);

  // Phase IV-6: per-user pref gating.  Falls open (true) when prefs
  // weren't provided so legacy code paths keep working.
  const showIncomingPopup = prefs ? !!prefs.show_incoming_popup : true;
  const showOutcomeBanner = prefs ? !!prefs.show_outcome_banner : true;
  const forceOutcomeBlocking = prefs ? !!prefs.force_outcome_blocking : true;
  const showMissedAlerts = prefs ? !!prefs.show_missed_alerts : true;

  useEffect(() => {
    // Subscribe to Ringostat events
    const unsubscribeIncoming = subscribe('ringostat:incoming_call', handleIncomingCall);
    const unsubscribeNeedsOutcome = subscribe('ringostat:call_needs_outcome', handleCallNeedsOutcome);
    const unsubscribeMissed = subscribe('ringostat:missed_call', handleMissedCall);

    // Load calls without outcome periodically
    loadCallsWithoutOutcome();
    const interval = setInterval(loadCallsWithoutOutcome, 30000); // Check every 30s

    return () => {
      unsubscribeIncoming();
      unsubscribeNeedsOutcome();
      unsubscribeMissed();
      clearInterval(interval);
    };
  }, [subscribe]);

  const handleIncomingCall = (data) => {
    console.log('[RINGOSTAT] Incoming call:', data);
    
    // Check if there's already an active call
    if (incomingCall && showIncomingPanel) {
      // Show "Another incoming call" toast
      toast.warning(
        <div className="flex items-center gap-3">
          <PhoneIncoming className="h-6 w-6 text-amber-600 animate-bounce" />
          <div>
            <div className="font-bold text-base">{t('cmp_second_incoming_call')}</div>
            <div className="text-sm font-medium">{data.lead_name || data.from}</div>
            <div className="text-xs text-muted-foreground mt-1">{t('cmp_first_call_is_still_active')}</div>
          </div>
        </div>,
        {
          duration: 15000,
          position: 'bottom-right',
          className: 'border-2 border-amber-500',
          action: {
            label: t('cmp_accept'),
            onClick: () => {
              setIncomingCall(data);
              openIncomingPanel(data);
            }
          }
        }
      );
      return;
    }
    
    setIncomingCall(data);
    
    // Show prominent toast with sound/vibration effect
    toast(
      <div 
        className="flex items-center gap-3 cursor-pointer p-2" 
        onClick={() => openIncomingPanel(data)}
      >
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-green-100 animate-pulse">
          <PhoneIncoming className="h-6 w-6 text-green-600" />
        </div>
        <div>
          <div className="font-bold text-base">{t('cmp_incoming_call_2')}</div>
          <div className="text-sm font-medium">{data.lead_name || data.from}</div>
          <div className="text-xs text-muted-foreground">{t('cmp_click_to_open')}</div>
        </div>
      </div>,
      {
        duration: 15000,
        position: 'top-right',
        className: 'border-2 border-green-500 shadow-xl',
        important: true
      }
    );

    // Auto-open panel after 2 seconds if not clicked
    setTimeout(() => {
      if (!showIncomingPanel) {
        openIncomingPanel(data);
      }
    }, 2000);
  };

  const handleCallNeedsOutcome = (data) => {
    console.log('[RINGOSTAT] Call needs outcome:', data);
    setOutcomeCall(data);
    setShowOutcomePanel(true);
    
    toast.info(t('cmp_call_completed_specify_result'), {
      duration: 5000
    });
  };

  const handleMissedCall = (data) => {
    console.log('[RINGOSTAT] Missed call:', data);
    
    toast.error(
      <div className="flex items-center gap-3">
        <PhoneOff className="h-5 w-5 text-red-600" />
        <div>
          <div className="font-semibold">{t('cmp_missed_call')}</div>
          <div className="text-sm">{data.lead_name || data.from}</div>
          <div className="text-xs text-muted-foreground">{t('cmp_task_created')}</div>
        </div>
      </div>,
      {
        duration: 8000
      }
    );
  };

  const openIncomingPanel = (data) => {
    // Phase IV-6: respect per-user pref — if user disabled incoming popup,
    // still keep state in memory (for badge counters etc.) but don't open
    // the intrusive Sheet panel.
    setIncomingCall(data);
    if (showIncomingPopup) {
      setShowIncomingPanel(true);
    }
  };

  const handleSaveOutcome = async () => {
    if (!outcome || !outcomeNote) {
      toast.error(t('cmp_specify_result_and_comment'));
      return;
    }

    try {
      const res = await fetch(`${BACKEND_URL}/api/manager/calls/${outcomeCall.call_id}/outcome`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          outcome,
          outcome_note: outcomeNote,
          callback_at: callbackAt || null
        })
      });

      if (res.ok) {
        toast.success(t('cmp_call_result_saved'));
        setShowOutcomePanel(false);
        setOutcome('');
        setOutcomeNote('');
        setCallbackAt('');
        // Reload calls without outcome
        loadCallsWithoutOutcome();
      } else {
        toast.error(t('cmp_save_error'));
      }
    } catch (error) {
      toast.error(t('r9_connection_error'));
    }
  };

  const loadCallsWithoutOutcome = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return;

      const res = await fetch(`${BACKEND_URL}/api/manager/calls/my?limit=50`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await res.json();
      if (data.calls) {
        // Filter calls that need outcome (duration > 30s, answered, no outcome)
        const needsOutcome = data.calls.filter(call => 
          !call.outcome && 
          call.duration > 30 && 
          call.status === 'ANSWERED'
        );
        setCallsWithoutOutcome(needsOutcome);
      }
    } catch (error) {
      console.error('Failed to load calls without outcome:', error);
    }
  };

  const handleFillOutcomeFromBanner = (call) => {
    setOutcomeCall(call);
    setShowOutcomePanel(true);
  };


  const getTemperatureColor = (temp) => {
    if (temp >= 80) return 'text-red-600';
    if (temp >= 50) return 'text-orange-600';
    if (temp >= 30) return 'text-yellow-600';
    return 'text-blue-600';
  };

  const getTemperatureLabel = (temp) => {
    if (temp >= 80) return t('adm3_ed039c0ce2');
    if (temp >= 50) return t('adm3_3f186146c3');
    if (temp >= 30) return t('adm3_9ca2f2e38c');
    return t('adm3_b8fdf23871');
  };

  return (
    <>
      {/* Incoming Call Panel */}
      <Sheet open={showIncomingPanel} onOpenChange={setShowIncomingPanel}>
        <SheetContent side="right" className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <PhoneIncoming className="h-5 w-5 text-green-600" />
              {t('cmp_incoming_call')}
            </SheetTitle>
            <SheetDescription>{t('cmp_lead_and_deal_context')}</SheetDescription>
          </SheetHeader>

          {incomingCall && (
            <div className="mt-6 space-y-4">
              {/* Phone */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">{t('cmp_phone')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span className="text-lg font-semibold">{incomingCall.from}</span>
                  </div>
                </CardContent>
              </Card>

              {/* Lead Info */}
              {incomingCall.lead_name && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">{t('cmp_lead')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-semibold">{incomingCall.lead_name}</span>
                      </div>
                      <div className="text-sm text-muted-foreground">{incomingCall.lead_phone}</div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Deal Info */}
              {incomingCall.deal_title && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">{t('cmp_deal_2')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <span className="font-semibold">{incomingCall.deal_title}</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Source */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">{t('cmp_source')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge>{incomingCall.source || 'ringostat'}</Badge>
                </CardContent>
              </Card>

              {/* Temperature (if available) */}
              {incomingCall.temperature !== undefined && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">{t('cmp_temperature')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <Thermometer className={`h-4 w-4 ${getTemperatureColor(incomingCall.temperature)}`} />
                      <span className={`font-semibold ${getTemperatureColor(incomingCall.temperature)}`}>
                        {getTemperatureLabel(incomingCall.temperature)}
                      </span>
                      <span className="text-sm text-muted-foreground">({incomingCall.temperature}/100)</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                {incomingCall.lead_id && (
                  <>
                    <Button 
                      className="flex-1"
                      onClick={() => {
                        window.location.href = `/admin/leads?id=${incomingCall.lead_id}`;
                      }}
                      data-testid="btn-open-lead"
                    >
                      {t('cmp_open_lead')}
                    </Button>
                    {incomingCall.deal_id && (
                      <Button 
                        variant="outline"
                        className="flex-1"
                        onClick={() => {
                          window.location.href = `/admin/legal?tab=deal_pipeline&dealId=${incomingCall.deal_id}`;
                        }}
                        data-testid="btn-open-deal"
                      >
                        {t('cmp_open_deal')}
                      </Button>
                    )}
                  </>
                )}
                {!incomingCall.lead_id && (
                  <Button 
                    className="flex-1"
                    onClick={() => {
                      // Create new lead with this phone number
                      window.location.href = `/admin/leads?create=true&phone=${incomingCall.from}`;
                    }}
                    data-testid="btn-create-lead"
                  >
                    {t('cmp_create_lead')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Call Outcome Panel */}
      <Sheet open={showOutcomePanel} onOpenChange={setShowOutcomePanel}>
        <SheetContent side="right" className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Phone className="h-5 w-5" />
              {t('cmp_call_result')}
            </SheetTitle>
            <SheetDescription>{t('cmp_specify_the_result_of_the_conversation_with_the_cu')}</SheetDescription>
          </SheetHeader>

          {outcomeCall && (
            <div className="mt-6 space-y-4">
              {/* Call Info */}
              <Card>
                <CardContent className="pt-6">
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">{t('cmp_phone_2')} </span>
                      <span className="font-semibold">{outcomeCall.from}</span>
                    </div>
                    {outcomeCall.lead_name && (
                      <div>
                        <span className="text-muted-foreground">{t('cmp_lead_2')} </span>
                        <span className="font-semibold">{outcomeCall.lead_name}</span>
                      </div>
                    )}
                    {outcomeCall.duration && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <span className="text-muted-foreground">{t('r9_duration')}{outcomeCall.duration}{t('r9_sec_short')}</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* AI Outcome Suggester */}
              {outcomeCall.call_id && (
                <AiOutcomeSuggester 
                  callId={outcomeCall.call_id}
                  onSuggestionAccept={(suggestedOutcome, nextAction) => {
                    setOutcome(suggestedOutcome);
                    setOutcomeNote(nextAction || '');
                  }}
                />
              )}

              {/* Outcome Selection */}
              <div className="space-y-2">
                <Label>{t('cmp_call_result_2')}</Label>
                <Select value={outcome} onValueChange={setOutcome}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('cmp_select_result')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="interested">{t('cmp_interested')}</SelectItem>
                    <SelectItem value="callback">{t('cmp_call_needed')}</SelectItem>
                    <SelectItem value="no_answer">{t('cmp_did_not_answer')}</SelectItem>
                    <SelectItem value="vin_request">{t('cmp_vin_request')}</SelectItem>
                    <SelectItem value="delivery_discussion">{t('cmp_delivery_discussion')}</SelectItem>
                    <SelectItem value="ready_deposit">{t('cmp_ready_for_deposit')}</SelectItem>
                    <SelectItem value="reject">{t('cmp_rejection')}</SelectItem>
                    <SelectItem value="next_step">{t('cmp_next_step')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Callback Time (conditional) */}
              {outcome === 'callback' && (
                <div className="space-y-2">
                  <Label>{t('cmp_when_to_call_back')}</Label>
                  <Input
                    type="datetime-local"
                    value={callbackAt}
                    onChange={(e) => setCallbackAt(e.target.value)}
                  />
                </div>
              )}

              {/* Comment */}
              <div className="space-y-2">
                <Label>{t('cmp_comment')}</Label>
                <Textarea
                  value={outcomeNote}
                  onChange={(e) => setOutcomeNote(e.target.value)}
                  placeholder={t('cmp_describe_the_conversation_result')}
                  rows={4}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.ctrlKey) {
                      e.preventDefault();
                      handleSaveOutcome();
                    }
                  }}
                />
                <p className="text-xs text-muted-foreground">{t('cmp_ctrlenter_for_quick_save')}</p>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                <Button 
                  className="flex-1"
                  onClick={handleSaveOutcome}
                  disabled={!outcome || !outcomeNote}
                >
                  {t('cmp_save_2')}
                </Button>
                <Button 
                  variant="outline"
                  onClick={() => setShowOutcomePanel(false)}
                >
                  {t('cmp_cancel_2')}
                </Button>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Outcome Required Banner — gated by per-user pref.
          When force_outcome_blocking is off (admin/team_lead overrides),
          the banner is still shown for awareness but its underlying
          OutcomeRequiredBanner will allow dismissing. */}
      {showOutcomeBanner && (
        <OutcomeRequiredBanner
          calls={callsWithoutOutcome}
          onFillOutcome={handleFillOutcomeFromBanner}
          dismissible={!forceOutcomeBlocking}
        />
      )}
    </>
  );
};

export default RingostatManager;
