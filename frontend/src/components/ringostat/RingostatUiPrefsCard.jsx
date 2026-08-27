/**
 * RingostatUiPrefsCard
 * --------------------
 * Settings UI block (embedded in RingostatAdminPage Settings tab and
 * in the user profile menu) that lets each user customize what they
 * see from Ringostat:
 *
 *   - Live bar (header status pill)
 *   - Incoming call popup
 *   - Missed call audio/toast alerts
 *   - Outcome-required banner
 *   - Aggregate supervision summary card (bottom-right)
 *
 * Managers cannot turn off the outcome banner (backend hard-guard).
 */
import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useRingostatPrefs } from '@/hooks/useRingostatPrefs';
import { toast } from 'sonner';

const ROW_DEFS = [
  { key: 'show_live_bar', label: 'Live call bar', desc: 'Header indicator showing current call status' },
  { key: 'show_incoming_popup', label: 'Incoming call popup', desc: 'Slide-in panel with lead info on a new call' },
  { key: 'show_missed_alerts', label: 'Missed call alerts', desc: 'Audio + toast notifications for missed calls' },
  { key: 'show_outcome_banner', label: 'Outcome-required banner', desc: 'Top banner forcing managers to fill outcomes' },
  { key: 'force_outcome_blocking', label: 'Block close until outcome filled', desc: 'Manager cannot dismiss outcome panel' },
  { key: 'show_aggregate_summary', label: 'Team / company summary card', desc: 'Passive supervision widget (team lead / admin)' },
];

const MANAGER_LOCKED_KEYS = ['show_outcome_banner', 'force_outcome_blocking'];

export default function RingostatUiPrefsCard() {
  const { prefs, savedPrefs, role, roleDefaults, save, loading } = useRingostatPrefs();
  const [busy, setBusy] = useState(false);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-slate-500">Loading preferences…</CardContent>
      </Card>
    );
  }

  const isManager = (role || '').toLowerCase() === 'manager';

  const toggle = async (key, val) => {
    if (isManager && MANAGER_LOCKED_KEYS.includes(key)) {
      toast.error("Managers cannot disable outcome enforcement");
      return;
    }
    setBusy(true);
    const ok = await save({ [key]: !!val });
    setBusy(false);
    toast(ok ? 'Saved' : 'Failed to save', ok ? {} : { className: 'bg-red-50' });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Ringostat — your view
          <Badge variant="secondary" className="text-[10px]">{role || 'user'}</Badge>
        </CardTitle>
        <CardDescription>
          Customize which Ringostat widgets appear in YOUR session. Other team members are unaffected.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {ROW_DEFS.map((row) => {
          const checked = !!prefs[row.key];
          const isOverridden = Object.prototype.hasOwnProperty.call(savedPrefs, row.key);
          const locked = isManager && MANAGER_LOCKED_KEYS.includes(row.key);
          return (
            <div
              key={row.key}
              className="flex items-center justify-between gap-3 py-2 border-b border-slate-100 dark:border-slate-800 last:border-b-0"
            >
              <div className="flex-1 min-w-0">
                <Label className="font-medium block">{row.label}</Label>
                <div className="text-xs text-slate-500 mt-0.5">{row.desc}</div>
                <div className="flex items-center gap-2 mt-1">
                  {isOverridden ? (
                    <Badge variant="outline" className="text-[10px] border-blue-300 text-blue-600">
                      custom
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px]">
                      role default
                    </Badge>
                  )}
                  <span className="text-[10px] text-slate-400">
                    default for {role || 'role'}: {String(roleDefaults?.[row.key])}
                  </span>
                </div>
              </div>
              <Switch
                checked={checked}
                disabled={busy || locked}
                onCheckedChange={(v) => toggle(row.key, v)}
                title={locked ? 'Locked: managers must always fill outcomes' : undefined}
              />
            </div>
          );
        })}
        {isManager && (
          <div className="text-[11px] text-amber-700 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-300 p-2 rounded">
            ⓘ As a manager, the outcome banner and outcome-blocking cannot be disabled — they enforce your direct
            customer-handling responsibility.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
