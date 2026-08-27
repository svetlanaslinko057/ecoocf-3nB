/**
 * BIBI Cars — Wave 2A — CallsTab
 * ================================
 *
 * Customer360 tab body — lists Ringostat calls aggregated for one customer.
 * Filters: date range, manager, direction, with-recording.
 * Row click → CallDrawer (audio + metadata + existing AI block).
 *
 * Read-only. No new AI generation here.
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneX,
  Funnel,
  ArrowClockwise,
  PlayCircle,
  WaveSine,
} from '@phosphor-icons/react';
import { API_URL } from '../../App';
import { useLang } from '../../i18n';
import useManagersMap from '../../hooks/useManagersMap';
import CallDrawer from './CallDrawer';
import MatchChips from './MatchChips';
import CallsDiagnostics from './CallsDiagnostics';

const ADMIN_ROLES = new Set(['admin', 'owner', 'master_admin']);

const formatDuration = (sec) => {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
};

const formatDateTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
};

const directionIcon = (dir) => {
  if (dir === 'inbound') return <PhoneIncoming size={16} weight="duotone" className="text-emerald-600" />;
  if (dir === 'outbound') return <PhoneOutgoing size={16} weight="duotone" className="text-sky-600" />;
  return <Phone size={16} weight="duotone" className="text-zinc-500" />;
};

const statusBadge = (status) => {
  const s = (status || '').toUpperCase();
  const cls = s === 'ANSWERED'
    ? 'bg-emerald-100 text-emerald-700'
    : s === 'MISSED'
    ? 'bg-rose-100 text-rose-700'
    : 'bg-zinc-100 text-zinc-600';
  return <span className={`text-[11px] px-1.5 py-0.5 rounded-md font-medium ${cls}`}>{s || '—'}</span>;
};

const outcomeBadge = (outcome) => {
  if (!outcome) return <span className="text-zinc-400">—</span>;
  const palette = {
    interested:    'bg-emerald-50 text-emerald-700 border-emerald-200',
    ready_deposit: 'bg-violet-50 text-violet-700 border-violet-200',
    vin_request:   'bg-sky-50 text-sky-700 border-sky-200',
    callback:      'bg-amber-50 text-amber-700 border-amber-200',
    reject:        'bg-rose-50 text-rose-700 border-rose-200',
    next_step:     'bg-zinc-50 text-zinc-700 border-zinc-200',
  };
  const cls = palette[outcome] || palette.next_step;
  return <span className={`text-[11px] px-2 py-0.5 rounded-full border ${cls}`}>{outcome.replace('_', ' ')}</span>;
};

const CallsTab = ({ customerId, customerRole }) => {
  const { t } = useLang();
  const { managers: managersMap } = useManagersMap();
  const managersList = useMemo(() => {
    const out = Object.values(managersMap || {});
    out.sort((a, b) => (a?.name || '').localeCompare(b?.name || ''));
    return out;
  }, [managersMap]);

  const [filters, setFilters] = useState({
    dateFrom: '',
    dateTo: '',
    managerId: '',
    direction: 'all',
    withRecording: false,
  });
  const [calls, setCalls] = useState([]);
  const [total, setTotal] = useState(0);
  const [sources, setSources] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCall, setSelectedCall] = useState(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const isAdmin = ADMIN_ROLES.has((customerRole || '').toLowerCase());

  const fetchCalls = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters.dateFrom) params.set('dateFrom', new Date(filters.dateFrom).toISOString());
      if (filters.dateTo) {
        // dateTo at end of day
        const dt = new Date(filters.dateTo);
        dt.setHours(23, 59, 59, 999);
        params.set('dateTo', dt.toISOString());
      }
      if (filters.managerId) params.set('managerId', filters.managerId);
      if (filters.direction && filters.direction !== 'all') params.set('direction', filters.direction);
      if (filters.withRecording) params.set('withRecording', 'true');
      params.set('limit', '200');

      const res = await axios.get(`${API_URL}/api/customers/${customerId}/calls?${params}`);
      if (res.data?.success) {
        setCalls(res.data.calls || []);
        setTotal(res.data.total || 0);
        setSources(res.data.sources || null);
      } else {
        throw new Error(res.data?.error || 'Failed to load calls');
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to load calls';
      setError(msg);
      if (e?.response?.status !== 401) toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [customerId, filters]);

  useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  const clearFilters = () => setFilters({
    dateFrom: '', dateTo: '', managerId: '', direction: 'all', withRecording: false,
  });

  const activeFilterCount =
    (filters.dateFrom ? 1 : 0) +
    (filters.dateTo ? 1 : 0) +
    (filters.managerId ? 1 : 0) +
    (filters.direction !== 'all' ? 1 : 0) +
    (filters.withRecording ? 1 : 0);

  return (
    <div className="section-card" data-testid="calls-tab">
      <div className="flex items-center justify-between mb-4">
        <div className="section-title-clean !mb-0">
          <WaveSine size={22} weight="duotone" className="text-[#4F46E5]" />
          <span>{t('w2a_calls_tab_title') || 'Calls & AI'}</span>
          <span className="ml-2 text-sm font-normal text-[#71717A]">({total})</span>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <button
              onClick={() => setDiagnosticsOpen(true)}
              className="text-xs px-3 py-1.5 border border-[#E4E4E7] rounded-md hover:bg-zinc-50 flex items-center gap-1.5"
              data-testid="calls-diagnostics-open"
              title={t('w2a_diag_subtitle') || 'Why calls match this customer'}
            >
              <Funnel size={14} weight="duotone" />
              {t('w2a_diag_button') || 'Diagnostics'}
            </button>
          )}
          <button
            onClick={fetchCalls}
            disabled={loading}
            className="text-xs px-3 py-1.5 border border-[#E4E4E7] rounded-md hover:bg-zinc-50 disabled:opacity-50 flex items-center gap-1.5"
            data-testid="calls-refresh"
          >
            <ArrowClockwise size={14} weight={loading ? 'fill' : 'duotone'} className={loading ? 'animate-spin' : ''} />
            {t('w2a_refresh') || 'Refresh'}
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-[#F8FAFC] border border-[#E4E4E7] rounded-lg p-3 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col">
            <label className="text-[11px] uppercase tracking-wide text-[#71717A] mb-0.5">{t('w2a_date_from') || 'From'}</label>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
              className="text-sm border border-[#E4E4E7] rounded-md px-2 py-1.5 bg-white"
              data-testid="calls-filter-date-from"
            />
          </div>
          <div className="flex flex-col">
            <label className="text-[11px] uppercase tracking-wide text-[#71717A] mb-0.5">{t('w2a_date_to') || 'To'}</label>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
              className="text-sm border border-[#E4E4E7] rounded-md px-2 py-1.5 bg-white"
              data-testid="calls-filter-date-to"
            />
          </div>
          <div className="flex flex-col">
            <label className="text-[11px] uppercase tracking-wide text-[#71717A] mb-0.5">{t('w2a_manager') || 'Manager'}</label>
            <select
              value={filters.managerId}
              onChange={(e) => setFilters((f) => ({ ...f, managerId: e.target.value }))}
              className="text-sm border border-[#E4E4E7] rounded-md px-2 py-1.5 bg-white min-w-[160px]"
              data-testid="calls-filter-manager"
            >
              <option value="">{t('w2a_all_managers') || 'All managers'}</option>
              {managersList.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-[11px] uppercase tracking-wide text-[#71717A] mb-0.5">{t('w2a_direction') || 'Direction'}</label>
            <select
              value={filters.direction}
              onChange={(e) => setFilters((f) => ({ ...f, direction: e.target.value }))}
              className="text-sm border border-[#E4E4E7] rounded-md px-2 py-1.5 bg-white"
              data-testid="calls-filter-direction"
            >
              <option value="all">{t('w2a_all') || 'All'}</option>
              <option value="inbound">{t('w2a_inbound') || 'Inbound'}</option>
              <option value="outbound">{t('w2a_outbound') || 'Outbound'}</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm select-none cursor-pointer pb-1.5">
            <input
              type="checkbox"
              checked={filters.withRecording}
              onChange={(e) => setFilters((f) => ({ ...f, withRecording: e.target.checked }))}
              data-testid="calls-filter-with-recording"
            />
            <span>{t('w2a_with_recording') || 'With recording'}</span>
          </label>
          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              className="text-xs px-3 py-1.5 border border-[#E4E4E7] rounded-md hover:bg-white pb-1.5"
              data-testid="calls-filter-clear"
            >
              {t('w2a_clear_filters') || 'Clear'} ({activeFilterCount})
            </button>
          )}
        </div>
        {sources && (
          <div className="text-[11px] text-[#71717A] mt-2 flex flex-wrap gap-x-3">
            <span><Funnel size={10} className="inline mr-0.5" /> {t('w2a_sources_label') || 'Matched via'}:</span>
            {sources.leadIds?.length > 0 && <span>leadIds={sources.leadIds.length}</span>}
            {sources.dealIds?.length > 0 && <span>dealIds={sources.dealIds.length}</span>}
            {sources.phones?.length > 0 && <span>phones={sources.phones.length}</span>}
          </div>
        )}
      </div>

      {/* Body */}
      {loading && calls.length === 0 ? (
        <div className="py-10 text-center text-[#71717A] text-sm" data-testid="calls-loading">
          {t('w2a_loading') || 'Loading calls…'}
        </div>
      ) : error ? (
        <div className="py-10 text-center text-rose-600 text-sm" data-testid="calls-error">{error}</div>
      ) : calls.length === 0 ? (
        <div className="py-12 text-center text-[#71717A]" data-testid="calls-empty">
          <Phone size={32} weight="duotone" className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-sm">{t('w2a_empty') || 'No calls match the current filters.'}</p>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-1" data-testid="calls-table-wrap">
          <table className="w-full text-sm" data-testid="calls-table">
            <thead>
              <tr className="border-b border-[#E4E4E7] text-left text-[12px] uppercase tracking-wide text-[#71717A]">
                <th className="py-2 px-2">{t('w2a_col_date') || 'Date'}</th>
                <th className="py-2 px-2">{t('w2a_col_direction') || 'Direction'}</th>
                <th className="py-2 px-2">{t('w2a_col_manager') || 'Manager'}</th>
                <th className="py-2 px-2">{t('w2a_col_duration') || 'Duration'}</th>
                <th className="py-2 px-2">{t('w2a_col_outcome') || 'Outcome'}</th>
                <th className="py-2 px-2">{t('w2a_col_status') || 'Status'}</th>
                <th className="py-2 px-2">{t('w2a_col_match') || 'Match'}</th>
                <th className="py-2 px-2 text-center">{t('w2a_col_recording') || 'Rec.'}</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c, idx) => (
                <tr
                  key={c.id || idx}
                  onClick={() => setSelectedCall(c)}
                  className="border-b border-[#F4F4F5] hover:bg-zinc-50 cursor-pointer"
                  data-testid={`calls-row-${idx}`}
                >
                  <td className="py-2 px-2 whitespace-nowrap">{formatDateTime(c.startedAt)}</td>
                  <td className="py-2 px-2">
                    <div className="flex items-center gap-1.5">
                      {directionIcon(c.direction)}
                      <span className="text-xs text-[#52525B]">{c.direction}</span>
                    </div>
                  </td>
                  <td className="py-2 px-2">{c.manager?.name || <span className="text-zinc-400">—</span>}</td>
                  <td className="py-2 px-2 tabular-nums">{formatDuration(c.duration)}</td>
                  <td className="py-2 px-2">{outcomeBadge(c.outcome)}</td>
                  <td className="py-2 px-2">{statusBadge(c.status)}</td>
                  <td className="py-2 px-2">
                    <MatchChips matchedBy={c.matchedBy} reasons={c.matchedReasons} size="xs" />
                  </td>
                  <td className="py-2 px-2 text-center">
                    {c.recordingAvailable ? (
                      <PlayCircle size={20} weight="duotone" className="text-[#4F46E5] inline" />
                    ) : (
                      <PhoneX size={16} className="text-zinc-300 inline" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedCall && (
        <CallDrawer
          call={selectedCall}
          onClose={() => setSelectedCall(null)}
        />
      )}

      <CallsDiagnostics
        customerId={customerId}
        open={diagnosticsOpen}
        onClose={() => setDiagnosticsOpen(false)}
      />
    </div>
  );
};

export default CallsTab;
