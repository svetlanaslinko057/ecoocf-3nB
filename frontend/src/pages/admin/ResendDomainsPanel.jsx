/**
 * ResendDomainsPanel — UI для управления доменами Resend прямо из админки.
 *
 * Возможности:
 *   • Список всех доменов аккаунта (status: verified / pending / failed / not_started)
 *   • Добавить домен (POST /resend/domains) → сразу видим SPF + DKIM + DMARC записи
 *   • Просмотр DNS-инструкции с copy-кнопками для каждой записи
 *   • «Verify now» — триггерим повторную проверку DNS
 *   • Удалить домен
 *   • Авто-рефреш каждые 30с пока есть домены в pending
 *
 * Используется внутри IntegrationsPage.jsx когда раскрыта карточка Resend.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  Copy,
  Trash2,
  ExternalLink,
  Globe,
  Eye,
  AlertTriangle,
} from 'lucide-react';
import { useLang } from '../../i18n/LanguageContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const STATUS_STYLE = {
  verified:    { color: 'bg-emerald-50 text-emerald-700 ring-emerald-200', icon: CheckCircle2, label: 'verified'    },
  pending:     { color: 'bg-amber-50   text-amber-700   ring-amber-200',   icon: Clock,        label: 'pending'     },
  not_started: { color: 'bg-zinc-100   text-zinc-700    ring-zinc-200',    icon: Clock,        label: 'not started' },
  failed:      { color: 'bg-rose-50    text-rose-700    ring-rose-200',    icon: XCircle,      label: 'failed'      },
  temporary_failure: { color: 'bg-amber-50 text-amber-700 ring-amber-200', icon: AlertTriangle, label: 'temp. failure' },
};

const REGIONS = [
  { value: 'us-east-1',      label: 'US East (N. Virginia)' },
  { value: 'eu-west-1',      label: 'EU West (Ireland)' },
  { value: 'sa-east-1',      label: 'SA East (São Paulo)' },
  { value: 'ap-northeast-1', label: 'AP Northeast (Tokyo)' },
];

function copyToClipboard(text) {
  if (!text) return;
  try {
    navigator.clipboard.writeText(text);
    toast.success('Copied');
  } catch {
    toast.error('Copy failed');
  }
}

export default function ResendDomainsPanel({ hasApiKey }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState({});       // domainId -> full domain (with records[])
  const [openId, setOpenId] = useState(null);       // which domain is expanded
  const [verifying, setVerifying] = useState({});   // domainId -> bool
  const [deleting, setDeleting] = useState({});     // domainId -> bool

  // Add form
  const [newDomain, setNewDomain] = useState('');
  const [newRegion, setNewRegion] = useState('us-east-1');
  const [adding, setAdding] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const fetchList = useCallback(async () => {
    if (!hasApiKey) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/integrations/resend/domains`, { headers: authHeaders() });
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load domains');
    } finally {
      setLoading(false);
    }
  }, [hasApiKey]);

  const fetchDetail = useCallback(async (domainId) => {
    try {
      const r = await axios.get(`${API_URL}/api/admin/integrations/resend/domains/${domainId}`, { headers: authHeaders() });
      setDetails((prev) => ({ ...prev, [domainId]: r.data?.domain || null }));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load DNS records');
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  // Auto-refresh every 30s if there are non-verified domains
  useEffect(() => {
    if (!hasApiKey) return undefined;
    const hasPending = items.some((d) => d.status !== 'verified');
    if (!hasPending) return undefined;
    const timer = setInterval(fetchList, 30000);
    return () => clearInterval(timer);
  }, [items, fetchList, hasApiKey]);

  const toggleOpen = async (domainId) => {
    if (openId === domainId) {
      setOpenId(null);
      return;
    }
    setOpenId(domainId);
    if (!details[domainId]) await fetchDetail(domainId);
  };

  const handleAdd = async () => {
    const name = (newDomain || '').trim().toLowerCase();
    if (!name || !name.includes('.')) {
      toast.error(t('resendDomainInvalid'));
      return;
    }
    setAdding(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/integrations/resend/domains`,
        { name, region: newRegion },
        { headers: authHeaders() },
      );
      const created = r.data?.domain;
      toast.success(t('resendDomainAdded').replace('{name}', name));
      setNewDomain('');
      setShowAdd(false);
      await fetchList();
      // Auto-expand the newly added domain so the admin sees the DNS records
      if (created?.id) {
        setDetails((prev) => ({ ...prev, [created.id]: created }));
        setOpenId(created.id);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to add domain');
    } finally {
      setAdding(false);
    }
  };

  const handleVerify = async (domainId) => {
    setVerifying((v) => ({ ...v, [domainId]: true }));
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/integrations/resend/domains/${domainId}/verify`,
        {},
        { headers: authHeaders() },
      );
      const fresh = r.data?.domain;
      if (fresh) setDetails((prev) => ({ ...prev, [domainId]: fresh }));
      if (fresh?.status === 'verified') {
        toast.success(t('resendDomainVerified').replace('{name}', fresh.name));
      } else {
        toast.info(t('resendDomainStatusUnknown').replace('{status}', fresh?.status || 'unknown'));
      }
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verify failed');
    } finally {
      setVerifying((v) => ({ ...v, [domainId]: false }));
    }
  };

  const handleDelete = async (domain) => {
    if (!window.confirm(t('resendConfirmDeleteDomain').replace('{name}', domain.name))) return;
    setDeleting((d) => ({ ...d, [domain.id]: true }));
    try {
      await axios.delete(
        `${API_URL}/api/admin/integrations/resend/domains/${domain.id}`,
        { headers: authHeaders() },
      );
      toast.success(t('resendDomainDeleted').replace('{name}', domain.name));
      if (openId === domain.id) setOpenId(null);
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    } finally {
      setDeleting((d) => ({ ...d, [domain.id]: false }));
    }
  };

  if (!hasApiKey) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12.5px] text-amber-800 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>
          Сначала введите Resend API Key выше и нажмите <b>Save</b>. После этого
          здесь появится возможность управлять доменами.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-[#71717A]" />
          <h4 className="text-[13px] font-semibold text-[#18181B]">
            Sender Domains
          </h4>
          <span className="text-[11.5px] text-[#71717A]">
            ({items.length})
          </span>
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
            data-testid="resend-add-domain-toggle"
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-[#18181B] text-white text-[12px] font-medium hover:bg-[#27272A]"
          >
            <Plus className="w-3.5 h-3.5" />
            Add domain
          </button>
        </div>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] p-3 space-y-2.5">
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">
                Domain name
              </label>
              <input
                type="text"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="bibi.cars"
                className="w-full h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
                data-testid="resend-new-domain"
              />
            </div>
            <div className="min-w-[180px]">
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">
                Region
              </label>
              <select
                value={newRegion}
                onChange={(e) => setNewRegion(e.target.value)}
                className="w-full h-9 px-2 rounded-lg border border-[#E4E4E7] bg-white text-[13px]"
                data-testid="resend-new-region"
              >
                {REGIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <button
              type="button"
              onClick={handleAdd}
              disabled={adding || !newDomain}
              className="h-9 px-3 rounded-lg bg-emerald-600 text-white text-[12.5px] font-medium hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="resend-add-confirm"
            >
              <Plus className={`w-3.5 h-3.5 ${adding ? 'animate-pulse' : ''}`} />
              {adding ? 'Adding…' : 'Add'}
            </button>
            <button
              type="button"
              onClick={() => { setShowAdd(false); setNewDomain(''); }}
              className="h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[12.5px] text-[#71717A] hover:bg-[#FAFAFA]"
            >
              Cancel
            </button>
          </div>
          <p className="text-[11px] text-[#71717A] leading-relaxed">
            После добавления Resend выдаст 3 DNS-записи (SPF + DKIM + DMARC).
            Скопируйте их в DNS-провайдер (Cloudflare / Namecheap / GoDaddy…),
            дождитесь распространения (5-30 мин), затем нажмите <b>Verify now</b>.
          </p>
        </div>
      )}

      {/* Domain list */}
      {items.length === 0 && !loading ? (
        <div className="rounded-xl border border-dashed border-[#E4E4E7] p-6 text-center text-[12.5px] text-[#71717A]">
          В вашем Resend-аккаунте ещё нет доменов. Нажмите <b>Add domain</b> чтобы добавить первый.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((d) => {
            const s = STATUS_STYLE[d.status] || STATUS_STYLE.failed;
            const StatusIcon = s.icon;
            const isOpen = openId === d.id;
            const detail = details[d.id];
            const isVerified = d.status === 'verified';
            return (
              <div key={d.id} className="rounded-xl border border-[#E4E4E7] bg-white overflow-hidden">
                {/* Row */}
                <div className="px-3.5 py-2.5 flex items-center gap-3 flex-wrap">
                  <button
                    type="button"
                    onClick={() => toggleOpen(d.id)}
                    className="flex items-center gap-2 min-w-0 flex-1 text-left"
                    data-testid={`resend-domain-${d.name}`}
                  >
                    <span className="font-mono text-[13.5px] font-semibold text-[#18181B] truncate">
                      {d.name}
                    </span>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-semibold ring-1 ${s.color} shrink-0`}>
                      <StatusIcon className="w-3 h-3" /> {s.label}
                    </span>
                    <span className="text-[10.5px] text-[#A1A1AA] hidden sm:inline shrink-0">
                      · {d.region}
                    </span>
                  </button>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {!isVerified && (
                      <button
                        type="button"
                        onClick={() => handleVerify(d.id)}
                        disabled={verifying[d.id]}
                        className="inline-flex items-center gap-1 h-7 px-2.5 rounded-lg bg-[#18181B] text-white text-[11px] font-medium hover:bg-[#27272A] disabled:opacity-50"
                        data-testid={`resend-verify-${d.name}`}
                      >
                        <RefreshCw className={`w-3 h-3 ${verifying[d.id] ? 'animate-spin' : ''}`} />
                        {verifying[d.id] ? 'Verifying…' : 'Verify now'}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => toggleOpen(d.id)}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-lg border border-[#E4E4E7] hover:bg-[#FAFAFA]"
                      title="View DNS records"
                    >
                      <Eye className="w-3.5 h-3.5 text-[#71717A]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(d)}
                      disabled={deleting[d.id]}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-lg border border-rose-100 bg-white text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                      title="Delete domain"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* DNS records (expanded) */}
                {isOpen && (
                  <div className="border-t border-[#F4F4F5] bg-[#FAFAFA] p-3 space-y-2">
                    {!detail ? (
                      <p className="text-[12px] text-[#71717A]">Loading DNS records…</p>
                    ) : (
                      <>
                        <div className="flex items-baseline justify-between flex-wrap gap-2">
                          <p className="text-[11px] uppercase tracking-wider text-[#71717A] font-semibold">
                            DNS records to add at your domain registrar
                          </p>
                          <a
                            href={`https://resend.com/domains/${d.id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] text-[#18181B] hover:underline"
                          >
                            Open in Resend <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-[12px]">
                            <thead className="text-[10px] uppercase tracking-wider text-[#71717A]">
                              <tr>
                                <th className="text-left py-1.5 pr-2">Status</th>
                                <th className="text-left py-1.5 pr-2">Type</th>
                                <th className="text-left py-1.5 pr-2">Name / Host</th>
                                <th className="text-left py-1.5 pr-2">Value</th>
                                <th className="text-left py-1.5 pr-2">TTL / Priority</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(detail.records || []).map((rec, idx) => {
                                const rs = STATUS_STYLE[rec.status] || STATUS_STYLE.pending;
                                const RIcon = rs.icon;
                                // Build the "Name" the user should put in DNS: for empty/@ root use @
                                const dnsName = rec.name ? `${rec.name}.${detail.name}` : detail.name;
                                return (
                                  <tr key={idx} className="border-t border-[#E4E4E7] align-top">
                                    <td className="py-2 pr-2">
                                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ring-1 ${rs.color}`}>
                                        <RIcon className="w-2.5 h-2.5" /> {rs.label}
                                      </span>
                                    </td>
                                    <td className="py-2 pr-2 font-mono text-[11.5px] font-semibold text-[#18181B]">
                                      {rec.type}
                                      <div className="text-[10px] text-[#A1A1AA] font-sans font-normal">
                                        {rec.record}
                                      </div>
                                    </td>
                                    <td className="py-2 pr-2 font-mono text-[11.5px] text-[#18181B] break-all max-w-[180px]">
                                      <div className="flex items-start gap-1">
                                        <span className="flex-1">{dnsName}</span>
                                        <button
                                          type="button"
                                          onClick={() => copyToClipboard(dnsName)}
                                          className="shrink-0 p-1 rounded hover:bg-white"
                                          title="Copy name"
                                        >
                                          <Copy className="w-3 h-3 text-[#71717A]" />
                                        </button>
                                      </div>
                                    </td>
                                    <td className="py-2 pr-2 font-mono text-[11px] text-[#3F3F46] break-all max-w-[320px]">
                                      <div className="flex items-start gap-1">
                                        <span className="flex-1">{rec.value}</span>
                                        <button
                                          type="button"
                                          onClick={() => copyToClipboard(rec.value)}
                                          className="shrink-0 p-1 rounded hover:bg-white"
                                          title="Copy value"
                                        >
                                          <Copy className="w-3 h-3 text-[#71717A]" />
                                        </button>
                                      </div>
                                    </td>
                                    <td className="py-2 pr-2 text-[11.5px] text-[#71717A] tabular-nums">
                                      {rec.ttl || 'Auto'}
                                      {rec.priority !== undefined && (
                                        <div className="text-[10px]">prio: {rec.priority}</div>
                                      )}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                        <div className="rounded-lg bg-white border border-[#E4E4E7] px-3 py-2 text-[11px] text-[#71717A] leading-relaxed">
                          <b className="text-[#18181B]">{t('resendWhatToDo')}</b> {t('resendDnsInstr')} <b>Verify now</b>.
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
