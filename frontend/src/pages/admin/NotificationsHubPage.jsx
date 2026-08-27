/**
 * Master-Admin → Notifications (unified hub)
 *
 * Объединяет два ранее раздельных блока:
 *   - /admin/settings/notifications-rules  (КОГДА слать: события × аудитории × каналы)
 *   - /admin/settings/email-templates      (ЧТО слать: subject/html/text для UA/EN/BG)
 *
 * Логика и API остаются прежними — никакой деградации:
 *   GET   /api/admin/notification-rules                 — список правил
 *   PATCH /api/admin/notification-rules/{event}         — изменить правило
 *   GET   /api/admin/email-templates                    — список шаблонов
 *   POST  /api/admin/email-templates                    — создать шаблон
 *   PATCH /api/admin/email-templates/{id}               — изменить шаблон
 *   POST  /api/admin/notifications/test-dispatch        — тестовая отправка
 *
 * Дизайн: единый стиль ‘insights-карточек’ — белый фон, hairline border,
 * чёрные пилюли каналов, светлые ряды аудиторий. Side-drawer редактор
 * шаблона открывается прямо из карточки события.
 *
 * Хинты-тултипы при наведении — БЕЗ иконок «?». Просто наводим мышь.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../../i18n';
import RefreshButton from '../../components/ui/RefreshButton';
import WhiteSelect from '../../components/ui/WhiteSelect';
import IntegrationsPage from './IntegrationsPage';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui/tooltip';
import {
  Bell,
  Mail,
  Smartphone,
  ToggleLeft,
  ToggleRight,
  Play,
  Users,
  UserCircle,
  Shield,
  Crown,
  Cable,
  Send,
  CheckCircle2,
  PlayCircle,
  FileCheck2,
  AlertTriangle,
  Save,
  Eye,
  Search,
  X,
  FileText,
  Plus,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─────────────────────── Static meta ─────────────────────────────────────
const EVENT_META = {
  invoice_sent:          { icon: Send,           fallback: 'Invoice sent to client' },
  payment_confirmed:     { icon: CheckCircle2,   fallback: 'Payment confirmed' },
  order_started:         { icon: PlayCircle,     fallback: 'Order launched' },
  order_finished:        { icon: FileCheck2,     fallback: 'Order completed' },
  payment_reminder:      { icon: AlertTriangle,  fallback: 'Payment reminder' },
  provider_tier_changed: { icon: Shield,         fallback: 'Provider tier changed' },
};

const AUDIENCE = {
  customer:     { labelKey: 'customer',         icon: UserCircle },
  manager:      { labelKey: 'roleManager',      icon: Users },
  team_lead:    { labelKey: 'roleTeamLead',     icon: Shield },
  master_admin: { labelKey: 'roleMasterAdmin',  icon: Crown },
};

const CHANNELS = {
  email:  { labelKey: 'emailLabel',   icon: Mail,       tipKey: 'hub_tip_channel_email' },
  in_app: { labelKey: 'inAppChannel', icon: Bell,       tipKey: 'hub_tip_channel_inapp' },
  sms:    { labelKey: 'smsChannel',   icon: Smartphone, tipKey: 'hub_tip_channel_sms' },
};

// Только email-канал использует HTML-шаблоны. SMS/in-app тоже могут иметь
// текст, но сейчас в системе редактор привязан к email_templates → отображаем
// «шаблоны» только когда канал email включён ИЛИ когда хоть один шаблон уже
// есть в БД (для возможности правки наследия).
const LANGS = [
  { code: 'ua', flag: '🇺🇦', label: 'UA' },
  { code: 'en', flag: '🇬🇧', label: 'EN' },
];

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const humanizeEvent = (key = '') =>
  String(key)
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/^./, (c) => c.toUpperCase());

// Reusable hover tooltip — NO icon. Just wrap children, hover triggers panel.
const HoverTip = ({ text, side = 'top', children, asChild = true }) => {
  if (!text) return children;
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-xs bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg"
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// ─────────────────────── Template editor (side drawer) ───────────────────
const TemplateDrawer = ({ open, draft, onClose, onChange, onSave, onTest, t }) => {
  const [preview, setPreview] = useState(false);
  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    try { document.body.style.overflow = 'hidden'; } catch { /* ignore */ }
    return () => { try { document.body.style.overflow = ''; } catch { /* ignore */ } };
  }, [open]);

  if (!open || !draft) return null;
  return createPortal(
    <div className="fixed inset-0 flex" style={{ zIndex: 9999, isolation: 'isolate' }}>
      <div className="flex-1 bg-zinc-900/40" onClick={onClose} />
      <aside className="w-full max-w-3xl bg-white shadow-2xl overflow-y-auto">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-white border-b border-zinc-200 px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="min-w-0 flex items-start gap-3">
            <HoverTip text={t('hub_tip_close_editor')} side="bottom">
              <button
                onClick={onClose}
                className="shrink-0 inline-flex items-center justify-center h-9 w-9 rounded-xl bg-white border border-[#E4E4E7] hover:bg-zinc-50 text-[#18181B] transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                aria-label="Close"
                data-testid="template-drawer-close-btn"
              >
                <X className="w-4 h-4" />
              </button>
            </HoverTip>
            <div className="min-w-0">
              <h2 className="font-semibold text-zinc-900 whitespace-nowrap">
                {draft._new ? t('adm2_82976e2a87') : t('adm2_2474e2a1f6')}
              </h2>
              <p className="text-xs text-zinc-500 truncate">
                {EVENT_META[draft.event]?.fallback || draft.event}
                {' · '}
                {t(AUDIENCE[draft.audience]?.labelKey || 'unknownLabel')}
                {' · '}
                {LANGS.find((l) => l.code === draft.lang)?.flag} {draft.lang?.toUpperCase()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap shrink-0 justify-end">
            <HoverTip text={t('hub_tip_preview')} side="bottom">
              <button
                onClick={() => setPreview((p) => !p)}
                className="px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 rounded-lg text-sm text-zinc-700 flex items-center gap-1 whitespace-nowrap"
                data-testid="template-drawer-preview-btn"
              >
                <Eye className="w-4 h-4" /> {preview ? 'HTML' : 'Preview'}
              </button>
            </HoverTip>
            <HoverTip text={t('hub_tip_test_dispatch')} side="bottom">
              <button
                onClick={onTest}
                className="px-3 py-1.5 bg-white border border-[#E4E4E7] hover:bg-zinc-50 text-[#18181B] rounded-lg text-sm flex items-center gap-1 whitespace-nowrap"
                data-testid="template-drawer-test-btn"
              >
                <Send className="w-4 h-4" /> {t('adm_test')}
              </button>
            </HoverTip>
            <HoverTip text={t('hub_tip_save_template')} side="bottom">
              <button
                onClick={onSave}
                className="px-3 py-1.5 bg-[#18181B] hover:bg-[#27272A] text-white rounded-lg text-sm font-medium flex items-center gap-1 whitespace-nowrap"
                data-testid="template-drawer-save-btn"
              >
                <Save className="w-4 h-4" /> {t('saveAction')}
              </button>
            </HoverTip>
          </div>
        </div>

        <div className="p-4 sm:p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              {t('adm2_subject_e2f5e8da81')}
            </label>
            <input
              value={draft.subject || ''}
              onChange={(e) => onChange({ ...draft, subject: e.target.value })}
              placeholder="New invoice #{{ invoice.id }}"
              className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#18181B]/15 focus:border-[#18181B]"
              data-testid="template-drawer-subject-input"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              {t('htmlBody')}
            </label>
            {preview ? (
              <div
                className="border border-zinc-200 rounded-lg p-4 max-h-96 overflow-y-auto bg-white"
                dangerouslySetInnerHTML={{ __html: draft.html || '' }}
              />
            ) : (
              <textarea
                rows={12}
                value={draft.html || ''}
                onChange={(e) => onChange({ ...draft, html: e.target.value })}
                placeholder="<p>Hello {{ customer.name }},</p>"
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
                data-testid="template-drawer-html-textarea"
              />
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              {t('adm2_372a742777')}
            </label>
            <textarea
              rows={3}
              value={draft.text_template || ''}
              onChange={(e) => onChange({ ...draft, text_template: e.target.value })}
              placeholder="Plain-text fallback for clients without HTML support"
              className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
              data-testid="template-drawer-text-textarea"
            />
          </div>

          <div className="bg-zinc-50 border border-zinc-100 rounded-lg p-3 text-xs text-zinc-500">
            <p className="font-medium text-zinc-700 mb-1">{t('adm_available_tokens')}</p>
            <code className="text-[11px] leading-relaxed block">
              {'{{ customer.name }}  {{ customer.email }}  {{ invoice.id }}  {{ invoice.total_fmt }}  {{ invoice.currency }}'}
              <br />
              {'{{ order.id }}  {{ order.steps_total }}  {{ manager.name }}  {{ manager.email }}'}
            </code>
          </div>
        </div>
      </aside>
    </div>,
    document.body,
  );
};

// ─────────────────────── Main hub page ───────────────────────────────────
export default function NotificationsHubPage() {
  const { t } = useLang();

  const [rules, setRules] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState('');

  // Filters
  const [filterEvent, setFilterEvent] = useState('');
  const [filterAud, setFilterAud] = useState('');
  const [filterChannel, setFilterChannel] = useState('');
  const [search, setSearch] = useState('');

  // Editor drawer
  const [draft, setDraft] = useState(null);

  // Advanced engineering panel toggle (hides raw API keys / SMTP creds)
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // ─── Loaders ───────────────────────────────────────────────────────────
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [r, tpl] = await Promise.all([
        axios.get(`${API_URL}/api/admin/notification-rules`, { headers: authHeaders() }),
        axios.get(`${API_URL}/api/admin/email-templates`, { headers: authHeaders() }),
      ]);
      setRules(r.data?.items || []);
      setTemplates(tpl.data?.items || []);
    } catch {
      toast.error(t('loadingError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ─── Rule actions ──────────────────────────────────────────────────────
  const saveRule = async (event, patch) => {
    try {
      const r = await axios.patch(
        `${API_URL}/api/admin/notification-rules/${event}`,
        patch,
        { headers: authHeaders() },
      );
      setRules((prev) => prev.map((x) => (x.event === event ? r.data.rule : x)));
      toast.success(t('saved'));
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_fd77287f02'));
    }
  };

  const toggleEnabled = (rule) =>
    saveRule(rule.event, { enabled: !rule.enabled, targets: rule.targets || [] });

  const toggleChannel = (rule, audience, channel) => {
    const targets = (rule.targets || []).map((t0) => ({ ...t0, channels: [...(t0.channels || [])] }));
    let target = targets.find((x) => x.audience === audience);
    if (!target) {
      targets.push({ audience, channels: [channel] });
    } else {
      const has = target.channels.includes(channel);
      target.channels = has
        ? target.channels.filter((c) => c !== channel)
        : [...target.channels, channel];
      if (target.channels.length === 0) {
        targets.splice(targets.indexOf(target), 1);
      }
    }
    return saveRule(rule.event, { enabled: rule.enabled, targets });
  };

  const testDispatch = async (event) => {
    setTesting(event);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/notifications/test-dispatch`,
        { event },
        { headers: authHeaders() },
      );
      toast.success(`${t('r9_sent')} · ${t('r9_recipients_label')}: ${r.data?.dispatch?.total || 0}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_fd77287f02'));
    } finally {
      setTesting('');
    }
  };

  // ─── Template actions ──────────────────────────────────────────────────
  const findTemplate = useCallback(
    (event, audience, lang) =>
      templates.find(
        (tpl) => tpl.event === event && tpl.audience === audience && tpl.lang === lang,
      ),
    [templates],
  );

  const openTemplate = (event, audience, lang) => {
    const existing = findTemplate(event, audience, lang);
    if (existing) {
      setDraft({ ...existing });
    } else {
      setDraft({
        _new: true,
        id: null,
        event,
        audience,
        lang,
        subject: '',
        html: '<p></p>',
        text_template: '',
      });
    }
  };

  const saveTemplate = async () => {
    if (!draft) return;
    try {
      const existing = !draft._new && templates.some((i) => i.id === draft.id);
      if (existing) {
        const r = await axios.patch(
          `${API_URL}/api/admin/email-templates/${draft.id}`,
          {
            subject: draft.subject,
            html: draft.html,
            text_template: draft.text_template || '',
          },
          { headers: authHeaders() },
        );
        const updated = r.data?.template || draft;
        setTemplates((prev) => prev.map((x) => (x.id === draft.id ? updated : x)));
      } else {
        const r = await axios.post(
          `${API_URL}/api/admin/email-templates`,
          draft,
          { headers: authHeaders() },
        );
        const created = r.data?.template;
        if (created) {
          setTemplates((prev) => {
            const without = prev.filter((x) => x.id !== created.id);
            return [...without, created];
          });
        }
      }
      toast.success(t('adm_template_saved'));
      setDraft(null);
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_d1b0c19159'));
    }
  };

  const testFromDrawer = async () => {
    if (!draft?.event) return;
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/notifications/test-dispatch`,
        { event: draft.event },
        { headers: authHeaders() },
      );
      toast.success(`Dispatch OK · ${r.data?.dispatch?.total || 0} ${t('recipients')}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_425cb83731'));
    }
  };

  // ─── Filters ───────────────────────────────────────────────────────────
  const filteredRules = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rules.filter((rule) => {
      if (filterEvent && rule.event !== filterEvent) return false;
      if (filterAud) {
        const has = (rule.targets || []).some((tg) => tg.audience === filterAud);
        if (!has) return false;
      }
      if (filterChannel) {
        const has = (rule.targets || []).some((tg) =>
          (tg.channels || []).includes(filterChannel),
        );
        if (!has) return false;
      }
      if (q) {
        const eventLabel = (EVENT_META[rule.event]?.fallback || humanizeEvent(rule.event)).toLowerCase();
        if (!eventLabel.includes(q) && !rule.event.includes(q)) return false;
      }
      return true;
    });
  }, [rules, filterEvent, filterAud, filterChannel, search]);

  const hasChannel = (rule, audience, channel) => {
    const t0 = (rule.targets || []).find((x) => x.audience === audience);
    return !!t0 && t0.channels.includes(channel);
  };

  // ─── Render ────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Bell className="w-[18px] h-[18px]" />
          </div>
          <div className="flex-1 min-w-0">
            <HoverTip text={t('hub_tip_page_intro')} side="bottom">
              <h1
                className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words cursor-default"
                style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
              >
                {t('hub_title')}
              </h1>
            </HoverTip>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('hub_subtitle')}
            </p>
          </div>
          <div className="shrink-0">
            <RefreshButton
              onClick={loadAll}
              loading={loading}
              ariaLabel={t('adm_refresh_3')}
              testId="notifications-hub-refresh-button"
            />
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="mb-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))] sm:[grid-template-columns:minmax(280px,2fr)_repeat(3,minmax(180px,1fr))]">
        <div className="relative min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('hub_search_placeholder')}
            className="w-full pl-10 pr-3 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#18181B]/15 focus:border-[#18181B]"
            data-testid="notifications-hub-search-input"
          />
        </div>
        <WhiteSelect value={filterEvent} onChange={(e) => setFilterEvent(e.target.value)} data-testid="notifications-hub-event-select">
          <option value="">{t('allEvents')}</option>
          {Object.entries(EVENT_META).map(([k, v]) => (
            <option key={k} value={k}>{v.fallback}</option>
          ))}
        </WhiteSelect>
        <WhiteSelect value={filterAud} onChange={(e) => setFilterAud(e.target.value)} data-testid="notifications-hub-audience-select">
          <option value="">{t('allAudiences')}</option>
          {Object.entries(AUDIENCE).map(([k, v]) => (
            <option key={k} value={k}>{t(v.labelKey)}</option>
          ))}
        </WhiteSelect>
        <WhiteSelect value={filterChannel} onChange={(e) => setFilterChannel(e.target.value)} data-testid="notifications-hub-channel-select">
          <option value="">{t('hub_all_channels')}</option>
          {Object.entries(CHANNELS).map(([k, v]) => (
            <option key={k} value={k}>{t(v.labelKey)}</option>
          ))}
        </WhiteSelect>
      </div>

      {/* Event cards */}
      <div className="space-y-4">
        {filteredRules.map((rule) => {
          const meta = EVENT_META[rule.event] || { icon: Bell, fallback: humanizeEvent(rule.event) };
          const EvIcon = meta.icon;
          return (
            <div
              key={rule.event}
              className={`bg-white border rounded-2xl overflow-hidden transition-opacity ${
                rule.enabled ? 'border-[#E4E4E7]' : 'border-[#E4E4E7] opacity-60'
              }`}
              data-testid={`hub-event-card-${rule.event}`}
            >
              {/* Card header */}
              <div className="px-5 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E4E4E7] bg-zinc-50/40">
                <div className="min-w-0 flex items-center gap-3 flex-1">
                  <div className="w-10 h-10 rounded-xl bg-[#18181B]/5 text-[#18181B] flex items-center justify-center shrink-0">
                    <EvIcon className="w-[18px] h-[18px]" />
                  </div>
                  <div className="min-w-0">
                    <HoverTip text={t('hub_tip_event_name')} side="top">
                      <p className="text-base sm:text-lg font-semibold text-[#18181B] leading-tight break-words cursor-default">
                        {meta.fallback || humanizeEvent(rule.event)}
                      </p>
                    </HoverTip>
                    <p className="text-[11px] text-zinc-400 font-mono mt-0.5">{rule.event}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <HoverTip text={t('hub_tip_test_event')} side="top">
                    <button
                      onClick={() => testDispatch(rule.event)}
                      disabled={testing === rule.event || !rule.enabled}
                      className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-white border border-[#E4E4E7] hover:bg-[#FAFAFA] text-[#18181B] text-xs font-medium disabled:opacity-50 transition-colors"
                      data-testid={`hub-test-button-${rule.event}`}
                    >
                      <Play className="w-3.5 h-3.5" />
                      {t('adm_test')}
                    </button>
                  </HoverTip>
                  <HoverTip text={rule.enabled ? t('hub_tip_disable_event') : t('hub_tip_enable_event')} side="top">
                    <button
                      onClick={() => toggleEnabled(rule)}
                      className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-medium transition-colors ${
                        rule.enabled
                          ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                          : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                      }`}
                      data-testid={`hub-enabled-toggle-${rule.event}`}
                    >
                      {rule.enabled ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                      {rule.enabled ? t('adm2_26841eb416') : t('adm2_7e9d3ee2f5')}
                    </button>
                  </HoverTip>
                </div>
              </div>

              {/* Audience rows */}
              <ul className="divide-y divide-[#F4F4F5]" data-testid={`hub-audience-list-${rule.event}`}>
                {Object.entries(AUDIENCE)
                  .filter(([audKey]) => !filterAud || audKey === filterAud)
                  .map(([audKey, aud]) => {
                  const Icon = aud.icon;
                  const emailActive = hasChannel(rule, audKey, 'email');
                  return (
                    <li
                      key={audKey}
                      className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 sm:px-6 py-4"
                      data-testid={`hub-audience-row-${rule.event}-${audKey}`}
                    >
                      {/* Identity */}
                      <div className="flex items-center gap-3 min-w-[180px] flex-1">
                        <div className="w-11 h-11 rounded-xl bg-[#18181B]/5 flex items-center justify-center shrink-0">
                          <Icon className="w-5 h-5 text-[#18181B]" />
                        </div>
                        <p className="text-sm sm:text-base font-medium text-[#18181B] truncate">
                          {t(aud.labelKey)}
                        </p>
                      </div>

                      {/* Channels */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {Object.entries(CHANNELS).map(([chKey, ch]) => {
                          const ChIcon = ch.icon;
                          const active = hasChannel(rule, audKey, chKey);
                          return (
                            <HoverTip key={chKey} text={t(ch.tipKey)} side="top">
                              <button
                                onClick={() => toggleChannel(rule, audKey, chKey)}
                                disabled={!rule.enabled}
                                aria-pressed={active}
                                className={`inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                                  active
                                    ? 'bg-[#18181B] text-white border border-[#18181B] shadow-sm hover:bg-[#27272A]'
                                    : 'bg-white border border-[#E4E4E7] text-zinc-600 hover:bg-zinc-50'
                                }`}
                                data-testid={`hub-channel-button-${rule.event}-${audKey}-${chKey}`}
                              >
                                <ChIcon className="w-3.5 h-3.5" />
                                {t(ch.labelKey)}
                              </button>
                            </HoverTip>
                          );
                        })}
                      </div>

                      {/* Email templates per language */}
                      <div className="flex items-center gap-1.5 flex-wrap ml-auto">
                        <span className="text-[11px] uppercase tracking-wider text-zinc-400 mr-1 font-medium">
                          {t('hub_templates_label')}
                        </span>
                        {LANGS.map((L) => {
                          const exists = !!findTemplate(rule.event, audKey, L.code);
                          return (
                            <HoverTip
                              key={L.code}
                              text={
                                exists
                                  ? `${t('hub_tip_edit_template')} · ${L.label}`
                                  : `${t('hub_tip_create_template')} · ${L.label}`
                              }
                              side="top"
                            >
                              <button
                                onClick={() => openTemplate(rule.event, audKey, L.code)}
                                disabled={!emailActive && !exists}
                                className={`inline-flex items-center gap-1 h-8 px-2.5 rounded-md text-[11px] font-semibold uppercase tracking-wide transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
                                  exists
                                    ? 'bg-white border border-[#18181B]/15 text-[#18181B] hover:bg-zinc-50'
                                    : 'bg-white border border-dashed border-[#E4E4E7] text-zinc-400 hover:border-[#18181B]/40 hover:text-[#18181B]'
                                }`}
                                data-testid={`hub-template-pill-${rule.event}-${audKey}-${L.code}`}
                              >
                                <span aria-hidden>{L.flag}</span>
                                <span>{L.label}</span>
                                {exists ? (
                                  <FileText className="w-3 h-3" />
                                ) : (
                                  <Plus className="w-3 h-3" />
                                )}
                              </button>
                            </HoverTip>
                          );
                        })}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}

        {filteredRules.length === 0 && !loading && (
          <div className="text-center py-12 text-zinc-400 text-sm bg-white border border-dashed border-[#E4E4E7] rounded-2xl">
            {t('adm_no_rules_found')}
          </div>
        )}
      </div>

      {/* Channel Integrations footer — repackaged as collapsible business-friendly block */}
      <div className="mt-10">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Cable className="w-[18px] h-[18px]" />
          </div>
          <div className="min-w-0 flex-1">
            <HoverTip text={t('hub_tip_integrations')} side="top">
              <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight cursor-default">
                {t('hub_integrations_business_title')}
              </h2>
            </HoverTip>
            <p className="text-xs sm:text-sm text-gray-500 mt-1">
              {t('hub_integrations_business_subtitle')}
            </p>
          </div>
        </div>

        {/* Collapsible advanced wrapper — hides raw API keys / SMTP creds by default */}
        <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            className="w-full text-left px-5 sm:px-6 py-4 flex items-start gap-3 hover:bg-zinc-50/60 transition-colors"
            data-testid="hub-advanced-toggle"
            aria-expanded={advancedOpen}
          >
            {advancedOpen ? (
              <ChevronDown className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" />
            ) : (
              <ChevronRight className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold text-[#18181B] leading-tight">
                {advancedOpen
                  ? t('hub_integrations_hide_advanced')
                  : t('hub_integrations_show_advanced')}
              </span>
              <span className="block text-[12px] text-[#71717A] mt-1 leading-relaxed">
                {t('hub_integrations_advanced_hint')}
              </span>
            </div>
          </button>
          {advancedOpen ? (
            <div className="border-t border-[#E4E4E7] p-4 sm:p-5" data-testid="hub-advanced-panel">
              <IntegrationsPage embedded filterProviders={['resend', 'email', 'sms']} />
            </div>
          ) : null}
        </div>
      </div>

      {/* Side drawer */}
      <TemplateDrawer
        open={!!draft}
        draft={draft}
        onClose={() => setDraft(null)}
        onChange={setDraft}
        onSave={saveTemplate}
        onTest={testFromDrawer}
        t={t}
      />
    </div>
  );
}
