import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  MagnifyingGlass, Funnel, Star, Clock, Warning, CheckCircle,
  ListChecks, User, Tag, Globe, CurrencyEur, Plus, X, FloppyDisk, Trash,
  Lightning, Fire, UserCircle,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { API_URL } from '../../App';
import { LEAD_PIPELINE, LEAD_SOURCES, statusLabel, sourceLabel } from './leadConstants';
import { PRIORITY_CFG } from './LeadPriorityBadge';
import { useLang } from '../../i18n/LanguageContext';

// Wave 10A — icon registry so backend can name the icon by string
const SMART_ICONS = { Phone: Lightning, Clock, Fire, CheckCircle, Warning, UserCircle, CurrencyEur };

/**
 * Left-side filter rail — mirrors the Zoho lead layout, but trimmed to
 * what we actually have in BIBI: saved filters, activity, system, fields.
 *
 * Controlled component. `filters` is the truth, `onChange` reports a
 * new partial set, the parent merges and pushes back via `filters` prop.
 */
const Section = ({ icon: Icon, title, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-[#F4F4F5] last:border-b-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-[#FAFAFA] transition-colors"
      >
        <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-[#52525B]">
          {Icon ? <Icon size={14} weight="duotone" /> : null}
          {title}
        </div>
        <span className="text-[#A1A1AA] text-xs">{open ? '−' : '+'}</span>
      </button>
      {open ? <div className="px-3 pb-3 pt-1 space-y-1.5">{children}</div> : null}
    </div>
  );
};

const Chip = ({ active, onClick, children, testId, danger }) => (
  <button
    onClick={onClick}
    data-testid={testId}
    className={`w-full text-left text-[12px] px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-2
               ${active
                  ? (danger ? 'bg-[#FEE2E2] text-[#B91C1C] font-semibold' : 'bg-[#EEF2FF] text-[#3730A3] font-semibold')
                  : 'text-[#52525B] hover:bg-[#F4F4F5]'}`}
  >
    {children}
  </button>
);

const LeadFiltersSidebar = ({ filters, onChange, lang, managers, onClose }) => {
  const { t } = useLang();
  const [savedFilters, setSavedFilters] = useState([]);
  const [smartFilters, setSmartFilters] = useState([]);
  const [showSavePrompt, setShowSavePrompt] = useState(false);
  const [savePromptName, setSavePromptName] = useState('');

  const fetchSaved = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/leads/saved-filters`);
      setSavedFilters(r.data?.items || []);
    } catch (e) { /* ignore */ }
  };
  const fetchSmart = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/leads/smart-filters`);
      setSmartFilters(r.data?.items || []);
    } catch (e) { /* ignore */ }
  };
  useEffect(() => { fetchSaved(); fetchSmart(); }, []);

  // Determine which smart-filter is currently active by deep-equality on its query
  const activeSmartId = (() => {
    for (const sf of smartFilters) {
      const q = sf.query || {};
      const matches = Object.entries(q).every(([k, v]) => filters[k] === v);
      const noExtra = Object.keys(filters || {}).filter(k => !(k in q) && filters[k] !== undefined && filters[k] !== false && filters[k] !== '').length === 0;
      if (matches && noExtra) return sf.id;
    }
    return null;
  })();

  const applySmart = (sf) => onChange({ ...(sf.query || {}), _replace: true });

  const setActivity = (key) => {
    // mutually exclusive activity flag
    const next = { hasOpenTasks: false, tasksOverdue: false, noOpenTasks: false };
    if (key && filters[key] !== true) next[key] = true;
    onChange(next);
  };

  const toggleSystem = (key, value) => {
    onChange({ [key]: filters[key] === value ? undefined : value });
  };

  const saveCurrent = async () => {
    const name = (savePromptName || '').trim();
    if (!name) { toast.error('Name is required'); return; }
    try {
      const r = await axios.post(`${API_URL}/api/leads/saved-filters`, {
        name, query: filters, icon: 'Funnel',
      });
      setSavedFilters((prev) => [r.data.item, ...prev]);
      setShowSavePrompt(false);
      setSavePromptName('');
      toast.success('Saved');
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const applySaved = (sf) => onChange({ ...sf.query, _replace: true });

  const deleteSaved = async (id) => {
    try {
      await axios.delete(`${API_URL}/api/leads/saved-filters/${id}`);
      setSavedFilters((prev) => prev.filter(s => s.id !== id));
    } catch (e) { toast.error('Failed'); }
  };

  const managerList = Object.values(managers || {});

  return (
    <aside
      className="w-[260px] shrink-0 bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden flex flex-col"
      data-testid="leads-filters-sidebar"
      style={{ maxHeight: 'calc(100vh - 200px)' }}
    >
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-[#F4F4F5] flex items-center justify-between">
        <div className="flex items-center gap-2 text-[13px] font-bold text-[#18181B]">
          <Funnel size={15} weight="duotone" />
          {t('leadsWs_filters')}
        </div>
        {onClose ? (
          <button onClick={onClose} className="p-1 hover:bg-[#F4F4F5] rounded" data-testid="leads-filters-close">
            <X size={14} />
          </button>
        ) : null}
      </div>

      {/* Search input */}
      <div className="p-3 border-b border-[#F4F4F5]">
        <div className="relative">
          <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
          <input
            type="text"
            value={filters.q || ''}
            onChange={(e) => onChange({ q: e.target.value })}
            placeholder={t('leadsWs_searchPlaceholder')}
            className="w-full pl-7 pr-2 py-1.5 text-[12px] border border-[#E4E4E7] rounded-lg focus:border-[#4F46E5] focus:ring-1 focus:ring-[#4F46E5]/30 outline-none"
            data-testid="leads-filter-q"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Saved filters */}
        <Section icon={Star} title={t('leadsWs_savedFilters')}>
          {savedFilters.length === 0 ? (
            <div className="text-[11px] text-[#A1A1AA] italic px-1">{t('leadsWs_savedEmpty')}</div>
          ) : savedFilters.map(sf => (
            <div key={sf.id} className="flex items-center gap-1 group">
              <Chip onClick={() => applySaved(sf)} testId={`leads-saved-${sf.id}`}>
                <Funnel size={12} /> {sf.name}
              </Chip>
              <button onClick={() => deleteSaved(sf.id)} className="opacity-0 group-hover:opacity-100 p-1 text-[#DC2626] hover:bg-[#FEE2E2] rounded transition-opacity" data-testid={`leads-saved-del-${sf.id}`}>
                <Trash size={11} />
              </button>
            </div>
          ))}
          {showSavePrompt ? (
            <div className="mt-2 space-y-1.5">
              <input
                value={savePromptName}
                onChange={(e) => setSavePromptName(e.target.value)}
                placeholder={t('leadsWs_filterNamePlaceholder')}
                className="w-full px-2 py-1 text-[12px] border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5]"
                data-testid="leads-saved-name-input"
              />
              <div className="flex gap-1">
                <button onClick={saveCurrent} className="flex-1 text-[11px] px-2 py-1 bg-[#4F46E5] hover:bg-[#4338CA] text-white rounded-lg font-semibold" data-testid="leads-saved-save">{t('leadsWs_save')}</button>
                <button onClick={() => { setShowSavePrompt(false); setSavePromptName(''); }} className="text-[11px] px-2 py-1 text-[#71717A] hover:bg-[#F4F4F5] rounded-lg">{t('leadsWs_cancel')}</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowSavePrompt(true)} className="w-full mt-1 flex items-center gap-1.5 text-[11px] text-[#4F46E5] hover:bg-[#EEF2FF] px-2 py-1 rounded-lg font-semibold" data-testid="leads-saved-add">
              <Plus size={11} weight="bold" /> {t('leadsWs_saveCurrent')}
            </button>
          )}
        </Section>

        {/* Wave 10A — Smart filter presets */}
        <Section icon={Lightning} title={t('leadsWs_smartFilters')}>
          {smartFilters.length === 0 ? (
            <div className="text-[11px] text-[#A1A1AA] italic px-1">{t('leadsWs_loading')}</div>
          ) : smartFilters.map(sf => {
            const Icon = SMART_ICONS[sf.icon] || Funnel;
            const active = activeSmartId === sf.id;
            return (
              <Chip
                key={sf.id}
                active={active}
                onClick={() => applySmart(sf)}
                testId={`leads-smart-${sf.id}`}
                danger={['needs_contact_today','stuck_negotiation','no_contact_7d'].includes(sf.id)}
              >
                <Icon size={12} weight={active ? 'fill' : 'regular'} style={{ color: sf.color }} />
                <span className="flex-1 truncate" title={(sf.description_i18n && sf.description_i18n[lang]) || sf.description}>
                  {(sf.name_i18n && sf.name_i18n[lang]) || sf.name}
                </span>
              </Chip>
            );
          })}
        </Section>

        {/* Wave 10A — Priority bucket chips */}
        <Section icon={Fire} title={t('leadsWs_priority')}>
          {['A','B','C','D'].map(b => {
            const cfg = PRIORITY_CFG[b];
            const active = filters.priority === b;
            return (
              <Chip
                key={b}
                active={active}
                onClick={() => onChange({ priority: active ? undefined : b })}
                testId={`leads-filter-priority-${b}`}
              >
                <span className="inline-block w-4 h-4 rounded font-extrabold text-[9px] flex items-center justify-center" style={{ background: cfg.dot, color: 'white' }}>{b}</span>
                <span>{cfg.label}</span>
              </Chip>
            );
          })}
        </Section>

        {/* Доопр #15 — Date preset filter */}
        <Section icon={Clock} title={t('dateRange') || 'Date range'}>
          <div className="px-1 py-1">
            <select
              value={filters.datePreset || 'all'}
              onChange={(e) => {
                const v = e.target.value;
                const now = new Date();
                const sod = (d) => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
                const eod = (d) => { const x = new Date(d); x.setHours(23,59,59,999); return x; };
                let from = null, to = null;
                if (v === 'today')        { from = sod(now); to = eod(now); }
                else if (v === 'yesterday'){ const y = new Date(now); y.setDate(y.getDate()-1); from = sod(y); to = eod(y); }
                else if (v === 'last_7d') { const f = new Date(now); f.setDate(f.getDate()-7); from = sod(f); to = eod(now); }
                else if (v === 'this_month'){ from = sod(new Date(now.getFullYear(), now.getMonth(), 1)); to = eod(now); }
                else if (v === 'last_month'){ from = sod(new Date(now.getFullYear(), now.getMonth()-1, 1)); to = eod(new Date(now.getFullYear(), now.getMonth(), 0)); }
                else if (v === 'last_3m') { const f = new Date(now); f.setMonth(f.getMonth()-3); from = sod(f); to = eod(now); }
                onChange({
                  datePreset: v === 'all' ? undefined : v,
                  dateFrom: from ? from.toISOString() : undefined,
                  dateTo:   to   ? to.toISOString()   : undefined,
                });
              }}
              className="w-full h-8 px-2 rounded-lg border border-[#E4E4E7] bg-white text-[12px]"
              data-testid="leads-date-preset"
            >
              <option value="all">{t('dateAll') || 'All time'}</option>
              <option value="today">{t('dateToday') || 'Today'}</option>
              <option value="yesterday">{t('dateYesterday') || 'Yesterday'}</option>
              <option value="last_7d">{t('dateLast7d') || 'Last 7 days'}</option>
              <option value="this_month">{t('dateThisMonth') || 'This month'}</option>
              <option value="last_month">{t('dateLastMonth') || 'Last month'}</option>
              <option value="last_3m">{t('dateLast3m') || 'Last 3 months'}</option>
            </select>
          </div>
        </Section>

        {/* Activity filters */}
        <Section icon={ListChecks} title={t('leadsWs_activity')}>
          <Chip active={filters.healthStatus === 'overdue'} onClick={() => onChange({ healthStatus: filters.healthStatus === 'overdue' ? undefined : 'overdue' })} testId="leads-filter-health-overdue" danger>
            <Warning size={12} weight="fill" /> {t('leadsWs_activityOverdue')}
          </Chip>
          <Chip active={filters.healthStatus === 'stale'} onClick={() => onChange({ healthStatus: filters.healthStatus === 'stale' ? undefined : 'stale' })} testId="leads-filter-health-stale">
            <Clock size={12} /> {t('leadsWs_activityStale')}
          </Chip>
          <Chip active={filters.healthStatus === 'healthy'} onClick={() => onChange({ healthStatus: filters.healthStatus === 'healthy' ? undefined : 'healthy' })} testId="leads-filter-health-healthy">
            <CheckCircle size={12} /> {t('leadsWs_activityHealthy')}
          </Chip>
          <Chip active={filters.noOpenTasks === true} onClick={() => setActivity('noOpenTasks')} testId="leads-filter-no-tasks">
            <CheckCircle size={12} /> {t('leadsWs_activityNoTasks')}
          </Chip>
          <Chip active={filters.hasOpenTasks === true} onClick={() => setActivity('hasOpenTasks')} testId="leads-filter-has-tasks">
            <ListChecks size={12} /> {t('leadsWs_activityHasTasks')}
          </Chip>
          <Chip active={filters.tasksOverdue === true} onClick={() => setActivity('tasksOverdue')} testId="leads-filter-overdue" danger>
            <Warning size={12} weight="fill" /> {t('leadsWs_activityOverdueTasks')}
          </Chip>
        </Section>

        {/* System filters */}
        <Section icon={Funnel} title={t('leadsWs_system')}>
          <Chip active={filters.managerId === 'unassigned'} onClick={() => onChange({ managerId: filters.managerId === 'unassigned' ? undefined : 'unassigned' })} testId="leads-filter-unassigned">
            <User size={12} /> {t('leadsWs_unassigned')}
          </Chip>
          <Chip active={filters.vinPresent === true} onClick={() => toggleSystem('vinPresent', true)} testId="leads-filter-has-vin">
            <Tag size={12} /> {t('leadsWs_hasVin')}
          </Chip>
          <Chip active={filters.vinPresent === false} onClick={() => toggleSystem('vinPresent', false)} testId="leads-filter-no-vin">
            <Tag size={12} /> {t('leadsWs_noVin')}
          </Chip>
        </Section>

        {/* Field filters */}
        <Section icon={Tag} title={t('leadsWs_fields')}>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('leadsWs_fieldStatus')}</label>
            <select
              value={filters.status || ''}
              onChange={(e) => onChange({ status: e.target.value || undefined })}
              className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
              data-testid="leads-filter-status"
            >
              <option value="">{t('leadsWs_allStatuses')}</option>
              {LEAD_PIPELINE.map(s => (
                <option key={s} value={s}>{statusLabel(lang, s)}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('leadsWs_fieldSource')}</label>
            <select
              value={filters.source || ''}
              onChange={(e) => onChange({ source: e.target.value || undefined })}
              className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
              data-testid="leads-filter-source"
            >
              <option value="">{t('leadsWs_allSources')}</option>
              {LEAD_SOURCES.map(s => (
                <option key={s} value={s}>{sourceLabel(lang, s)}</option>
              ))}
            </select>
          </div>

          {/* UTM filters (Team-Lead spec, 2026-06-10) ─────────────────────
              These are substring matches on the backend (case-insensitive),
              so partial slugs work: "fb" matches "fb_ads" + "facebook". */}
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Source</label>
            <input
              type="text"
              value={filters.utm_source || ''}
              onChange={(e) => onChange({ utm_source: e.target.value || undefined })}
              placeholder="google, facebook, ringostat…"
              className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
              data-testid="leads-filter-utm-source"
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Medium</label>
            <input
              type="text"
              value={filters.utm_medium || ''}
              onChange={(e) => onChange({ utm_medium: e.target.value || undefined })}
              placeholder="cpc, social, email…"
              className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
              data-testid="leads-filter-utm-medium"
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">UTM Campaign</label>
            <input
              type="text"
              value={filters.utm_campaign || ''}
              onChange={(e) => onChange({ utm_campaign: e.target.value || undefined })}
              placeholder="spring_sale_2026…"
              className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
              data-testid="leads-filter-utm-campaign"
            />
          </div>

          {managerList.length > 0 ? (
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('leadsWs_fieldManager')}</label>
              <select
                value={filters.managerId && filters.managerId !== 'unassigned' ? filters.managerId : ''}
                onChange={(e) => onChange({ managerId: e.target.value || undefined })}
                className="w-full text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5] bg-white"
                data-testid="leads-filter-manager"
              >
                <option value="">{t('leadsWs_allManagers')}</option>
                {managerList.map(m => (
                  <option key={m.id || m.email} value={m.id || m.email}>{m.name || m.email}</option>
                ))}
              </select>
            </div>
          ) : null}

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-[#71717A] mb-1">{t('leadsWs_fieldBudget')}</label>
            <div className="flex gap-1.5">
              <input
                type="number"
                value={filters.budgetFrom ?? ''}
                onChange={(e) => onChange({ budgetFrom: e.target.value === '' ? undefined : Number(e.target.value) })}
                placeholder={t('leadsWs_budgetFrom')}
                className="w-1/2 text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5]"
                data-testid="leads-filter-budget-from"
              />
              <input
                type="number"
                value={filters.budgetTo ?? ''}
                onChange={(e) => onChange({ budgetTo: e.target.value === '' ? undefined : Number(e.target.value) })}
                placeholder={t('leadsWs_budgetTo')}
                className="w-1/2 text-[12px] px-2 py-1.5 border border-[#E4E4E7] rounded-lg outline-none focus:border-[#4F46E5]"
                data-testid="leads-filter-budget-to"
              />
            </div>
          </div>
        </Section>
      </div>

      {/* Footer reset */}
      <div className="p-2 border-t border-[#F4F4F5]">
        <button
          onClick={() => onChange({ _replace: true })}
          className="w-full text-[12px] text-[#71717A] hover:bg-[#F4F4F5] px-2 py-1.5 rounded-lg"
          data-testid="leads-filters-reset"
        >
          {t('leadsWs_resetAll')}
        </button>
      </div>
    </aside>
  );
};

export default LeadFiltersSidebar;
