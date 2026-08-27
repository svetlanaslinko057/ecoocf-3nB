/**
 * ResendWebhooksPanel — управление Resend webhook’ами + просмотр статистики событий.
 *
 * Возможности:
 *   • Список webhook’ов (endpoint_url / events / status)
 *   • Создать webhook с подстановкой нашего receiver URL по умолчанию
 *   • Чекбоксы для выбора событий (delivered / bounced / complained / opened / clicked / ...)
 *   • После создания — модалка с webhook secret (whsec_xxx, нужен для Svix validation)
 *   • Удалить webhook
 *   • Stats: счётчики delivered / bounced / complained за последние 30 дней
 *
 * Когда webhook создан и DNS-домен верифицирован — каждое отправленное письмо
 * автоматически апдейтится в email_outbox: events.delivered / events.bounced / ...
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus,
  RefreshCw,
  Trash2,
  Copy,
  Webhook,
  AlertTriangle,
  Eye,
  EyeOff,
  CheckCircle2,
  Send,
  X,
  TrendingUp,
} from 'lucide-react';
import { useLang } from '../../i18n/LanguageContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const EVENT_LABELS = {
  'email.sent':             { label: 'Sent',             color: 'bg-zinc-100 text-zinc-700' },
  'email.delivered':        { label: 'Delivered',        color: 'bg-emerald-50 text-emerald-700' },
  'email.delivery_delayed': { label: 'Delivery delayed', color: 'bg-amber-50 text-amber-700' },
  'email.bounced':          { label: 'Bounced',          color: 'bg-rose-50 text-rose-700' },
  'email.complained':       { label: 'Complained',       color: 'bg-rose-50 text-rose-700' },
  'email.opened':           { label: 'Opened',           color: 'bg-sky-50 text-sky-700' },
  'email.clicked':          { label: 'Clicked',          color: 'bg-sky-50 text-sky-700' },
  'email.failed':           { label: 'Failed',           color: 'bg-rose-50 text-rose-700' },
};

const STAT_LABELS = {
  delivered:         { label: 'Delivered',         color: 'text-emerald-700' },
  bounced:           { label: 'Bounced',           color: 'text-rose-700'    },
  complained:        { label: 'Complained',        color: 'text-rose-700'    },
  opened:            { label: 'Opened',            color: 'text-sky-700'     },
  clicked:           { label: 'Clicked',           color: 'text-sky-700'     },
  delivery_delayed:  { label: 'Delayed',           color: 'text-amber-700'   },
};

function copyToClipboard(text) {
  if (!text) return;
  try {
    navigator.clipboard.writeText(text);
    toast.success('Copied');
  } catch {
    toast.error('Copy failed');
  }
}

export default function ResendWebhooksPanel({ hasApiKey }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [availableEvents, setAvailableEvents] = useState([]);
  const [suggestedUrl, setSuggestedUrl] = useState('');
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);

  const [showAdd, setShowAdd] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newEvents, setNewEvents] = useState(new Set([
    'email.delivered', 'email.bounced', 'email.complained', 'email.failed', 'email.opened', 'email.clicked',
  ]));
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState({});

  // Secret modal (Resend returns it on create — needed for Svix validation)
  const [createdSecret, setCreatedSecret] = useState(null); // { url, secret }
  const [secretVisible, setSecretVisible] = useState(false);

  const fetchList = useCallback(async () => {
    if (!hasApiKey) return;
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        axios.get(`${API_URL}/api/admin/integrations/resend/webhooks`, { headers: authHeaders() }),
        axios.get(`${API_URL}/api/admin/integrations/resend/webhook-stats`, { headers: authHeaders() }),
      ]);
      setItems(r1.data?.items || []);
      setAvailableEvents(r1.data?.available_events || []);
      const suggested = r1.data?.suggested_receiver_url || '';
      setSuggestedUrl(suggested);
      if (!newUrl) setNewUrl(suggested);
      setStats(r2.data?.stats_30d || {});
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load webhooks');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasApiKey]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleCreate = async () => {
    const url = (newUrl || '').trim();
    if (!url.startsWith('http')) {
      toast.error(t('resendEndpointHttps'));
      return;
    }
    if (newEvents.size === 0) {
      toast.error(t('resendSelectAtLeastOneEvent'));
      return;
    }
    setAdding(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/integrations/resend/webhooks`,
        { endpoint_url: url, events: Array.from(newEvents) },
        { headers: authHeaders() },
      );
      const created = r.data?.webhook;
      const secret = created?.secret || created?.signing_secret;
      if (secret) {
        setCreatedSecret({ url: created.endpoint_url || url, secret });
      }
      toast.success(t('resendWebhookCreated'));
      setShowAdd(false);
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create webhook');
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (wh) => {
    if (!window.confirm(t('resendConfirmDeleteWebhook').replace('{url}', wh.endpoint_url))) return;
    setDeleting((d) => ({ ...d, [wh.id]: true }));
    try {
      await axios.delete(
        `${API_URL}/api/admin/integrations/resend/webhooks/${wh.id}`,
        { headers: authHeaders() },
      );
      toast.success(t('resendWebhookDeleted'));
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    } finally {
      setDeleting((d) => ({ ...d, [wh.id]: false }));
    }
  };

  const toggleEvent = (ev) => {
    setNewEvents((prev) => {
      const next = new Set(prev);
      if (next.has(ev)) next.delete(ev); else next.add(ev);
      return next;
    });
  };

  if (!hasApiKey) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12.5px] text-amber-800 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{t('resendNeedSaveMainKey')}</span>
      </div>
    );
  }

  const statKeys = ['delivered', 'bounced', 'complained', 'opened', 'clicked', 'delivery_delayed'];

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Webhook className="w-4 h-4 text-[#71717A]" />
          <h4 className="text-[13px] font-semibold text-[#18181B]">Webhooks</h4>
          <span className="text-[11.5px] text-[#71717A]">({items.length})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={fetchList}
            disabled={loading}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white border border-[#E4E4E7] hover:bg-[#FAFAFA] disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#71717A] ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => setShowAdd(!showAdd)}
            data-testid="resend-add-webhook-toggle"
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-[#18181B] text-white text-[12px] font-medium hover:bg-[#27272A]"
          >
            <Plus className="w-3.5 h-3.5" />
            New webhook
          </button>
        </div>
      </div>

      {/* Stats grid (30d) */}
      <div className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] p-3">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="w-3.5 h-3.5 text-[#71717A]" />
          <p className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold">
            Event stats · last 30 days
          </p>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {statKeys.map((k) => {
            const meta = STAT_LABELS[k];
            const v = stats[k] || 0;
            return (
              <div key={k} className="bg-white border border-[#E4E4E7] rounded-lg px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-wider text-[#71717A] font-semibold">{meta.label}</p>
                <p className={`text-[18px] font-bold tabular-nums ${meta.color} leading-tight mt-0.5`}>{v}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] p-3 space-y-3">
          <div>
            <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">Endpoint URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://yourdomain.com/api/webhooks/resend/events"
                className="flex-1 h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
                data-testid="resend-new-webhook-url"
              />
              {suggestedUrl && newUrl !== suggestedUrl && (
                <button
                  type="button"
                  onClick={() => setNewUrl(suggestedUrl)}
                  className="h-9 px-2.5 rounded-lg border border-[#E4E4E7] bg-white text-[11.5px] text-[#71717A] hover:bg-[#FAFAFA] whitespace-nowrap"
                  title="Use our receiver"
                >
                  Use ours
                </button>
              )}
            </div>
            {suggestedUrl === newUrl && (
              <p className="text-[11px] text-emerald-700 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                Используется наш receiver — события автоматически обновят email_outbox.
              </p>
            )}
          </div>

          <div>
            <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1.5">Events</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {availableEvents.map((ev) => {
                const checked = newEvents.has(ev);
                const meta = EVENT_LABELS[ev] || { label: ev, color: 'bg-zinc-100 text-zinc-700' };
                return (
                  <label
                    key={ev}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-pointer text-[11.5px] ${
                      checked ? 'border-[#18181B] bg-[#18181B] text-white' : 'border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[#3F3F46]'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleEvent(ev)}
                      className="sr-only"
                    />
                    <span className={`w-3 h-3 rounded border-2 flex items-center justify-center ${checked ? 'bg-white border-white' : 'border-[#A1A1AA]'}`}>
                      {checked && <CheckCircle2 className="w-2.5 h-2.5 text-[#18181B]" />}
                    </span>
                    <span>{meta.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCreate}
              disabled={adding || !newUrl}
              className="h-9 px-3 rounded-lg bg-emerald-600 text-white text-[12.5px] font-medium hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="resend-create-webhook"
            >
              <Plus className={`w-3.5 h-3.5 ${adding ? 'animate-pulse' : ''}`} />
              {adding ? 'Creating…' : 'Create webhook'}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[12.5px] text-[#71717A] hover:bg-[#FAFAFA]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Webhooks list */}
      {items.length === 0 && !loading ? (
        <div className="rounded-xl border border-dashed border-[#E4E4E7] p-6 text-center text-[12.5px] text-[#71717A]">
          В аккаунте Resend ещё нет webhook’ов. Создайте один — мы предзаполнили endpoint нашим receiver URL.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((w) => (
            <div key={w.id} className="rounded-xl border border-[#E4E4E7] bg-white p-3">
              <div className="flex items-center gap-3 flex-wrap mb-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <Send className="w-3.5 h-3.5 text-[#71717A] shrink-0" />
                  <span className="font-mono text-[12px] text-[#18181B] truncate">{w.endpoint_url}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(w)}
                  disabled={deleting[w.id]}
                  className="inline-flex items-center justify-center w-7 h-7 rounded-lg border border-rose-100 bg-white text-rose-600 hover:bg-rose-50 disabled:opacity-50 shrink-0"
                  title="Delete webhook"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                {(w.events || []).map((ev) => {
                  const meta = EVENT_LABELS[ev] || { label: ev, color: 'bg-zinc-100 text-zinc-700' };
                  return (
                    <span key={ev} className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${meta.color}`}>
                      {meta.label}
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Secret modal */}
      {createdSecret && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setCreatedSecret(null)}>
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <Webhook className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-[15px] font-semibold text-[#18181B]">Webhook created</h3>
                  <p className="text-[11.5px] text-[#71717A]">{t('resendSigningSecretSaved')}</p>
                </div>
              </div>
              <button type="button" onClick={() => setCreatedSecret(null)} className="p-1.5 rounded-lg hover:bg-[#FAFAFA]">
                <X className="w-4 h-4 text-[#71717A]" />
              </button>
            </div>

            <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5 text-[12px] text-sky-800 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                Webhook secret автоматически сохранён в integration_configs.resend.settings.webhook_secret —
                receiver-эндпоинт будет валидировать подписи Svix входящих событий.
              </span>
            </div>

            <div>
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">Signing secret (whsec_…)</label>
              <div className="flex items-center gap-2">
                <input
                  type={secretVisible ? 'text' : 'password'}
                  readOnly
                  value={createdSecret.secret}
                  className="flex-1 h-10 px-3 rounded-lg border border-[#E4E4E7] bg-[#FAFAFA] text-[13px] font-mono"
                />
                <button
                  type="button"
                  onClick={() => setSecretVisible(!secretVisible)}
                  className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-[#E4E4E7] hover:bg-[#FAFAFA]"
                >
                  {secretVisible ? <EyeOff className="w-4 h-4 text-[#71717A]" /> : <Eye className="w-4 h-4 text-[#71717A]" />}
                </button>
                <button
                  type="button"
                  onClick={() => copyToClipboard(createdSecret.secret)}
                  className="inline-flex items-center gap-1.5 h-10 px-3 rounded-lg bg-[#18181B] text-white text-[12.5px] font-medium hover:bg-[#27272A]"
                >
                  <Copy className="w-3.5 h-3.5" />
                  Copy
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setCreatedSecret(null)}
              className="w-full h-10 rounded-lg bg-[#18181B] text-white text-[13px] font-medium hover:bg-[#27272A]"
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
