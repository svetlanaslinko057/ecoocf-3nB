import React from 'react';
import { Pencil, Trash, Receipt, UserPlus, ArrowsClockwise, Phone, User, Clock } from '@phosphor-icons/react';
import { Select, SelectContent, SelectItem, SelectTrigger } from '../ui/select';
import { LEAD_PIPELINE, STATUS_THEME, statusLabel, sourceLabel } from './leadConstants';
import LeadSlaBadge from './LeadSlaBadge';
import LeadSiteTemperatureBadge from './LeadSiteTemperatureBadge';
import { useLang } from '../../i18n/LanguageContext';

/**
 * Compact human delta — "5m", "3h", "2d", "Jan 4". Returns "—" for nothing.
 */
function relativeShort(iso) {
  if (!iso) return '—';
  try {
    const t = new Date(iso).getTime();
    if (isNaN(t)) return '—';
    const diffMs = Date.now() - t;
    if (diffMs < 0) return new Date(iso).toLocaleDateString();
    const m = Math.floor(diffMs / 60000);
    if (m < 1)  return 'now';
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    const d = Math.floor(h / 24);
    if (d < 14) return `${d}d`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return '—';
  }
}

/**
 * Table view of leads. Stateless — receives the items array + handlers.
 */
const LeadTableView = ({
  leads, lang, managers, loading, activityMap,
  selectedIds, setSelectedIds, canBulkActions,
  onOpenEdit, onDelete, onConvert, onReassign, onQuotes, onChangeStatus,
}) => {
  const { t } = useLang();
  const toggle = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };
  const toggleAll = (checked) => {
    if (checked) setSelectedIds(new Set(leads.map(l => l.id)));
    else setSelectedIds(new Set());
  };

  return (
    <div className="card overflow-hidden bg-white" data-testid="leads-table-view">
      <div className="overflow-x-auto">
        <table className="table-premium min-w-[900px] w-full">
          <thead>
            <tr>
              {canBulkActions ? (
                <th className="w-10 text-center">
                  <input
                    type="checkbox"
                    checked={leads.length > 0 && selectedIds.size === leads.length}
                    onChange={(e) => toggleAll(e.target.checked)}
                    className="rounded border-[#A1A1AA] text-[#4F46E5] focus:ring-[#4F46E5]"
                    data-testid="leads-table-select-all"
                  />
                </th>
              ) : null}
              <th>{t('firstName')}</th>
              <th>{t('phone')}</th>
              <th>{t('vinAuto')}</th>
              <th>{t('source')}</th>
              <th>{t('status')}</th>
              <th>{t('manager')}</th>
              <th>{t('leadsWs_fieldBudget')}</th>
              <th className="whitespace-nowrap">
                <span className="inline-flex items-center gap-1">
                  <Clock size={12} />
                  {t('lastContact') || 'Last contact'}
                </span>
              </th>
              <th className="text-right">{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={canBulkActions ? 10 : 9} className="text-center py-12 text-[#71717A]">
                <div className="flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin"></div>
                  {t('loadingDots')}
                </div>
              </td></tr>
            ) : leads.length === 0 ? (
              <tr><td colSpan={canBulkActions ? 10 : 9} className="text-center py-12 text-[#71717A]">{t('noLeadsFound')}</td></tr>
            ) : leads.map(lead => {
              const mgr = lead.managerId ? (managers || {})[lead.managerId] : null;
              const theme = STATUS_THEME[lead.status] || STATUS_THEME.new;
              const sel = selectedIds.has(lead.id);
              return (
                <tr key={lead.id} data-testid={`lead-row-${lead.id}`} className={sel ? 'bg-[#F5F3FF]' : ''}>
                  {canBulkActions ? (
                    <td className="w-10 text-center">
                      <input type="checkbox" checked={sel} onChange={() => toggle(lead.id)} className="rounded border-[#A1A1AA] text-[#4F46E5]" data-testid={`lead-table-select-${lead.id}`} />
                    </td>
                  ) : null}
                  <td className="font-medium text-[#18181B]">
                    <div className="truncate max-w-[180px] flex items-center gap-1.5">
                      <span className="truncate">{lead.firstName} {lead.lastName}</span>
                      <LeadSlaBadge lead={lead} size="xs" showLabel={false} />
                      <LeadSiteTemperatureBadge lastSeen={(activityMap || {})[lead.id]} size="xs" />
                    </div>
                    {lead.email ? <div className="text-[10px] text-[#A1A1AA] truncate max-w-[180px]">{lead.email}</div> : null}
                  </td>
                  <td>
                    {lead.phone ? (
                      <a href={`tel:${String(lead.phone).replace(/\s+/g,'')}`} className="inline-flex items-center gap-1 text-[#18181B] hover:text-[#4F46E5] tabular-nums" data-testid={`lead-phone-${lead.id}`}>
                        <Phone size={12} /> {lead.phone}
                      </a>
                    ) : <span className="text-[#A1A1AA]">—</span>}
                  </td>
                  <td className="text-xs">
                    {lead.vin ? <span className="font-mono text-[#71717A]">{lead.vin}</span> : null}
                    {lead.vehicleInterest && !lead.vin ? <span className="text-[#71717A]">{lead.vehicleInterest}</span> : null}
                    {!lead.vin && !lead.vehicleInterest ? <span className="text-[#A1A1AA]">—</span> : null}
                  </td>
                  <td className="text-xs text-[#71717A]">{sourceLabel(lang, lead.source)}</td>
                  <td>
                    <Select value={lead.status} onValueChange={(v) => onChangeStatus(lead, v)}>
                      <SelectTrigger className="w-[140px] h-8 bg-transparent border-0 p-0" data-testid={`lead-status-${lead.id}`}>
                        <span
                          className="text-[11px] font-semibold px-2 py-1 rounded-md inline-flex items-center gap-1"
                          style={{ backgroundColor: theme.soft, color: theme.text }}
                        >
                          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: theme.dot }}></span>
                          {statusLabel(lang, lead.status)}
                        </span>
                      </SelectTrigger>
                      <SelectContent>
                        {LEAD_PIPELINE.map(s => (
                          <SelectItem key={s} value={s}>{statusLabel(lang, s)}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td>
                    {mgr ? (
                      <div className="flex items-center gap-1.5 text-xs">
                        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-semibold text-[10px]">
                          {(mgr.name || mgr.email || '?').slice(0,1).toUpperCase()}
                        </div>
                        <span className="text-[#18181B] truncate max-w-[110px]">{mgr.name || mgr.email}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-[#A1A1AA] italic flex items-center gap-1"><User size={12} /> unassigned</span>
                    )}
                  </td>
                  <td className="text-[#059669] font-medium text-sm tabular-nums">
                    {(lead.budgetEur || lead.budgetUsd) ? `€${Number(lead.budgetEur || lead.budgetUsd).toLocaleString()}` : <span className="text-[#A1A1AA]">—</span>}
                  </td>
                  <td className="whitespace-nowrap" data-testid={`lead-last-contact-${lead.id}`}>
                    <div className="flex flex-col leading-tight">
                      <span
                        className={`text-xs font-medium tabular-nums ${lead.lastContactAt ? 'text-[#18181B]' : 'text-[#DC2626]'}`}
                        title={lead.lastContactAt ? new Date(lead.lastContactAt).toLocaleString() : 'No contact recorded'}
                      >
                        {relativeShort(lead.lastContactAt)}
                      </span>
                      {lead.statusChangedAt && lead.statusChangedAt !== lead.lastContactAt ? (
                        <span
                          className="text-[10px] text-[#A1A1AA] tabular-nums"
                          title={`Status changed: ${new Date(lead.statusChangedAt).toLocaleString()}`}
                        >
                          status {relativeShort(lead.statusChangedAt)}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center justify-end gap-1">
                      {onReassign ? (
                        <button onClick={() => onReassign(lead)} className="p-2 hover:bg-[#EEF2FF] rounded-lg" data-testid={`reassign-lead-${lead.id}`} title="Reassign">
                          <ArrowsClockwise size={14} className="text-[#4F46E5]" />
                        </button>
                      ) : null}
                      {onQuotes ? (
                        <button onClick={() => onQuotes(lead)} className="p-2 hover:bg-[#DBEAFE] rounded-lg" data-testid={`quotes-lead-${lead.id}`} title="Quotes">
                          <Receipt size={14} className="text-[#2563EB]" />
                        </button>
                      ) : null}
                      <button onClick={() => onConvert(lead)} disabled={!!lead.customerId} className={`p-2 rounded-lg ${lead.customerId ? 'opacity-30 cursor-not-allowed' : 'hover:bg-[#DCFCE7]'}`} data-testid={`convert-lead-${lead.id}`}>
                        <UserPlus size={14} className={lead.customerId ? 'text-[#71717A]' : 'text-[#16A34A]'} />
                      </button>
                      <button onClick={() => onOpenEdit(lead)} className="p-2 hover:bg-[#F4F4F5] rounded-lg" data-testid={`edit-lead-${lead.id}`}>
                        <Pencil size={14} className="text-[#71717A]" />
                      </button>
                      <button onClick={() => onDelete(lead.id)} className="p-2 hover:bg-[#FEE2E2] rounded-lg" data-testid={`delete-lead-${lead.id}`}>
                        <Trash size={14} className="text-[#DC2626]" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default LeadTableView;
