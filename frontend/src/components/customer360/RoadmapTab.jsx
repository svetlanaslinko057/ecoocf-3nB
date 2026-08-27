/**
 * Customer360 — RoadmapTab (Sprint 3.5)
 * --------------------------------------
 * Manager-facing view of the customer's vehicle journey roadmaps.
 * Allows creating a brand-new roadmap, advancing stages, leaving notes,
 * and editing the SLA / ETA for the current stage.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  PlusCircle,
  Car,
  CaretDown,
  CaretUp,
  Trash,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';
import RoadmapStepper from '../roadmap/RoadmapStepper';
import SalesPipelineBoard from './SalesPipelineBoard';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const STATUS_OPTIONS = [
  { value: 'pending', label_en: 'Pending', label_uk: 'Очікування' },
  { value: 'in_progress', label_en: 'In progress', label_uk: 'В роботі' },
  { value: 'done', label_en: 'Done', label_uk: 'Готово' },
  { value: 'blocked', label_en: 'Blocked', label_uk: 'Заблоковано' },
  { value: 'skipped', label_en: 'Skipped', label_uk: 'Пропущено' },
];

const pickL = (opt, lang) => opt[`label_${lang}`] || opt.label_en;

const RoadmapTab = ({ customerId }) => {
  const { t, lang } = useLang();
  const [roadmaps, setRoadmaps] = useState([]);
  const [stageTemplate, setStageTemplate] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});
  const [editing, setEditing] = useState(null); // { roadmapId, stage }
  const [showNew, setShowNew] = useState(false);
  const [pipelineType, setPipelineType] = useState('sales_pipeline'); // UAT #4: default = sales view

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/customers/${customerId}/roadmaps`, {
        headers: authHeaders(),
        params: { type: pipelineType },
      });
      const items = res.data?.items || [];
      setRoadmaps(items);
      setStageTemplate(res.data?.stage_template || []);
      return items;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load roadmaps');
      return [];
    } finally {
      setLoading(false);
    }
  }, [customerId, pipelineType]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const items = await load();
      if (!cancelled && items && items.length) {
        // Auto-expand the most recent roadmap so the user immediately sees progress.
        setExpanded({ [items[0].id]: true });
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const toggle = (rid) => setExpanded((s) => ({ ...s, [rid]: !s[rid] }));

  const handleStageEdit = (roadmap, stage) => {
    setEditing({
      roadmapId: roadmap.id,
      stageKey: stage.key,
      stageLabel: stage[`label_${lang}`] || stage.label_en || stage.key,
      status: stage.status || 'pending',
      sla_days: stage.sla_days || 7,
      eta: stage.eta || '',
      note: '',
    });
  };

  const submitEdit = async () => {
    if (!editing) return;
    try {
      const body = {
        status: editing.status,
        sla_days: Number(editing.sla_days) || undefined,
        eta: editing.eta || undefined,
        note: (editing.note || '').trim() || undefined,
      };
      await axios.patch(
        `${API_URL}/api/roadmaps/${editing.roadmapId}/stages/${editing.stageKey}`,
        body,
        { headers: authHeaders() }
      );
      toast.success('Stage updated');
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update stage');
    }
  };

  const handleDelete = async (roadmapId) => {
    if (!window.confirm('Cancel this roadmap? (soft-delete — it stays in history)')) return;
    try {
      await axios.delete(`${API_URL}/api/roadmaps/${roadmapId}`, { headers: authHeaders() });
      toast.success('Roadmap cancelled');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Cancel failed');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40" data-testid="roadmap-tab-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="customer360-roadmap-tab">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-[#18181B]">
            {lang === 'ru' ? 'Дорожная карта клиента'
              : lang === 'uk' ? 'Дорожня карта клієнта'
              : 'Client Roadmap'}
          </h3>
          <p className="text-sm text-[#71717A]">
            {pipelineType === 'sales_pipeline'
              ? (lang === 'uk' ? 'Воронка продажу: від нового ліда до завершеної угоди'
                : lang === 'ru' ? 'Воронка продаж: от нового лида до завершённой сделки'
                : 'Sales pipeline: from new lead to completed deal')
              : (lang === 'uk' ? 'Подорож авто: від аукціону до передачі клієнту'
                : lang === 'ru' ? 'Путь автомобиля: от аукциона до передачи клиенту'
                : 'Vehicle journey from auction to handover')}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Pipeline type switcher */}
          <div className="inline-flex bg-zinc-100 rounded-xl p-0.5" data-testid="roadmap-type-switcher">
            <button
              onClick={() => setPipelineType('sales_pipeline')}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition ${pipelineType === 'sales_pipeline' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}
              data-testid="roadmap-type-sales"
            >
              {lang === 'uk' ? 'Продажі' : lang === 'ru' ? 'Продажи' : 'Sales'}
            </button>
            <button
              onClick={() => setPipelineType('vehicle_journey')}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition ${pipelineType === 'vehicle_journey' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}
              data-testid="roadmap-type-vehicle"
            >
              {lang === 'uk' ? 'Авто' : lang === 'ru' ? 'Авто' : 'Vehicle'}
            </button>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="inline-flex items-center gap-2 px-3 py-2 bg-[#18181B] text-white rounded-xl hover:bg-[#3F3F46] text-sm font-medium"
            data-testid="roadmap-new-btn"
          >
            <PlusCircle size={16} /> {lang === 'ru' ? 'Новая' : lang === 'uk' ? 'Нова' : 'New'}
          </button>
        </div>
      </div>

      {/* Empty state */}
      {roadmaps.length === 0 && (
        <div className="section-card text-center py-12" data-testid="roadmap-empty">
          <Car size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">
            {pipelineType === 'sales_pipeline'
              ? (lang === 'uk' ? 'Дорожньої карти продажу немає. Натисніть «Нова», щоб створити.'
                : lang === 'ru' ? 'Дорожной карты продаж пока нет. Нажмите «Новая», чтобы создать.'
                : 'No sales pipeline roadmap yet. Click "New" to create one.')
              : (lang === 'ru' ? 'Дорожных карт пока нет. Новая создаётся автоматически после оплаты инвойса.'
                : lang === 'uk' ? 'Дорожніх карт ще немає. Нова створюється автоматично після оплати інвойсу.'
                : 'No roadmaps yet. One is created automatically after an invoice is paid.')}
          </p>
        </div>
      )}

      {/* UAT #4 — Sales Pipeline horizontal board view */}
      {pipelineType === 'sales_pipeline' && roadmaps.map((rm) => (
        <SalesPipelineBoard
          key={rm.id}
          roadmap={rm}
          lang={lang}
          onChanged={load}
        />
      ))}

      {/* Vehicle Journey roadmap cards (existing behaviour) */}
      {pipelineType === 'vehicle_journey' && roadmaps.map((rm) => {
        const isOpen = !!expanded[rm.id];
        return (
          <div key={rm.id} className="section-card" data-testid={`roadmap-card-${rm.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1 cursor-pointer" onClick={() => toggle(rm.id)}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-[#18181B]">{rm.title || 'Vehicle roadmap'}</span>
                  {rm.vehicle?.vin && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-100 text-zinc-600">VIN: {rm.vehicle.vin}</span>
                  )}
                  <span className="text-[11px] text-zinc-500">#{(rm.id || '').slice(-8)}</span>
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex-1 max-w-xs h-2 bg-zinc-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 transition-all" style={{ width: `${rm.progress_pct || 0}%` }} />
                  </div>
                  <span className="text-xs tabular-nums text-zinc-600 font-medium">{rm.progress_pct || 0}%</span>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button onClick={() => handleDelete(rm.id)} className="p-2 hover:bg-red-50 rounded-lg" title="Cancel roadmap">
                  <Trash size={14} className="text-red-500" />
                </button>
                <button onClick={() => toggle(rm.id)} className="p-2 hover:bg-zinc-100 rounded-lg">
                  {isOpen ? <CaretUp size={14} /> : <CaretDown size={14} />}
                </button>
              </div>
            </div>

            {isOpen && (
              <div className="mt-5 pt-5 border-t border-zinc-100">
                <RoadmapStepper
                  roadmap={rm}
                  stageTemplate={stageTemplate}
                  lang={lang}
                  onStageClick={(stage) => handleStageEdit(rm, stage)}
                />

                {/* Notes per stage */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
                  {(rm.stages || []).filter((s) => (s.notes || []).length > 0).map((s) => (
                    <div key={s.key} className="p-3 rounded-xl border border-zinc-200 bg-zinc-50/40">
                      <p className="text-[11px] uppercase tracking-wider font-bold text-zinc-500">
                        {s[`label_${lang}`] || s.label_en}
                      </p>
                      <ul className="mt-1.5 space-y-1">
                        {(s.notes || []).slice(-3).map((n) => (
                          <li key={n.id} className="text-sm text-zinc-700">
                            «{n.body}»
                            <span className="ml-1 text-[10px] text-zinc-400">
                              — {n.author || 'system'}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="roadmap-edit-modal">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-zinc-900">{editing.stageLabel}</h3>
              <button onClick={() => setEditing(null)} className="text-zinc-400 hover:text-zinc-700">×</button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Status</label>
                <select
                  value={editing.status}
                  onChange={(e) => setEditing({ ...editing, status: e.target.value })}
                  className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm"
                  data-testid="roadmap-edit-status"
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{pickL(o, lang)}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">SLA (days)</label>
                  <input
                    type="number" min="1"
                    value={editing.sla_days}
                    onChange={(e) => setEditing({ ...editing, sla_days: e.target.value })}
                    className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">ETA</label>
                  <input
                    type="date"
                    value={editing.eta?.slice(0, 10) || ''}
                    onChange={(e) => setEditing({ ...editing, eta: e.target.value })}
                    className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Note</label>
                <textarea
                  rows={3}
                  value={editing.note}
                  onChange={(e) => setEditing({ ...editing, note: e.target.value })}
                  placeholder="Optional comment for client / team"
                  className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg">Cancel</button>
              <button
                onClick={submitEdit}
                className="px-4 py-2 bg-[#18181B] text-white text-sm rounded-lg hover:bg-[#3F3F46]"
                data-testid="roadmap-edit-save"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New roadmap modal */}
      {showNew && (
        <NewRoadmapModal
          customerId={customerId}
          stageTemplate={stageTemplate}
          lang={lang}
          pipelineType={pipelineType}
          onClose={() => setShowNew(false)}
          onCreated={() => { setShowNew(false); load(); }}
        />
      )}
    </div>
  );
};

const NewRoadmapModal = ({ customerId, stageTemplate, lang, pipelineType, onClose, onCreated }) => {
  const [title, setTitle] = useState('');
  const [vin, setVin] = useState('');
  const defaultInitial = (stageTemplate && stageTemplate[0]?.key) || (pipelineType === 'sales_pipeline' ? 'new_lead' : 'vehicle_found');
  const [initialStage, setInitialStage] = useState(defaultInitial);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await axios.post(
        `${API_URL}/api/customers/${customerId}/roadmaps`,
        {
          title: title || undefined,
          vehicle: vin ? { vin } : undefined,
          initial_stage: initialStage,
          pipeline_type: pipelineType,
        },
        { headers: authHeaders() }
      );
      toast.success('Roadmap created');
      onCreated?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="roadmap-new-modal">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-zinc-900 mb-4">{lang === 'ru' ? 'Новая дорожная карта' : 'New roadmap'}</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{lang === 'ru' ? 'Название' : 'Title'}</label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="BMW X5 2022" className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" data-testid="roadmap-new-title" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">VIN</label>
            <input type="text" value={vin} onChange={(e) => setVin(e.target.value)} placeholder="5UXKR0C58E0H..." className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">{lang === 'ru' ? 'Начальный этап' : 'Initial stage'}</label>
            <select value={initialStage} onChange={(e) => setInitialStage(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm">
              {stageTemplate.map((s) => (
                <option key={s.key} value={s.key}>{s[`label_${lang}`] || s.label_en}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg">Cancel</button>
          <button onClick={submit} disabled={saving} className="px-4 py-2 bg-[#18181B] text-white text-sm rounded-lg hover:bg-[#3F3F46] disabled:opacity-50" data-testid="roadmap-new-save">
            {saving ? '…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoadmapTab;
