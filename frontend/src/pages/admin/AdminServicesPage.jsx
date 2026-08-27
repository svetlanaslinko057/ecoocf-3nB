/**
 * Master-Admin Services Catalog
 * Master admin manages WHICH services managers can attach to invoices.
 * Each service has a default price + a workflow definition (steps that
 * appear on the order once payment succeeds).
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Package, Plus, Pencil, Trash2, Save, X, RefreshCw, ListChecks, DollarSign, Power, ArrowUp, ArrowDown, Sparkles } from 'lucide-react';

import { useLang } from '../../i18n';
import WhiteSelect from '../../components/ui/WhiteSelect';
import RefreshButton from '../../components/ui/RefreshButton';
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CATEGORIES = ['import', 'logistics', 'docs', 'custom'];

const CATEGORY_COLORS = {
  import:    { bg: 'bg-violet-100',  text: 'text-violet-700',  hex: '#7C3AED' },
  logistics: { bg: 'bg-blue-100',    text: 'text-blue-700',    hex: '#2563EB' },
  docs:      { bg: 'bg-amber-100',   text: 'text-amber-700',   hex: '#D97706' },
  custom:    { bg: 'bg-emerald-100', text: 'text-emerald-700', hex: '#059669' },
};

const emptyService = () => ({
  id: null,
  code: '',
  name: '',
  name_en: '',
  description: '',
  description_en: '',
  category: 'custom',
  default_price: 0,
  currency: 'USD',
  default_qty: 1,
  // Phase Final / Block 1 — live template binding. When set, the backend
  // resolver uses template.steps at invoice-creation time instead of the
  // inline workflow array below.
  workflow_template_id: null,
  // Workflow labels stay as English fallback; consumers (manager view) localize at render time.
  workflow: [
    { key: 'pending',     label: 'Pending' },
    { key: 'in_progress', label: 'In progress' },
    { key: 'completed',   label: 'Completed' },
  ],
  is_active: true,
});

// Language-aware getter for service fields.  Falls back EN → UK → first non-empty.
const pickLocalized = (svc, base, lang) => {
  if (!svc) return '';
  const v = (
    lang === 'en'  ? (svc[`${base}_en`] || svc[`${base}_uk`] || svc[base] || '')
  : /* uk */         (svc[base] || svc[`${base}_uk`] || svc[`${base}_en`] || '')
  );
  return v;
};

// Language-aware getter for a workflow step's label.
// Step shape: { key, label (uk fallback), label_en }
const pickStepLabel = (step, lang) => {
  if (!step) return '';
  if (lang === 'en') return step.label_en || step.label || step.label_uk || step.key || '';
  return step.label || step.label_uk || step.label_en || step.key || '';
};

export default function AdminServicesPage() {
  const { t, lang } = useLang();
  const [items, setItems] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editor, setEditor] = useState(null); // service object being edited or null
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [svcR, tplR] = await Promise.all([
        axios.get(`${API_URL}/api/admin/services`),
        axios.get(`${API_URL}/api/admin/workflow-templates`),
      ]);
      setItems(svcR.data?.items || []);
      setTemplates(tplR.data?.items || []);
    } catch {
      toast.error(t('servicesLoadFail'));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const moveStep = (idx, dir) => {
    const wf = [...(editor?.workflow || [])];
    const j = idx + dir;
    if (j < 0 || j >= wf.length) return;
    [wf[idx], wf[j]] = [wf[j], wf[idx]];
    setEditor({ ...editor, workflow: wf });
  };

  const applyTemplate = (tpl) => {
    setEditor({ ...editor, workflow: (tpl.steps || []).map((s) => ({ ...s })) });
    setShowTemplatePicker(false);
    toast.success(`${t('applied')}: ${tpl.name}`);
  };

  const saveService = async () => {
    if (!editor?.name) { toast.error(t('adm_name_is_required')); return; }
    try {
      if (editor.id) {
        await axios.patch(`${API_URL}/api/admin/services/${editor.id}`, editor);
        toast.success(t('serviceUpdated'));
      } else {
        await axios.post(`${API_URL}/api/admin/services`, editor);
        toast.success(t('serviceCreated'));
      }
      setEditor(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_d1b0c19159'));
    }
  };

  const toggleActive = async (svc) => {
    try {
      await axios.patch(`${API_URL}/api/admin/services/${svc.id}`, { is_active: !svc.is_active });
      await load();
    } catch { toast.error(t('errorGeneric')); }
  };

  const deleteService = async (svc) => {
    if (!window.confirm(`${t('adm_deactivate_service')} "${svc.name}"?`)) return;
    try {
      await axios.delete(`${API_URL}/api/admin/services/${svc.id}`);
      toast.success(t('deactivated'));
      await load();
    } catch { toast.error(t('errorGeneric')); }
  };

  return (
    <div className="space-y-6">
      {/*
        ── Services Catalog header ───────────────────────────────────────
        June 2026 — refresh ALWAYS pinned to the top-RIGHT corner.

        Mobile (< md):
          ┌───────────────────────────────────────────────────────┐
          │ [icon]  Services Catalog              [Refresh]       │  ← Row 1
          │         Services that managers can…                   │
          ├───────────────────────────────────────────────────────┤
          │ [ + New service ]                                     │  ← Row 2
          └───────────────────────────────────────────────────────┘

        Desktop (≥ md):
          ┌───────────────────────────────────────────────────────┐
          │ [icon]  Services Catalog       [+ New service][Refr]  │
          │         subtitle…                                     │
          └───────────────────────────────────────────────────────┘
      */}
      <div className="mb-6">
        {/* Row 1: icon + title (left) ←——→ refresh (right). Always. */}
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Package className="w-[18px] h-[18px]" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight break-words">
              {t('adm_services_catalog')}
            </h1>
            <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed break-words">
              {t('adm_services_that_managers_can_add_to_invoices_workflo')}
            </p>
          </div>
          {/* Refresh pinned top-RIGHT on every viewport. On desktop we also
              show the "+ New service" button to the LEFT of refresh in the
              same row (hidden on mobile — moves to its own row below). */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setEditor(emptyService())}
              data-testid="new-service-btn-desktop"
              className="hidden md:inline-flex items-center justify-center gap-2 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-[12.5px] font-semibold whitespace-nowrap focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 transition-colors"
            >
              <Plus className="w-4 h-4" /> {t('adm_new_service')}
            </button>
            <RefreshButton
              onClick={load}
              loading={loading}
              ariaLabel={t('adm_refresh_3')}
              testId="services-refresh-btn"
            />
          </div>
        </div>

        {/* Row 2 (mobile only): + New service on its own line, full button
            but left-aligned. On desktop this row is hidden (button moved
            into the header row above). */}
        <div className="mt-4 md:hidden">
          <button
            onClick={() => setEditor(emptyService())}
            data-testid="new-service-btn"
            className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-[13px] font-semibold focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 transition-colors"
          >
            <Plus className="w-4 h-4" /> {t('adm_new_service')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {items.map((s) => {
          const c = CATEGORY_COLORS[s.category] || CATEGORY_COLORS.custom;
          const localizedName = pickLocalized(s, 'name', lang) || s.name || s.code;
          const localizedDesc = pickLocalized(s, 'description', lang);
          return (
            <div key={s.id} className={`bg-white border rounded-2xl p-5 hover:shadow-sm transition-shadow ${s.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${c.hex}15` }}>
                    <Package className="w-5 h-5" style={{ color: c.hex }} />
                  </div>
                  <div>
                    <p className="font-semibold text-gray-900">{localizedName}</p>
                    <p className="text-xs text-gray-400 font-mono">{s.code}</p>
                  </div>
                </div>
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${c.bg} ${c.text} font-medium`}>{s.category}</span>
              </div>
              {localizedDesc && <p className="text-sm text-gray-600 mb-3 line-clamp-2">{localizedDesc}</p>}
              <div className="flex items-center justify-between text-sm mb-3">
                <span className="flex items-center gap-1 text-gray-700 font-semibold">
                  <DollarSign className="w-3.5 h-3.5 text-gray-400" />{s.default_price} {s.currency}
                </span>
                <span className="flex items-center gap-1 text-gray-500 text-xs">
                  <ListChecks className="w-3.5 h-3.5" /> {s.workflow?.length || 0} {t('stages')}
                </span>
              </div>
              <div className="flex flex-wrap gap-1 mb-3">
                {(s.workflow || []).map((w, i) => (
                  <span key={i} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{pickStepLabel(w, lang)}</span>
                ))}
              </div>
              <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
                <button onClick={() => setEditor(s)} className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 rounded-lg text-xs font-medium text-gray-700">
                  <Pencil className="w-3.5 h-3.5" /> {t('adm_edit_2')}
                </button>
                <button onClick={() => toggleActive(s)} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${s.is_active ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`} title={s.is_active ? t('adm2_ad2cf79efb') : t('adm2_a053dc5a68')}>
                  <Power className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => deleteService(s)} className="px-3 py-1.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-lg text-xs" title={t('deleteAction')}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
        {items.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 bg-white border border-dashed border-gray-300 rounded-2xl">
            <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-[#F4F4F5] text-[#71717A] flex items-center justify-center">
              <Package className="w-6 h-6" />
            </div>
            <p className="text-gray-500 text-sm">{t('catalogEmpty')}</p>
            <button onClick={() => setEditor(emptyService())} className="mt-3 inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 transition-colors">
              <Plus className="w-4 h-4" /> {t('createFirstService')}
            </button>
          </div>
        )}
      </div>

      {editor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/50"
          onClick={() => setEditor(null)}
          data-testid="service-editor-overlay"
        >
          <div
            className="bg-white rounded-2xl border border-[#E4E4E7] shadow-[0_24px_80px_rgba(0,0,0,0.22)] w-[calc(100vw-24px)] sm:w-full max-w-3xl max-h-[90vh] grid grid-rows-[auto_minmax(0,1fr)_auto] relative"
            onClick={(e) => e.stopPropagation()}
            data-testid="service-editor-panel"
          >
            {/* Sticky header */}
            <div className="sticky top-0 z-10 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 border-b border-[#E4E4E7] rounded-t-2xl">
              <div className="px-5 sm:px-6 py-4 flex items-start gap-3">
                <div className="min-w-0">
                  <h2 className="text-base sm:text-lg font-semibold text-[#18181B] leading-6" data-testid="service-editor-title">
                    {editor.id ? t('adm2_edd431fa5c') : t('adm2_aa9cb4097c')}
                  </h2>
                  <p className="mt-0.5 text-sm text-zinc-500 leading-5">
                    {t('adm_services_that_managers_can_add_to_invoices_workflo')}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setEditor(null)}
                  aria-label="Close"
                  className="ml-auto shrink-0 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                  data-testid="service-editor-close-button"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Scroll body */}
            <div className="min-h-0 overflow-y-auto px-5 sm:px-6 py-5">
              <div className="space-y-7">

                {/* Code (full width) */}
                <Input
                  label={t('adm2_id_9444e12405')}
                  value={editor.code}
                  onChange={(v) => setEditor({ ...editor, code: v.toLowerCase().replace(/[^a-z0-9_]/g, '_') })}
                  placeholder={t('adm_eg_transit_insurance')}
                  testId="service-editor-code-input"
                />

                {/* Names section — UA/EN/BG triplet, auto-fit, never 3-col below lg */}
                <section>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-[#18181B]">Names</h3>
                    <span className="text-xs text-zinc-500">UA · EN</span>
                  </div>
                  <div className="mt-3 border-t border-[#E4E4E7]" />
                  <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))] lg:[grid-template-columns:repeat(2,minmax(240px,1fr))]">
                    <Input
                      label={`${t('adm2_ua_505ab38de4').replace(/[()*]/g, '').trim()} (UA)`}
                      value={editor.name}
                      onChange={(v) => setEditor({ ...editor, name: v })}
                      required
                      testId="service-editor-name-ua-input"
                    />
                    <Input
                      label={`${t('adm2_en_f3cef333c8').replace(/[()*]/g, '').trim()} (EN)`}
                      value={editor.name_en}
                      onChange={(v) => setEditor({ ...editor, name_en: v })}
                      testId="service-editor-name-en-input"
                    />
                  </div>
                </section>

                {/* Descriptions section — UA/EN */}
                <section>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-[#18181B]">{t('description')}</h3>
                    <span className="text-xs text-zinc-500">UA · EN</span>
                  </div>
                  <div className="mt-3 border-t border-[#E4E4E7]" />
                  <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))] lg:[grid-template-columns:repeat(3,minmax(240px,1fr))]">
                    {[
                      { lng: 'UA', val: editor.description, setter: (v) => setEditor({ ...editor, description: v }), ph: t('adm3_83e1640fc0'), testId: 'service-editor-description-ua' },
                      { lng: 'EN', val: editor.description_en, setter: (v) => setEditor({ ...editor, description_en: v }), ph: 'Description in English', testId: 'service-editor-description-en' },
                    ].map(({ lng, val, setter, ph, testId }) => (
                      <div key={lng} className="min-w-0">
                        <label className="block text-sm font-medium text-[#18181B] mb-2">
                          {t('description')} ({lng})
                        </label>
                        <textarea
                          rows={4}
                          value={val || ''}
                          onChange={(e) => setter(e.target.value)}
                          placeholder={ph}
                          data-testid={testId}
                          className="w-full min-w-0 min-h-[120px] resize-y px-3.5 py-2.5 border border-[#E4E4E7] rounded-xl text-sm text-[#18181B] bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF] transition-colors leading-relaxed"
                        />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Pricing section — Category / Base price / Currency, auto-fit */}
                <section>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-[#18181B]">{t('basePrice')}</h3>
                    <span className="text-xs text-zinc-500">{t('category')} · {t('currency')}</span>
                  </div>
                  <div className="mt-3 border-t border-[#E4E4E7]" />
                  <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
                    <div className="min-w-0">
                      <label className="block text-sm font-medium text-[#18181B] mb-2">{t('category')}</label>
                      <WhiteSelect
                        value={editor.category}
                        onChange={(e) => setEditor({ ...editor, category: e.target.value })}
                        data-testid="service-editor-category-select"
                      >
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </WhiteSelect>
                    </div>
                    <Input
                      label={t('basePrice')}
                      type="number"
                      value={editor.default_price}
                      onChange={(v) => setEditor({ ...editor, default_price: Number(v) })}
                      testId="service-editor-base-price-input"
                    />
                    <div className="min-w-0">
                      <label className="block text-sm font-medium text-[#18181B] mb-2">{t('currency')}</label>
                      <WhiteSelect
                        value={editor.currency}
                        onChange={(e) => setEditor({ ...editor, currency: e.target.value })}
                        data-testid="service-editor-currency-select"
                      >
                        {['USD', 'EUR', 'UAH', 'BGN', 'GBP'].map((c) => <option key={c} value={c}>{c}</option>)}
                      </WhiteSelect>
                    </div>
                  </div>
                </section>

                {/* Workflow section */}
                <section>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <h3 className="text-sm font-semibold text-[#18181B]">{t('adm2_workflow_861fd50d5f')}</h3>
                    <button
                      type="button"
                      onClick={() => setShowTemplatePicker(true)}
                      className="inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border border-[#E4E4E7] bg-white text-sm font-medium text-[#18181B] hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                      data-testid="service-editor-apply-template-button"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                      {t('adm_apply_template')}
                    </button>
                  </div>
                  <div className="mt-3 border-t border-[#E4E4E7]" />

                  {/* Phase Final / Block 1 — Live Template Binding control.
                      When a template_id is set, order steps are resolved
                      LIVE from the template at invoice-creation time.
                      When unbound, the inline step list (below) is used. */}
                  <div className="mt-4 rounded-2xl border border-violet-200 bg-violet-50/40 px-4 py-3">
                    <div className="flex items-start gap-3 flex-wrap">
                      <Sparkles className="w-4 h-4 text-violet-600 mt-1 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[#18181B]">
                          Live Workflow Template Binding
                        </p>
                        <p className="text-[12px] text-zinc-600 mt-0.5">
                          When bound, order steps are resolved LIVE from the chosen template
                          (editing the template updates ALL bound services). Leave unbound to
                          use the custom inline steps below.
                        </p>
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          <WhiteSelect
                            value={editor.workflow_template_id || ''}
                            onChange={(e) => setEditor({ ...editor, workflow_template_id: e.target.value || null })}
                            data-testid="service-editor-workflow-template-bind"
                            className="min-w-[260px]"
                          >
                            <option value="">— Custom (use inline steps) —</option>
                            {templates.map((tpl) => (
                              <option key={tpl.id} value={tpl.id}>
                                {tpl.name} ({(tpl.steps || []).length} steps)
                                {tpl.is_default ? ' • default' : ''}
                              </option>
                            ))}
                          </WhiteSelect>
                          {editor.workflow_template_id && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-700 bg-violet-100 px-2 py-1 rounded-md">
                              BOUND — inline steps below are IGNORED
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className={`mt-4 rounded-2xl border border-[#E4E4E7] bg-white ${editor.workflow_template_id ? 'opacity-50 pointer-events-none' : ''}`} data-testid="service-editor-workflow-steps-list">
                    {(editor.workflow || []).length === 0 ? (
                      <p className="p-6 text-sm text-zinc-500 text-center">No steps yet — add one or apply a template.</p>
                    ) : (
                      <div className="p-3 space-y-2">
                        {(editor.workflow || []).map((w, idx) => (
                          <div
                            key={idx}
                            className="rounded-xl border border-[#E4E4E7] bg-white px-3 py-3 space-y-2"
                            data-testid="service-editor-workflow-step-item"
                          >
                            {/* Top row: number + action buttons */}
                            <div className="flex items-center gap-2">
                              <span className="shrink-0 h-8 min-w-[2rem] px-2 rounded-lg bg-zinc-100 text-zinc-600 text-xs font-semibold inline-flex items-center justify-center">
                                {idx + 1}
                              </span>
                              <div className="ml-auto shrink-0 flex items-center gap-1.5">
                                <button
                                  type="button"
                                  disabled={idx === 0}
                                  onClick={() => moveStep(idx, -1)}
                                  className="h-9 w-9 rounded-lg border border-[#E4E4E7] bg-white hover:bg-zinc-50 text-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center justify-center transition-colors"
                                  title={t('moveUp')}
                                  aria-label="Move up"
                                >
                                  <ArrowUp className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  disabled={idx === (editor.workflow || []).length - 1}
                                  onClick={() => moveStep(idx, +1)}
                                  className="h-9 w-9 rounded-lg border border-[#E4E4E7] bg-white hover:bg-zinc-50 text-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center justify-center transition-colors"
                                  title={t('moveDown')}
                                  aria-label="Move down"
                                >
                                  <ArrowDown className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setEditor({ ...editor, workflow: editor.workflow.filter((_, i) => i !== idx) })}
                                  className="h-9 w-9 rounded-lg border border-rose-100 bg-rose-50 hover:bg-rose-100 text-rose-600 inline-flex items-center justify-center transition-colors"
                                  title={t('deleteAction')}
                                  aria-label="Delete step"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                            {/* Bottom row: key + label inputs (auto-fit, never collapses below 180px) */}
                            <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
                              <input
                                className="w-full min-w-0 px-3 py-2 min-h-[2.5rem] border border-[#E4E4E7] rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]"
                                placeholder="key (latin)"
                                value={w.key}
                                onChange={(e) => {
                                  const wf = [...editor.workflow];
                                  wf[idx] = { ...wf[idx], key: e.target.value };
                                  setEditor({ ...editor, workflow: wf });
                                }}
                                data-testid={`service-editor-step-key-input-${idx}`}
                              />
                              <input
                                className="w-full min-w-0 px-3 py-2 min-h-[2.5rem] border border-[#E4E4E7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]"
                                placeholder={t('stageName')}
                                value={w.label}
                                onChange={(e) => {
                                  const wf = [...editor.workflow];
                                  wf[idx] = { ...wf[idx], label: e.target.value };
                                  setEditor({ ...editor, workflow: wf });
                                }}
                                data-testid={`service-editor-step-label-input-${idx}`}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditor({ ...editor, workflow: [...(editor.workflow || []), { key: 'new_step', label: t('newStage') }] })}
                    className="mt-3 inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border border-[#E4E4E7] bg-white text-sm font-medium text-[#635BFF] hover:bg-violet-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                    data-testid="service-editor-add-workflow-step-button"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    {t('adm_add_stage')}
                  </button>
                </section>

                {/* Active toggle */}
                <div className="flex items-center gap-3 rounded-xl border border-[#E4E4E7] bg-white px-4 py-3">
                  <input
                    type="checkbox"
                    id="service-editor-active-checkbox"
                    checked={!!editor.is_active}
                    onChange={(e) => setEditor({ ...editor, is_active: e.target.checked })}
                    className="w-4 h-4 rounded border-zinc-300 text-[#635BFF] focus:ring-[#635BFF]/30"
                    data-testid="service-editor-active-checkbox"
                  />
                  <label htmlFor="service-editor-active-checkbox" className="text-sm font-medium text-[#18181B] select-none cursor-pointer">
                    {t('adm_active_2')}
                  </label>
                </div>
              </div>
            </div>

            {/* Sticky footer */}
            <div className="sticky bottom-0 z-10 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 border-t border-[#E4E4E7] rounded-b-2xl">
              <div className="px-5 sm:px-6 py-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setEditor(null)}
                    className="h-11 w-full rounded-xl border border-[#E4E4E7] bg-white text-[#18181B] font-medium hover:bg-zinc-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                    data-testid="service-editor-cancel-button"
                  >
                    {t('cancelAction')}
                  </button>
                  <button
                    type="button"
                    onClick={saveService}
                    className="h-11 w-full rounded-xl bg-[#18181B] text-white font-medium hover:bg-[#27272A] active:bg-black transition-colors inline-flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15"
                    data-testid="service-editor-save-button"
                  >
                    <Save className="w-4 h-4" />
                    {t('saveAction')}
                  </button>
                </div>
              </div>
            </div>

            {/* Template picker overlay (inside the modal panel) */}
            {showTemplatePicker && (
              <div className="absolute inset-0 bg-zinc-900/50 flex items-center justify-center p-4 sm:p-6 rounded-2xl" onClick={() => setShowTemplatePicker(false)}>
                <div className="bg-white rounded-2xl shadow-2xl w-[calc(100%-24px)] sm:w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col border border-[#E4E4E7]" onClick={(e) => e.stopPropagation()}>
                  <div className="px-4 py-3 border-b border-[#E4E4E7] flex items-center justify-between">
                    <h3 className="font-semibold text-zinc-900 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-violet-600" /> {t('adm_workflow_template')}
                    </h3>
                    <button onClick={() => setShowTemplatePicker(false)} className="h-9 w-9 inline-flex items-center justify-center rounded-xl border border-[#E4E4E7] bg-white hover:bg-zinc-50 transition-colors" aria-label="Close">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-3">
                    {templates.length === 0 ? (
                      <p className="text-sm text-zinc-500 text-center py-6">{t('noTemplatesYet')}</p>
                    ) : templates.map((tpl) => (
                      <button
                        key={tpl.id}
                        onClick={() => applyTemplate(tpl)}
                        className="w-full text-left p-3 rounded-xl hover:bg-zinc-50 border border-[#E4E4E7] mb-2 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-zinc-900 truncate">{tpl.name}</p>
                            {tpl.description && <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{tpl.description}</p>}
                          </div>
                          <span className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full shrink-0">{(tpl.steps || []).length} {t('adm3_a05981dbfb')}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-1 flex-wrap">
                          {(tpl.steps || []).map((s, i) => (
                            <span key={i} className="text-[10px] px-1.5 py-0.5 bg-zinc-100 text-zinc-600 rounded">{s.label}</span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange, type = 'text', required, placeholder, testId }) {
  return (
    <div className="min-w-0">
      <label className="block text-sm font-medium text-[#18181B] mb-2">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </label>
      <input
        type={type}
        value={value === null || value === undefined ? '' : value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="w-full min-w-0 px-3.5 py-2.5 min-h-[2.75rem] border border-[#E4E4E7] rounded-xl text-sm text-[#18181B] bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF] transition-colors"
      />
    </div>
  );
}
