/**
 * BIBI Cars - Wave 8 - Lead Workspace
 *
 * Replaces the legacy flat table with a full Kanban+Table workspace:
 *  - Top toolbar: total / sort / view toggle (Kanban|Table) / bulk actions / create
 *  - Left filters rail: saved / activity / system / fields
 *  - Main board: drag-and-drop Kanban OR table view
 *  - Create/edit modal preserved from V7 + Reassign + Convert flows
 *
 * Route mounted at /admin/leads (was the old Leads.js page).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang } from '../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Target } from '@phosphor-icons/react';

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import QuoteHistory from '../components/crm/QuoteHistory';
import RefreshButton from '../components/ui/RefreshButton';
import SharedZoneBadge from '../components/ui/SharedZoneBadge';
import ReassignDialog from '../components/ui/ReassignDialog';
import useManagersMap from '../hooks/useManagersMap';

import LeadViewToolbar from '../components/leads/LeadViewToolbar';
import LeadFiltersSidebar from '../components/leads/LeadFiltersSidebar';
import LeadKanbanBoard from '../components/leads/LeadKanbanBoard';
import LeadTableView from '../components/leads/LeadTableView';
import LeadCreateModal from '../components/leads/LeadCreateModal';
import { computeSlaClient } from '../components/leads/LeadSlaBadge';
import { LEAD_PIPELINE, statusLabel } from '../components/leads/leadConstants';
import { detectCountry, isValidForCountry } from '../components/ui/PhoneInput';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const VIEW_STORAGE_KEY = 'bibi.leads.view';

const Leads = () => {
  const { lang, t } = useLang();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canReassign = ['admin', 'owner', 'master_admin', 'team_lead'].includes(role);
  const canBulkActions = canReassign;
  const currentUserId = user?.id || user?.managerId || user?.email;

  const { managers: managersMap, invalidate: invalidateManagers } = useManagersMap();

  // ── View state ──
  const [view, setView] = useState(() => {
    try { return localStorage.getItem(VIEW_STORAGE_KEY) || 'kanban'; } catch { return 'kanban'; }
  });
  useEffect(() => { try { localStorage.setItem(VIEW_STORAGE_KEY, view); } catch {} }, [view]);

  // ── Filters state ──
  // Filter shape:
  //   q, status, source, managerId, vinPresent (true/false),
  //   hasOpenTasks, tasksOverdue, noOpenTasks (one-of),
  //   budgetFrom, budgetTo,
  //   createdFrom, createdTo,
  //   lastContactFrom, lastContactTo
  const [filters, setFilters] = useState({});
  const [filtersMobileOpen, setFiltersMobileOpen] = useState(false);

  // ── Sort + paging ──
  const [sort, setSort] = useState('created_at:desc');

  // ── Data state ──
  const [kanbanCols, setKanbanCols] = useState([]);
  const [tableItems, setTableItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // ── Selection (table view only) ──
  const [selectedIds, setSelectedIds] = useState(new Set());

  // ── Modals ──
  const [showCreate, setShowCreate] = useState(false);
  const [editingLead, setEditingLead] = useState(null);
  const [formData, setFormData] = useState({
    firstName: '', lastName: '', email: '', phone: '', phoneCountry: 'BG',
    vehicleInterest: '', source: 'website', description: '', budgetEur: '',
  });
  const [formErrors, setFormErrors] = useState({});

  const [reassignTarget, setReassignTarget] = useState(null);

  const [showQuoteHistory, setShowQuoteHistory] = useState(false);
  const [selectedLead, setSelectedLead] = useState(null);

  // Block 6.2 — SLA overdue client-side filter (kept simple to avoid backend churn)
  const [slaOverdueOnly, setSlaOverdueOnly] = useState(false);

  // Launch-prep — site-activity temperature map (one read for the whole list,
  // reuses the existing /online endpoint; no new API). { leadId: last_seen_at }.
  const [activityMap, setActivityMap] = useState({});
  useEffect(() => {
    let cancelled = false;
    axios
      .get(`${API_URL}/api/v1/site-activity/online?kind=lead&minutes=${60 * 24 * 30}`)
      .then((r) => {
        if (cancelled) return;
        const m = {};
        (r.data?.items || []).forEach((it) => {
          if (it.target_id) m[it.target_id] = it.last_seen_at;
        });
        setActivityMap(m);
      })
      .catch(() => { /* silent — tracker may not be installed yet */ });
    return () => { cancelled = true; };
  }, []);

  // ── Build query params from filters + sort ──
  const buildParams = useCallback(() => {
    const p = new URLSearchParams();
    Object.entries(filters || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '' || v === false) return;
      if (k === '_replace') return;
      p.append(k, String(v));
    });
    if (sort) p.append('sort', sort);
    return p;
  }, [filters, sort]);

  // ── Fetch data based on view ──
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (view === 'kanban') {
        const p = buildParams();
        p.append('lang', lang || 'uk');
        const r = await axios.get(`${API_URL}/api/leads/kanban?${p}`);
        setKanbanCols(r.data?.columns || []);
        setTotal(r.data?.total || 0);
      } else {
        const p = buildParams();
        p.append('limit', '200');
        const r = await axios.get(`${API_URL}/api/leads?${p}`);
        setTableItems(r.data?.data || r.data?.items || []);
        setTotal(r.data?.total || 0);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [view, buildParams, lang]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Filters merge handler ──
  const handleFiltersChange = useCallback((patch) => {
    setFilters((prev) => {
      if (patch && patch._replace) {
        // replace fully (used by saved filters + reset)
        const { _replace, ...rest } = patch;
        return { ...rest };
      }
      const next = { ...prev };
      Object.entries(patch || {}).forEach(([k, v]) => {
        if (v === undefined || v === '' || v === null || v === false) delete next[k];
        else next[k] = v;
      });
      return next;
    });
  }, []);

  // ── Form ──
  const resetForm = () => {
    setEditingLead(null);
    setFormData({
      firstName: '', lastName: '', email: '', phone: '', phoneCountry: 'BG',
      vehicleInterest: '', source: 'website', description: '', budgetEur: '',
    });
    setFormErrors({});
  };

  const openCreate = () => { resetForm(); setShowCreate(true); };

  const openEdit = (lead) => {
    setEditingLead(lead);
    const detected = detectCountry(lead.phone);
    setFormData({
      firstName: lead.firstName || '',
      lastName:  lead.lastName  || '',
      email:     lead.email     || '',
      phone:     lead.phone     || '',
      phoneCountry: lead.phoneCountry || (detected && detected.code) || 'BG',
      vehicleInterest: lead.vehicleInterest || lead.company || '',
      source:    lead.source || 'website',
      description: lead.description || lead.notes || '',
      budgetEur: lead.budgetEur || lead.budgetUsd || '',
    });
    setFormErrors({});
    setShowCreate(true);
  };

  const validate = () => {
    const errs = {};
    if (!(formData.firstName || '').trim()) errs.firstName = "Required";
    if (!(formData.lastName || '').trim()) errs.lastName = "Required";
    if (!(formData.email || '').trim()) errs.email = "Required";
    else if (!EMAIL_RE.test(formData.email.trim())) errs.email = "Invalid email";
    if (formData.phone && !isValidForCountry(formData.phone, formData.phoneCountry)) {
      errs.phone = "Invalid phone";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) { toast.error(t('leadsWs_toastCheckFields')); return; }
    try {
      const payload = {
        firstName: formData.firstName.trim(),
        lastName:  formData.lastName.trim(),
        email:     formData.email.trim(),
        phone:     formData.phone || null,
        phoneCountry: formData.phoneCountry || null,
        vehicleInterest: formData.vehicleInterest || null,
        source:    formData.source,
        description: formData.description || null,
        budgetEur: Number(formData.budgetEur) || 0,
      };
      if (editingLead) {
        await axios.put(`${API_URL}/api/leads/${editingLead.id}`, payload);
        toast.success(t('leadsWs_toastSaved'));
      } else {
        await axios.post(`${API_URL}/api/leads`, payload);
        toast.success(t('leadsWs_toastLeadCreated'));
      }
      setShowCreate(false);
      resetForm();
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.response?.data?.message || t('leadsWs_toastError'));
    }
  };

  // ── Per-lead handlers ──
  const handleDelete = async (id) => {
    if (!window.confirm(t('leadsWs_confirmDelete'))) return;
    try {
      await axios.delete(`${API_URL}/api/leads/${id}`);
      toast.success(t('leadsWs_toastDeleted'));
      fetchData();
    } catch (err) { toast.error(t('leadsWs_toastError')); }
  };

  const handleConvert = async (lead) => {
    if (lead.customerId) { toast.info(t('leadsWs_toastAlreadyClient')); return; }
    if (!window.confirm(t('leadsWs_confirmConvert'))) return;
    try {
      const r = await axios.post(`${API_URL}/api/leads/${lead.id}/convert`);
      toast.success(t('leadsWs_toastConverted'));
      fetchData();
      const cid = r?.data?.customer?.id;
      if (cid) setTimeout(() => { window.location.href = `/admin/customers?focus=${cid}`; }, 600);
    } catch (err) {
      toast.error(err.response?.data?.detail || t('leadsWs_toastConvErr'));
    }
  };

  const handleChangeStatus = async (lead, newStatus) => {
    try {
      await axios.patch(`${API_URL}/api/leads/${lead.id}/status`, { status: newStatus, reason: 'table_change' });
      toast.success(`→ ${statusLabel(lang, newStatus)}`);
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || t('leadsWs_toastError')); }
  };

  // ── Bulk handlers ──
  const handleBulkReassign = () => {
    if (selectedIds.size === 0) return;
    setReassignTarget({ ids: Array.from(selectedIds), currentManagerId: null });
  };

  const handleBulkChangeStatus = async (newStatus) => {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    const confirmMsg = (t('leadsWs_confirmBulkStatus') || 'Move {count} leads to "{status}"?')
      .replace('{count}', ids.length)
      .replace('{status}', statusLabel(lang, newStatus));
    if (!window.confirm(confirmMsg)) return;
    let ok = 0, fail = 0;
    for (const id of ids) {
      try {
        await axios.patch(`${API_URL}/api/leads/${id}/status`, { status: newStatus, reason: 'bulk_change' });
        ok += 1;
      } catch (e) { fail += 1; }
    }
    toast.success(`${ok}${fail ? ` / ${fail}` : ''}`);
    setSelectedIds(new Set());
    fetchData();
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    const confirmMsg = (t('leadsWs_confirmBulkDelete') || 'Permanently delete {count} leads?').replace('{count}', ids.length);
    if (!window.confirm(confirmMsg)) return;
    let ok = 0, fail = 0;
    for (const id of ids) {
      try { await axios.delete(`${API_URL}/api/leads/${id}`); ok += 1; }
      catch (e) { fail += 1; }
    }
    toast.success(`${ok}${fail ? ` / ${fail}` : ''}`);
    setSelectedIds(new Set());
    fetchData();
  };

  const navigate = useNavigate();
  const onCardOpen = (lead) => navigate(`/admin/leads/${lead.id}`);

  return (
    <motion.div
      data-testid="leads-page"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* Page header */}
      <div className="flex flex-row items-start justify-between gap-3 mb-5">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Target size={20} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight">
              Lead Workspace
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1">
              {t('leadsWs_subtitle')}
            </p>
            <div className="mt-2"><SharedZoneBadge /></div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <RefreshButton onClick={fetchData} loading={loading} ariaLabel="Refresh" testId="leads-refresh-btn" />
        </div>
      </div>

      {/* Toolbar */}
      <LeadViewToolbar
        title="Lead Workspace"
        total={total}
        view={view}
        onViewChange={setView}
        sort={sort}
        onSortChange={setSort}
        selectedCount={selectedIds.size}
        onClearSelection={() => setSelectedIds(new Set())}
        onBulkReassign={handleBulkReassign}
        onBulkChangeStatus={handleBulkChangeStatus}
        onBulkDelete={handleBulkDelete}
        onOpenCreate={openCreate}
        onToggleFiltersMobile={() => setFiltersMobileOpen(true)}
        lang={lang}
        canBulkActions={canBulkActions}
        slaOverdueOnly={slaOverdueOnly}
        onToggleSlaOverdue={setSlaOverdueOnly}
      />

      {/* Body: filters rail + board/table */}
      <div className="flex gap-4">
        {/* Desktop sidebar */}
        <div className="hidden lg:block">
          <LeadFiltersSidebar
            filters={filters}
            onChange={handleFiltersChange}
            lang={lang}
            managers={managersMap}
          />
        </div>

        {/* Mobile drawer */}
        {filtersMobileOpen ? (
          <div className="lg:hidden fixed inset-0 z-50 bg-black/30 flex" onClick={() => setFiltersMobileOpen(false)}>
            <div onClick={(e) => e.stopPropagation()} className="w-[280px] bg-white h-full overflow-hidden">
              <LeadFiltersSidebar
                filters={filters}
                onChange={handleFiltersChange}
                lang={lang}
                managers={managersMap}
                onClose={() => setFiltersMobileOpen(false)}
              />
            </div>
          </div>
        ) : null}

        {/* Main area */}
        <div className="flex-1 min-w-0">
          {view === 'kanban' ? (
            <LeadKanbanBoard
              columns={slaOverdueOnly
                ? (kanbanCols || []).map(col => ({ ...col, items: (col.items || []).filter(l => ['overdue','escalated'].includes(computeSlaClient(l).state)) }))
                : kanbanCols}
              lang={lang}
              managers={managersMap}
              canReassign={canReassign}
              role={role}
              currentUserId={currentUserId}
              onCardOpen={onCardOpen}
              onReassign={(lead) => setReassignTarget({ ids: [lead.id], currentManagerId: lead.managerId })}
              onRefresh={fetchData}
            />
          ) : (
            <LeadTableView
              leads={slaOverdueOnly
                ? (tableItems || []).filter(l => ['overdue','escalated'].includes(computeSlaClient(l).state))
                : tableItems}
              lang={lang}
              managers={managersMap}
              loading={loading}
              activityMap={activityMap}
              selectedIds={selectedIds}
              setSelectedIds={setSelectedIds}
              canBulkActions={canBulkActions}
              onOpenEdit={(lead) => navigate(`/admin/leads/${lead.id}`)}
              onDelete={handleDelete}
              onConvert={handleConvert}
              onReassign={canReassign ? (lead) => setReassignTarget({ ids: [lead.id], currentManagerId: lead.managerId }) : null}
              onQuotes={(lead) => { setSelectedLead(lead); setShowQuoteHistory(true); }}
              onChangeStatus={handleChangeStatus}
            />
          )}
        </div>
      </div>

      {/* Create / edit modal */}
      <LeadCreateModal
        open={showCreate}
        onOpenChange={(open) => { setShowCreate(open); if (!open) resetForm(); }}
        formData={formData}
        setFormData={setFormData}
        formErrors={formErrors}
        editingLead={editingLead}
        onSubmit={handleSubmit}
        lang={lang}
      />

      {/* Quote history modal (table view action) */}
      <Dialog open={showQuoteHistory} onOpenChange={setShowQuoteHistory}>
        <DialogContent className="max-w-3xl bg-white rounded-2xl border border-[#E4E4E7]" data-testid="quote-history-modal">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold text-[#18181B]">
              Розрахунки: {selectedLead?.firstName} {selectedLead?.lastName}
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            {selectedLead && (
              <QuoteHistory leadId={selectedLead.id} vin={selectedLead.vin} onScenarioChange={() => fetchData()} />
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Reassign dialog */}
      {canReassign && reassignTarget ? (
        <ReassignDialog
          open={!!reassignTarget}
          onClose={() => setReassignTarget(null)}
          entity="lead"
          ids={reassignTarget.ids}
          currentManagerId={reassignTarget.currentManagerId}
          onSuccess={() => {
            setSelectedIds(new Set());
            invalidateManagers();
            fetchData();
          }}
        />
      ) : null}
    </motion.div>
  );
};

export default Leads;
