/**
 * Invoice Reminders Dashboard
 *
 * /admin/invoice-reminders
 *
 * Monitor, configure and run invoice-reminder logic.
 *
 * Conventions:
 *   • Tooltips use the same `cursor-help` whole-block hover pattern as the rest of the app
 *     (e.g. Dashboard.js section titles). NO separate (i) icons — the entire trigger element
 *     is the hover target. The popover is the dark BIBI style.
 *   • Clicking an invoice row in "Critical Overdue Invoices" opens a real drawer with
 *     full invoice data (GET /api/invoices/{id}) + real action buttons (mark-paid / send / cancel).
 *
 * Everything renders an HONEST empty state when no invoices exist.
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang, getLocale } from '../i18n';
import RefreshButton from '../components/ui/RefreshButton';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  Clock,
  Warning,
  ShieldWarning,
  Bell,
  ArrowsClockwise,
  Check,
  CaretRight,
  ChartLineUp,
  Play,
  Gear,
  Power,
  EnvelopeSimple,
  ChatCircleDots,
  DeviceMobile,
  AppWindow,
  X,
  PaperPlaneTilt,
  Prohibit,
  Receipt,
  User as UserIcon,
} from '@phosphor-icons/react';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '../components/ui/tooltip';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '../components/ui/sheet';

// ─────────────────────────────────────────────────────────────────
// Shared tooltip — hover-on-block, matches Dashboard.js convention
// ─────────────────────────────────────────────────────────────────

const TIP_CONTENT_CLASS =
  'max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg z-[60]';

const HoverTip = ({ children, side = 'top', align = 'start', tip }) => {
  if (!tip) return children;
  return (
    <Tooltip delayDuration={150}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side={side} align={align} className={TIP_CONTENT_CLASS}>
        {tip}
      </TooltipContent>
    </Tooltip>
  );
};

// ─────────────────────────────────────────────────────────────────
// Presentational helpers
// ─────────────────────────────────────────────────────────────────

const COLOR_MAP = {
  amber:   { bg: 'bg-amber-50',   fg: 'text-amber-600' },
  orange:  { bg: 'bg-orange-50',  fg: 'text-orange-600' },
  red:     { bg: 'bg-red-50',     fg: 'text-red-600' },
  emerald: { bg: 'bg-emerald-50', fg: 'text-emerald-600' },
  blue:    { bg: 'bg-blue-50',    fg: 'text-blue-600' },
  violet:  { bg: 'bg-violet-50',  fg: 'text-violet-600' },
};

const SummaryCard = ({ title, value, icon: Icon, color = 'amber', subtitle, tip, testId }) => {
  const c = COLOR_MAP[color] || COLOR_MAP.amber;
  return (
    <HoverTip tip={tip} side="top" align="center">
      <div
        className="bg-white rounded-2xl border border-[#E4E4E7] p-3 sm:p-4 flex items-start gap-3 cursor-help hover:border-[#D4D4D8] hover:shadow-sm transition-all"
        data-testid={testId}
      >
        <div className={`p-2 rounded-xl ${c.bg} flex-shrink-0`}>
          <Icon size={20} weight="duotone" className={c.fg} />
        </div>
        <div className="min-w-0 flex-1">
          <p
            className="text-xl sm:text-2xl font-bold text-[#18181B] leading-tight"
            style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
          >
            {value}
          </p>
          <p className="text-xs sm:text-sm font-medium text-[#18181B] truncate mt-0.5">{title}</p>
          {subtitle && <p className="text-[10px] sm:text-xs text-[#A1A1AA] mt-0.5 truncate">{subtitle}</p>}
        </div>
      </div>
    </HoverTip>
  );
};

const RuleCard = ({ icon: Icon, color, title, description, tip, testId }) => {
  const c = COLOR_MAP[color] || COLOR_MAP.blue;
  return (
    <HoverTip tip={tip} side="top" align="center">
      <div
        className="bg-white/80 rounded-xl p-3 cursor-help hover:bg-white transition-colors"
        data-testid={testId}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <div className={`p-1.5 rounded-lg ${c.bg}`}>
            <Icon size={14} className={c.fg} />
          </div>
          <span className="font-medium text-[#18181B] text-sm flex-1 truncate">{title}</span>
        </div>
        <p className="text-xs text-[#71717A] leading-snug">{description}</p>
      </div>
    </HoverTip>
  );
};

// ─────────────────────────────────────────────────────────────────
// Invoice Detail Drawer — real backend (GET /api/invoices/{id} +
// PATCH mark-paid / send / cancel)
// ─────────────────────────────────────────────────────────────────

const STATUS_META = {
  draft:     { label: 'Draft',     cls: 'bg-zinc-100 text-zinc-700' },
  sent:      { label: 'Sent',      cls: 'bg-blue-100 text-blue-700' },
  pending:   { label: 'Pending',   cls: 'bg-amber-100 text-amber-700' },
  overdue:   { label: 'Overdue',   cls: 'bg-red-100 text-red-700' },
  paid:      { label: 'Paid',      cls: 'bg-emerald-100 text-emerald-700' },
  cancelled: { label: 'Cancelled', cls: 'bg-zinc-100 text-zinc-500 line-through' },
  void:      { label: 'Void',      cls: 'bg-zinc-100 text-zinc-500 line-through' },
  refunded:  { label: 'Refunded',  cls: 'bg-violet-100 text-violet-700' },
};

const fmtMoney = (v, currency = 'USD') => {
  try {
    return new Intl.NumberFormat(getLocale(), { style: 'currency', currency }).format(v || 0);
  } catch {
    return `$${(v || 0).toLocaleString()}`;
  }
};

const InvoiceDrawer = ({ invoiceId, onClose, onChanged }) => {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing]   = useState(null); // 'mark-paid' | 'send' | 'cancel' | null
  const [error, setError]     = useState(null);

  const load = useCallback(async () => {
    if (!invoiceId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API_URL}/api/invoices/${invoiceId}`);
      setInvoice(r.data?.data || r.data);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to load invoice';
      setError(typeof msg === 'string' ? msg : 'Failed to load invoice');
    } finally {
      setLoading(false);
    }
  }, [invoiceId]);

  useEffect(() => { load(); }, [load]);

  const act = async (action) => {
    if (!invoice?.id || acting) return;
    setActing(action);
    try {
      const r = await axios.patch(`${API_URL}/api/invoices/${invoice.id}/${action}`, {});
      const updated = r.data?.invoice || r.data?.data || null;
      const labels = {
        'mark-paid': 'Invoice marked as paid',
        send:        'Invoice sent',
        cancel:      'Invoice cancelled',
      };
      toast.success(labels[action] || 'Done');
      setInvoice(updated || invoice);
      onChanged?.();
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Action failed';
      toast.error(typeof msg === 'string' ? msg : 'Action failed');
    } finally {
      setActing(null);
    }
  };

  const status = invoice?.status || 'pending';
  const meta = STATUS_META[status] || STATUS_META.pending;
  const canMarkPaid = !!invoice && !['paid', 'cancelled', 'void'].includes(status);
  const canSend     = !!invoice && ['draft', 'pending'].includes(status);
  const canCancel   = !!invoice && !['paid', 'cancelled', 'void', 'refunded'].includes(status);

  const items = Array.isArray(invoice?.items) ? invoice.items : [];

  return (
    <div className="fixed inset-0 z-50 flex" data-testid="invoice-drawer">
      <button
        type="button"
        aria-label="Close drawer"
        className="flex-1 bg-zinc-900/40"
        onClick={onClose}
      />
      <aside className="w-full max-w-md bg-white shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-[#E4E4E7] px-5 py-4 flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-wider text-[#A1A1AA] flex items-center gap-1">
              <Receipt size={12} /> Invoice
            </p>
            <p className="font-mono text-sm text-[#18181B] truncate mt-0.5">
              {invoice?.id || invoiceId}
            </p>
            <div className="mt-1.5">
              <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${meta.cls}`}>
                {meta.label}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[#FAFAFA] rounded-lg text-[#71717A] hover:text-[#18181B]"
            data-testid="invoice-drawer-close"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full" />
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-medium text-red-700">{error}</p>
              <p className="text-[11px] text-red-600/80 mt-1">
                Tried <span className="font-mono">GET /api/invoices/{invoiceId}</span>
              </p>
            </div>
          ) : invoice ? (
            <>
              {/* Amount block */}
              <div className="bg-gradient-to-br from-[#18181B] to-[#3F3F46] rounded-2xl p-5 text-white">
                <p className="text-xs opacity-80 uppercase tracking-wider">Amount</p>
                <p className="text-3xl font-bold mt-1 tabular-nums">
                  {fmtMoney(invoice.total ?? invoice.amount, invoice.currency || 'USD')}
                </p>
                {invoice.dueDate && (
                  <p className="text-xs opacity-80 mt-2">
                    Due: {new Date(invoice.dueDate).toLocaleDateString(getLocale())}
                  </p>
                )}
              </div>

              {/* Meta grid */}
              <div className="grid grid-cols-2 gap-3 text-[12px]">
                <MetaRow icon={UserIcon} label="Customer" value={invoice.customerId || '—'} />
                <MetaRow icon={Receipt} label="Title" value={invoice.title || invoice.description || '—'} />
                <MetaRow icon={Clock} label="Created"
                  value={invoice.created_at ? new Date(invoice.created_at).toLocaleString(getLocale()) : '—'} />
                <MetaRow icon={PaperPlaneTilt} label="Sent"
                  value={invoice.sentAt ? new Date(invoice.sentAt).toLocaleString(getLocale()) : '—'} />
                <MetaRow icon={Bell} label="Reminders" value={String(invoice.reminderCount ?? 0)} />
                <MetaRow icon={ArrowsClockwise} label="Last reminder"
                  value={invoice.lastReminderAt ? new Date(invoice.lastReminderAt).toLocaleString(getLocale()) : '—'} />
              </div>

              {/* Items */}
              {items.length > 0 && (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[#A1A1AA] font-semibold mb-2">Items</p>
                  <div className="space-y-1.5">
                    {items.map((it, i) => (
                      <div key={i} className="flex items-center justify-between text-xs text-[#18181B] px-3 py-2 rounded-lg bg-[#FAFAFA]">
                        <span className="truncate pr-2">{it.title || it.name || `Item ${i + 1}`}</span>
                        <span className="font-medium whitespace-nowrap">{fmtMoney(it.amount || it.price, invoice.currency || 'USD')}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Real actions */}
              <div>
                <p className="text-[11px] uppercase tracking-wider text-[#A1A1AA] font-semibold mb-2">Actions</p>
                <div className="grid grid-cols-1 gap-2">
                  <ActionBtn
                    icon={Check}
                    label={acting === 'mark-paid' ? 'Marking…' : 'Mark as paid'}
                    onClick={() => act('mark-paid')}
                    disabled={!canMarkPaid || !!acting}
                    intent="primary"
                    testId="invoice-mark-paid"
                  />
                  <ActionBtn
                    icon={PaperPlaneTilt}
                    label={acting === 'send' ? 'Sending…' : 'Send reminder email'}
                    onClick={() => act('send')}
                    disabled={!canSend || !!acting}
                    intent="ghost"
                    testId="invoice-send"
                  />
                  <ActionBtn
                    icon={Prohibit}
                    label={acting === 'cancel' ? 'Cancelling…' : 'Cancel invoice'}
                    onClick={() => act('cancel')}
                    disabled={!canCancel || !!acting}
                    intent="danger"
                    testId="invoice-cancel"
                  />
                </div>
                <p className="text-[11px] text-[#A1A1AA] mt-2">
                  Actions hit <span className="font-mono">PATCH /api/invoices/{'{id}'}/{'{action}'}</span> in real time.
                </p>
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
};

const MetaRow = ({ icon: Icon, label, value }) => (
  <div className="bg-[#FAFAFA] rounded-xl px-3 py-2 min-w-0">
    <div className="flex items-center gap-1.5 text-[#71717A]">
      <Icon size={12} />
      <span className="text-[10px] uppercase tracking-wider font-medium">{label}</span>
    </div>
    <p className="text-[12px] text-[#18181B] truncate mt-0.5 font-medium" title={String(value)}>
      {value}
    </p>
  </div>
);

const ActionBtn = ({ icon: Icon, label, onClick, disabled, intent = 'primary', testId }) => {
  const base = 'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed';
  const intents = {
    primary: 'bg-[#18181B] text-white hover:bg-[#3F3F46]',
    ghost:   'border border-[#E4E4E7] text-[#18181B] bg-white hover:bg-[#FAFAFA]',
    danger:  'border border-red-200 text-red-600 bg-white hover:bg-red-50',
  };
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`${base} ${intents[intent]}`} data-testid={testId}>
      <Icon size={14} weight="duotone" />
      <span>{label}</span>
    </button>
  );
};

// ─────────────────────────────────────────────────────────────────
// Settings Sheet
// ─────────────────────────────────────────────────────────────────

const CHANNELS = [
  { id: 'email',    label: 'Email',    icon: EnvelopeSimple, help: 'Outbound email reminders to the customer + manager.' },
  { id: 'in_app',   label: 'In-app',   icon: AppWindow,      help: 'Inline notification inside the BIBI Cars dashboard.' },
  { id: 'telegram', label: 'Telegram', icon: ChatCircleDots, help: 'Telegram bot DM to the manager (requires bot setup).' },
  { id: 'sms',      label: 'SMS',      icon: DeviceMobile,   help: 'Text-message reminder to the customer (requires SMS provider).' },
];

const FIELD_META = {
  level1_days:         { label: 'Level 1 — Manager',     unit: 'days',  min: 0, max: 60,
    help: 'Days past due before an invoice escalates to Level 1 (Manager warning).' },
  level2_days:         { label: 'Level 2 — Team Lead',   unit: 'days',  min: 0, max: 90,
    help: 'Days past due before an invoice escalates to Level 2 (Team Lead).' },
  level3_days:         { label: 'Level 3 — Owner',       unit: 'days',  min: 0, max: 180,
    help: 'Days past due before an invoice escalates to Level 3 (Owner).' },
  critical_days:       { label: 'Critical',              unit: 'days',  min: 0, max: 365,
    help: 'Days past due before an invoice is flagged as Critical (requires immediate action).' },
  reminder_after_days: { label: 'Start reminders after', unit: 'days',  min: 0, max: 60,
    help: 'How long after issue/dueDate the scanner starts dispatching reminders.' },
  cooldown_hours:      { label: 'Cooldown',              unit: 'hours', min: 1, max: 720,
    help: 'Minimum time between two reminders for the SAME invoice. Prevents spam.' },
  pre_reminder_hours:  { label: 'T-24h pre-reminder',    unit: 'hours', min: 0, max: 168,
    help: 'Send a heads-up reminder this many hours BEFORE the invoice is due.' },
};

const NumberInput = ({ fieldKey, meta, value, onChange }) => (
  <div data-testid={`settings-field-${fieldKey}`}>
    <HoverTip tip={meta.help} side="top" align="start">
      <label className="text-[12px] font-medium text-[#3F3F46] truncate cursor-help mb-1 block">
        {meta.label}
      </label>
    </HoverTip>
    <div className="relative">
      <input
        type="number"
        min={meta.min}
        max={meta.max}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        className="w-full pr-14 px-3 py-2 rounded-lg border border-[#E4E4E7] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15 text-sm"
      />
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-[#A1A1AA] uppercase pointer-events-none select-none">
        {meta.unit}
      </span>
    </div>
  </div>
);

const SettingsSheet = ({ open, onOpenChange, settings, onSaved }) => {
  const [draft, setDraft]   = useState(settings);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState([]);

  useEffect(() => { setDraft(settings); setErrors([]); }, [settings, open]);

  if (!draft) return null;

  const setField = (k, v) => setDraft({ ...draft, [k]: v });
  const toggleChannel = (id) => {
    const current = new Set(draft.channels || []);
    if (current.has(id)) current.delete(id); else current.add(id);
    setDraft({ ...draft, channels: [...current] });
  };

  const handleSave = async () => {
    setSaving(true);
    setErrors([]);
    try {
      const payload = {
        enabled: draft.enabled,
        level1_days: Number(draft.level1_days),
        level2_days: Number(draft.level2_days),
        level3_days: Number(draft.level3_days),
        critical_days: Number(draft.critical_days),
        reminder_after_days: Number(draft.reminder_after_days),
        cooldown_hours: Number(draft.cooldown_hours),
        pre_reminder_hours: Number(draft.pre_reminder_hours),
        channels: draft.channels || [],
      };
      const res = await axios.put(`${API_URL}/api/invoice-reminders/settings`, payload);
      toast.success('Reminder settings saved');
      onSaved?.(res.data?.data || draft);
      onOpenChange(false);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const list = Array.isArray(detail?.errors) ? detail.errors : (typeof detail === 'string' ? [detail] : ['Failed to save settings']);
      setErrors(list);
      toast.error(list[0]);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto" data-testid="reminder-settings-sheet">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Gear size={18} weight="duotone" /> Reminder settings
          </SheetTitle>
          <SheetDescription>
            Edit how invoice reminders behave. Changes apply to the next scan (manual or hourly).
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-5">
          <HoverTip tip="When off, no reminders are dispatched — hourly cron and Run processing both no-op." side="bottom" align="start">
            <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] cursor-help">
              <div className="flex items-center gap-2 min-w-0">
                <Power size={16} className="text-[#71717A]" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#18181B]">Reminder engine</p>
                  <p className="text-[11px] text-[#71717A]">Master switch for the whole reminder workflow.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setField('enabled', !draft.enabled); }}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${draft.enabled ? 'bg-emerald-500' : 'bg-zinc-300'}`}
                data-testid="settings-enabled-toggle"
                aria-pressed={!!draft.enabled}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${draft.enabled ? 'translate-x-5' : 'translate-x-1'}`} />
              </button>
            </div>
          </HoverTip>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#A1A1AA] mb-2">Escalation thresholds</p>
            <div className="grid grid-cols-2 gap-3">
              {['level1_days', 'level2_days', 'level3_days', 'critical_days'].map(k => (
                <NumberInput key={k} fieldKey={k} meta={FIELD_META[k]} value={draft[k]} onChange={(v) => setField(k, v)} />
              ))}
            </div>
            <p className="text-[11px] text-[#A1A1AA] mt-2">
              Must satisfy: <span className="font-mono">level1 ≤ level2 ≤ level3 ≤ critical</span>
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#A1A1AA] mb-2">Dispatch policy</p>
            <div className="grid grid-cols-1 gap-3">
              {['reminder_after_days', 'cooldown_hours', 'pre_reminder_hours'].map(k => (
                <NumberInput key={k} fieldKey={k} meta={FIELD_META[k]} value={draft[k]} onChange={(v) => setField(k, v)} />
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#A1A1AA] mb-2">Notification channels</p>
            <div className="grid grid-cols-2 gap-2">
              {CHANNELS.map(ch => {
                const active = (draft.channels || []).includes(ch.id);
                const Icon = ch.icon;
                return (
                  <HoverTip key={ch.id} tip={ch.help} side="top" align="center">
                    <button
                      type="button"
                      onClick={() => toggleChannel(ch.id)}
                      className={`flex items-center gap-2 p-2.5 rounded-xl border text-left transition-colors cursor-help ${active ? 'border-[#18181B] bg-[#18181B] text-white' : 'border-[#E4E4E7] bg-white text-[#18181B] hover:border-[#A1A1AA]'}`}
                      data-testid={`settings-channel-${ch.id}`}
                      aria-pressed={active}
                    >
                      <Icon size={16} weight="duotone" />
                      <span className="text-sm font-medium flex-1 truncate">{ch.label}</span>
                      {active && <Check size={14} />}
                    </button>
                  </HoverTip>
                );
              })}
            </div>
            <p className="text-[11px] text-[#A1A1AA] mt-2">At least one channel must remain enabled.</p>
          </div>

          {errors.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3">
              <p className="text-xs font-medium text-red-700 mb-1">Validation errors</p>
              <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-red-700">
                {errors.map((er, i) => <li key={i}>{er}</li>)}
              </ul>
            </div>
          )}
        </div>

        <SheetFooter className="mt-6 gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 rounded-xl border border-[#E4E4E7] text-sm font-medium hover:bg-[#FAFAFA]"
            data-testid="settings-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-xl bg-[#18181B] text-white text-sm font-medium hover:bg-[#3F3F46] disabled:opacity-50 flex items-center gap-2"
            data-testid="settings-save"
          >
            {saving && <ArrowsClockwise size={14} className="animate-spin" />}
            Save settings
          </button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};

// ─────────────────────────────────────────────────────────────────
// Main dashboard
// ─────────────────────────────────────────────────────────────────

const InvoiceRemindersDashboard = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [criticalInvoices, setCriticalInvoices] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerInvoiceId, setDrawerInvoiceId] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [summaryRes, criticalRes, settingsRes] = await Promise.all([
        axios.get(`${API_URL}/api/invoice-reminders/escalation-summary`),
        axios.get(`${API_URL}/api/invoice-reminders/critical`),
        axios.get(`${API_URL}/api/invoice-reminders/settings`),
      ]);
      setSummary(summaryRes.data);
      const c = criticalRes.data;
      setCriticalInvoices(Array.isArray(c) ? c : (c?.data || []));
      setSettings(settingsRes.data?.data || settingsRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error(t('adm_data_loading_error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleForceProcess = async () => {
    try {
      setProcessing(true);
      const res = await axios.post(`${API_URL}/api/invoice-reminders/process`);
      const data = res.data || {};
      if (data.success === false) {
        toast.error(data.error || t('adm_processing_error'));
        return;
      }
      if (data.skipped) {
        toast.info('Reminder engine is currently disabled in settings.');
        return;
      }
      const processed = data.processed ?? 0;
      const reminders = data.reminders ?? 0;
      if (processed === 0 && reminders === 0) {
        toast.success(t('adm_no_reminders_to_send') || 'Scan completed — no reminders due right now.');
      } else {
        toast.success(`Inspected ${processed} invoice(s), dispatched ${reminders} reminder(s).`);
      }
      fetchData();
    } catch (error) {
      const msg = error?.response?.data?.error
        || error?.response?.data?.detail
        || error?.message
        || t('adm_processing_error');
      toast.error(typeof msg === 'string' ? msg : t('adm_processing_error'));
    } finally {
      setProcessing(false);
    }
  };

  const hasInvoiceData = summary?.hasData !== false;
  const live = summary?.settings || settings || {};
  const userRole = (user?.role || '').toLowerCase();
  const canEditSettings = ['admin', 'master_admin', 'owner', 'team_lead'].includes(userRole) || !user;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin w-8 h-8 border-2 border-[#18181B] border-t-transparent rounded-full" />
      </div>
    );
  }

  const levelTip = (label, days, action) =>
    `${label} — invoice is ${days}+ day(s) past due. Action: ${action}.`;

  return (
    <TooltipProvider delayDuration={150}>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-5 sm:space-y-6"
        data-testid="invoice-reminders-dashboard"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <HoverTip
              side="bottom"
              align="start"
              tip="Automated workflow that watches unpaid invoices and dispatches reminders on a schedule. Counters and the critical list are live — they read from the invoices collection. Edit thresholds via Settings."
            >
              <div className="inline-flex items-center gap-2 cursor-help">
                <h1
                  className="text-xl sm:text-2xl font-bold text-[#18181B] truncate"
                  style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
                >
                  {t('adm_invoice_reminders')}
                </h1>
                {live?.enabled === false && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-200 text-zinc-700">
                    <Power size={10} /> ENGINE OFF
                  </span>
                )}
              </div>
            </HoverTip>
            <p className="text-xs sm:text-sm text-[#71717A] mt-0.5 line-clamp-2">
              {t('adm_reminders_and_escalations_monitoring')}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <RefreshButton onClick={fetchData} ariaLabel="Refresh" testId="refresh-btn" />
            {canEditSettings && (
              <HoverTip tip="Edit reminder thresholds (Level 1/2/3, Critical), cooldown, T-24h pre-reminder, and notification channels." side="bottom" align="end">
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-[#FAFAFA] text-sm font-medium cursor-help"
                  data-testid="settings-btn"
                >
                  <Gear size={16} />
                  <span className="hidden sm:inline">Settings</span>
                </button>
              </HoverTip>
            )}
            <HoverTip tip="Run the reminder scanner once now (instead of waiting for the hourly cron). Respects cooldown, so it will not double-fire reminders." side="bottom" align="end">
              <button
                onClick={handleForceProcess}
                disabled={processing}
                className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-[#18181B] text-white rounded-xl hover:bg-[#3F3F46] transition-colors disabled:opacity-50 whitespace-nowrap text-sm font-medium cursor-help"
                data-testid="process-btn"
              >
                {processing ? <ArrowsClockwise size={16} className="animate-spin" /> : <Play size={16} weight="fill" />}
                <span className="hidden xs:inline sm:inline">{t('r9_run_processing_1j2k3l')}</span>
              </button>
            </HoverTip>
          </div>
        </div>

        {/* Empty state */}
        {!hasInvoiceData ? (
          <div
            className="bg-white rounded-2xl border border-dashed border-[#E4E4E7] p-8 sm:p-12 text-center"
            data-testid="invoice-reminders-empty"
          >
            <div className="inline-flex p-3 rounded-2xl bg-[#F4F4F5] mb-4">
              <Bell size={28} weight="duotone" className="text-[#A1A1AA]" />
            </div>
            <h2
              className="text-base sm:text-lg font-semibold text-[#18181B]"
              style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
            >
              No invoice reminder data yet
            </h2>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1.5 max-w-md mx-auto leading-relaxed">
              Once invoices are issued through the system, escalation counters and overdue alerts appear here.
              Use <b>Run processing</b> to force a scan at any time, or open <b>Settings</b> to tune thresholds.
            </p>
          </div>
        ) : (
          <>
            {/* Counters */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              <SummaryCard
                title={t('level1Manager')}
                value={summary?.level1Count || 0}
                icon={Clock}
                color="amber"
                subtitle={`${live.level1_days ?? 1}+ days overdue`}
                tip={levelTip('Level 1 (Manager)', live.level1_days ?? 1, 'Warning sent to the account manager via email + in-app')}
                testId="summary-level1"
              />
              <SummaryCard
                title={t('level2TeamLead')}
                value={summary?.level2Count || 0}
                icon={Warning}
                color="orange"
                subtitle={`${live.level2_days ?? 3}+ days overdue`}
                tip={levelTip('Level 2 (Team Lead)', live.level2_days ?? 3, 'Escalation to the team lead, manager copied')}
                testId="summary-level2"
              />
              <SummaryCard
                title={t('level3Owner')}
                value={summary?.level3Count || 0}
                icon={ShieldWarning}
                color="red"
                subtitle={`${live.level3_days ?? 5}+ days overdue`}
                tip={levelTip('Level 3 (Owner)', live.level3_days ?? 5, 'Notice escalated to the owner / master admin')}
                testId="summary-level3"
              />
              <SummaryCard
                title={t('criticalLevel')}
                value={summary?.criticalCount || 0}
                icon={Bell}
                color="red"
                subtitle={`${live.critical_days ?? 7}+ days overdue`}
                tip={levelTip('Critical', live.critical_days ?? 7, 'Immediate action: deal frozen, manual intervention required')}
                testId="summary-critical"
              />
            </div>

            {/* Rules */}
            <div className="bg-gradient-to-br from-violet-50 to-indigo-50 rounded-2xl border border-violet-200 p-4 sm:p-5">
              <HoverTip
                side="top" align="start"
                tip="Schedule the reminder engine follows. Adjustable in Settings. Times are evaluated against each invoice's dueDate."
              >
                <h2
                  className="text-base sm:text-lg font-semibold text-[#18181B] mb-3 sm:mb-4 inline-block cursor-help"
                  style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
                >
                  {t('adm_reminder_rules')}
                </h2>
              </HoverTip>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <RuleCard
                  icon={Clock} color="blue"
                  title={`T-${live.pre_reminder_hours ?? 24}h (Pre-reminder)`}
                  description={`Heads-up reminder ${live.pre_reminder_hours ?? 24} hours before the invoice is due.`}
                  tip={`Polite pre-reminder sent ${live.pre_reminder_hours ?? 24}h before dueDate to both customer and manager.`}
                  testId="rule-pre"
                />
                <RuleCard
                  icon={Bell} color="amber"
                  title="T-0 (Due today)"
                  description={t('adm_urgent_reminder_on_deadline_day')}
                  tip="On the dueDate itself: urgent reminder fires to the customer (high-priority email + in-app)."
                  testId="rule-today"
                />
                <RuleCard
                  icon={Warning} color="orange"
                  title={`T+${live.level1_days ?? 1}–${(live.level2_days ?? 3) - 1} days`}
                  description={`Auto-escalates to L1 (Manager) at +${live.level1_days ?? 1}d, then to L2 (Team Lead) at +${live.level2_days ?? 3}d.`}
                  tip={`First and second escalation. Reminders sent on every scan after the cooldown of ${live.cooldown_hours ?? 48}h elapses.`}
                  testId="rule-l1l2"
                />
                <RuleCard
                  icon={ShieldWarning} color="red"
                  title={`T+${live.level3_days ?? 5}+ days`}
                  description={`L3 (Owner) at +${live.level3_days ?? 5}d, Critical at +${live.critical_days ?? 7}d.`}
                  tip={`Last two stages. Critical (≥${live.critical_days ?? 7}d) requires manual intervention; the deal may be frozen.`}
                  testId="rule-l3crit"
                />
                <RuleCard
                  icon={Check} color="emerald"
                  title="Notification channels"
                  description={(live.channels || []).join(', ').toUpperCase() || '—'}
                  tip="Active delivery channels. Multiple may be combined. Edit via Settings."
                  testId="rule-channels"
                />
                <RuleCard
                  icon={ArrowsClockwise} color="violet"
                  title={`Cooldown: ${live.cooldown_hours ?? 48}h`}
                  description="Minimum time between two reminders for the same invoice."
                  tip="Anti-spam guard. Even if you press Run processing repeatedly, a single invoice will not be reminded again until cooldown elapses."
                  testId="rule-cooldown"
                />
              </div>
            </div>

            {/* Critical Overdue Invoices — rows are now CLICKABLE and open the real drawer */}
            <div className="bg-white rounded-2xl border border-[#E4E4E7] p-4 sm:p-5">
              <div className="flex items-center justify-between mb-4 gap-2">
                <HoverTip
                  side="top" align="start"
                  tip={`Invoices at least ${live.critical_days ?? 7} days past due and still unpaid, sorted by oldest dueDate first. Click any row to open the invoice and take action.`}
                >
                  <h2
                    className="text-base sm:text-lg font-semibold text-[#18181B] truncate cursor-help inline-block"
                    style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
                  >
                    {t('adm_critical_overdue_invoices')}
                  </h2>
                </HoverTip>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700 flex-shrink-0 whitespace-nowrap">
                  {criticalInvoices.length} total
                </span>
              </div>
              {criticalInvoices.length > 0 ? (
                <div className="space-y-2.5">
                  {criticalInvoices.map((invoice) => (
                    <HoverTip
                      key={invoice.id}
                      side="top" align="start"
                      tip={`Click to open invoice #${(invoice.id || '').slice(0, 8)} — view details, send a reminder, mark as paid or cancel.`}
                    >
                      <button
                        type="button"
                        onClick={() => setDrawerInvoiceId(invoice.id)}
                        className="w-full flex items-center gap-3 p-3 bg-white rounded-xl border border-[#E4E4E7] hover:shadow-md hover:border-[#A1A1AA] transition-all text-left cursor-pointer"
                        data-testid={`critical-row-${invoice.id}`}
                      >
                        <div className="p-2 rounded-lg bg-red-50 flex-shrink-0">
                          <Warning size={18} className="text-red-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-medium text-[#18181B] truncate text-sm">
                              #{invoice.id?.slice(0, 8)}
                            </p>
                            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700 flex-shrink-0">
                              OVERDUE
                            </span>
                          </div>
                          <p className="text-xs text-[#71717A] truncate">{invoice.title || invoice.description || '—'}</p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="font-bold text-[#18181B] text-sm whitespace-nowrap">
                            {fmtMoney(invoice.amount, invoice.currency || 'USD')}
                          </p>
                          <p className="text-[10px] text-[#71717A] whitespace-nowrap">
                            {invoice.dueDate ? new Date(invoice.dueDate).toLocaleDateString(getLocale()) : '—'}
                          </p>
                        </div>
                        <CaretRight size={14} className="text-[#A1A1AA] flex-shrink-0" />
                      </button>
                    </HoverTip>
                  ))}
                </div>
              ) : (
                <div className="text-center py-10">
                  <Check size={40} className="mx-auto mb-3 text-emerald-500" />
                  <p className="font-medium text-[#18181B] text-sm">{t('adm_no_critical_invoices')}</p>
                  <p className="text-xs text-[#71717A] mt-1">{t('adm_all_invoices_are_ok')}</p>
                </div>
              )}
            </div>

            {/* Cron info */}
            <HoverTip
              side="top" align="start"
              tip="Background worker runs every 60 minutes. Uses the same logic as Run processing. Cooldown prevents duplicate reminders."
            >
              <div className="bg-[#F4F4F5] rounded-xl p-3 sm:p-4 flex items-start gap-3 cursor-help">
                <ChartLineUp size={20} className="text-[#71717A] flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-xs sm:text-sm font-medium text-[#18181B]">{t('adm_automatic_processing')}</p>
                  <p className="text-[11px] sm:text-xs text-[#71717A] leading-snug">
                    {t('adm_cron_job_runs_every_hour_to_check_and_send_reminde')}
                  </p>
                  {summary?.lastProcessedAt && (
                    <p className="text-[10px] sm:text-[11px] text-[#A1A1AA] mt-0.5">
                      Last reminder dispatched: {new Date(summary.lastProcessedAt).toLocaleString(getLocale())}
                    </p>
                  )}
                </div>
              </div>
            </HoverTip>
          </>
        )}

        <SettingsSheet
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          settings={settings}
          onSaved={(saved) => {
            setSettings(saved);
            fetchData();
          }}
        />

        {drawerInvoiceId && (
          <InvoiceDrawer
            invoiceId={drawerInvoiceId}
            onClose={() => setDrawerInvoiceId(null)}
            onChanged={fetchData}
          />
        )}
      </motion.div>
    </TooltipProvider>
  );
};

export default InvoiceRemindersDashboard;
