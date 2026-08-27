/**
 * SalesPipelineBoard — Customer 360 → Roadmap (Sales Pipeline view)
 * UAT Enhancement #4 — «Дорожня карта клієнта»
 *
 * Renders a single sales_pipeline roadmap as a horizontal board with one
 * card per stage. Each card surfaces (per spec):
 *   • Stage name + short description
 *   • Manager key actions as checkboxes
 *   • Recommended next step (highlighted)
 *   • Free-text comment (editable)
 *   • Risks list (add / remove)
 *   • Stage history (transitions)
 *
 * Uses the shared backend layer:
 *   PATCH /api/roadmaps/{rid}/stages/{key}              status / comment
 *   PATCH /api/roadmaps/{rid}/stages/{key}/checklist/{itemKey}
 *   POST  /api/roadmaps/{rid}/stages/{key}/risks
 *   DELETE /api/roadmaps/{rid}/stages/{key}/risks/{rid}
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  CheckCircle2, Circle, AlertTriangle, ChevronDown, ChevronUp,
  Clock, X, Plus, History,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_THEME = {
  pending:     { bg: 'bg-zinc-50',    border: 'border-zinc-200',    text: 'text-zinc-600',    label: { uk: 'Очікує', en: 'Pending', bg: 'Изчаква' } },
  in_progress: { bg: 'bg-amber-50',   border: 'border-amber-300',   text: 'text-amber-700',   label: { uk: 'В роботі', en: 'In progress', bg: 'В процес' } },
  done:        { bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', label: { uk: 'Готово', en: 'Done', bg: 'Готово' } },
  blocked:     { bg: 'bg-rose-50',    border: 'border-rose-300',    text: 'text-rose-700',    label: { uk: 'Заблоковано', en: 'Blocked', bg: 'Блокирано' } },
  skipped:     { bg: 'bg-zinc-100',   border: 'border-zinc-300',    text: 'text-zinc-500',    label: { uk: 'Пропущено', en: 'Skipped', bg: 'Пропуснат' } },
};

const SEVERITY_THEME = {
  low:    { bg: 'bg-zinc-100',   text: 'text-zinc-700' },
  medium: { bg: 'bg-amber-100',  text: 'text-amber-700' },
  high:   { bg: 'bg-rose-100',   text: 'text-rose-700' },
};

const pick = (obj, lang, prefix) =>
  obj[`${prefix}_${lang}`] || obj[`${prefix}_en`] || obj[prefix] || '';

const StageCard = ({ stage, roadmapId, lang, isCurrent, onChanged }) => {
  const [expanded, setExpanded] = useState(isCurrent);
  const [comment, setComment] = useState(stage.comment || '');
  const [newRisk, setNewRisk] = useState({ label: '', severity: 'medium' });
  const [savingComment, setSavingComment] = useState(false);
  const theme = STATUS_THEME[stage.status] || STATUS_THEME.pending;

  const toggleChecklist = async (itemKey, done) => {
    try {
      await axios.patch(
        `${API_URL}/api/roadmaps/${roadmapId}/stages/${stage.key}/checklist/${itemKey}`,
        { done }
      );
      toast.success(done ? '✓' : '○', { duration: 700 });
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const setStatus = async (status) => {
    try {
      await axios.patch(`${API_URL}/api/roadmaps/${roadmapId}/stages/${stage.key}`, { status });
      toast.success('Status updated');
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const saveComment = async () => {
    setSavingComment(true);
    try {
      await axios.patch(`${API_URL}/api/roadmaps/${roadmapId}/stages/${stage.key}`, { comment });
      toast.success('Comment saved');
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSavingComment(false); }
  };

  const addRisk = async () => {
    if (!newRisk.label.trim()) return;
    try {
      await axios.post(`${API_URL}/api/roadmaps/${roadmapId}/stages/${stage.key}/risks`, newRisk);
      toast.success('Risk added');
      setNewRisk({ label: '', severity: 'medium' });
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const removeRisk = async (rid) => {
    try {
      await axios.delete(`${API_URL}/api/roadmaps/${roadmapId}/stages/${stage.key}/risks/${rid}`);
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const label = pick(stage, lang, 'label');
  const description = pick(stage, lang, 'description');
  const recommended = pick(stage, lang, 'recommended_next');

  return (
    <div
      className={`rounded-2xl border-2 ${theme.border} ${theme.bg} overflow-hidden transition-all shrink-0 w-[300px] flex flex-col`}
      data-testid={`stage-card-${stage.key}`}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-200/70 bg-white/40">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500">
              {label}
            </p>
            <p className="text-[11.5px] text-zinc-700 leading-snug mt-0.5 line-clamp-2">
              {description}
            </p>
          </div>
          <span
            className={`shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${theme.border} ${theme.text} bg-white`}
            data-testid={`stage-status-${stage.key}`}
          >
            {theme.label[lang] || theme.label.en}
          </span>
        </div>

        {/* SLA / deadline */}
        {stage.deadline_at ? (
          <div className={`mt-2 inline-flex items-center gap-1 text-[10px] ${stage.sla_breached ? 'text-rose-700' : 'text-zinc-500'}`}>
            <Clock className="w-3 h-3" />
            SLA {stage.sla_days || 0}d
            {stage.sla_breached ? ' · overdue' : ''}
          </div>
        ) : null}
      </div>

      {/* Checklist */}
      <div className="px-4 py-3 space-y-1.5">
        <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500 mb-1">
          {lang === 'uk' ? 'Дії менеджера' : lang === 'ru' ? 'Действия' : 'Manager actions'}
        </p>
        {(stage.checklist || []).length === 0 ? (
          <p className="text-[11px] text-zinc-400 italic">—</p>
        ) : (
          (stage.checklist || []).map((c) => (
            <button
              key={c.key}
              onClick={() => toggleChecklist(c.key, !c.done)}
              className="w-full text-left flex items-center gap-2 group"
              data-testid={`stage-checklist-${stage.key}-${c.key}`}
            >
              {c.done
                ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                : <Circle className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-600 shrink-0" />}
              <span className={`text-[11.5px] ${c.done ? 'line-through text-zinc-400' : 'text-zinc-800'}`}>
                {c.label}
              </span>
            </button>
          ))
        )}
      </div>

      {/* Status actions */}
      <div className="px-4 pb-2 flex flex-wrap gap-1.5">
        {['in_progress', 'done', 'blocked', 'skipped'].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            disabled={stage.status === s}
            className={`text-[10px] px-2 py-0.5 rounded-full border ${stage.status === s ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'} disabled:opacity-60 disabled:cursor-not-allowed`}
            data-testid={`stage-setstatus-${stage.key}-${s}`}
          >
            {STATUS_THEME[s].label[lang] || s}
          </button>
        ))}
      </div>

      {/* Recommended next */}
      {recommended && (
        <div className="px-4 pb-3">
          <div className="bg-blue-50 border border-blue-200 rounded-lg px-2.5 py-1.5">
            <p className="text-[10px] uppercase tracking-wider font-bold text-blue-700 mb-0.5">
              {lang === 'uk' ? 'Рекомендований крок' : lang === 'ru' ? 'Рекомендация' : 'Recommended next'}
            </p>
            <p className="text-[11.5px] text-blue-900 leading-snug">{recommended}</p>
          </div>
        </div>
      )}

      {/* Expandable: comment + risks + history */}
      <div className="border-t border-zinc-200/70 bg-white">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2 text-[11px] text-zinc-500 hover:bg-zinc-50"
          data-testid={`stage-expand-${stage.key}`}
        >
          <span>{lang === 'uk' ? 'Деталі' : lang === 'ru' ? 'Детали' : 'Details'}</span>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        {expanded && (
          <div className="px-4 pb-3 space-y-3">
            {/* Comment */}
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500 mb-1">
                {lang === 'uk' ? 'Коментар' : lang === 'ru' ? 'Комментарий' : 'Comment'}
              </p>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                onBlur={() => (comment !== (stage.comment || '')) && saveComment()}
                rows={2}
                placeholder={lang === 'uk' ? 'Нотатка по етапу…' : lang === 'ru' ? 'Заметка по этапу…' : 'Stage note…'}
                className="w-full text-[11.5px] px-2 py-1.5 rounded border border-zinc-200 focus:border-[#4F46E5] focus:ring-1 focus:ring-[#4F46E5]/30 outline-none"
                data-testid={`stage-comment-${stage.key}`}
              />
              {savingComment && <p className="text-[10px] text-zinc-400 mt-0.5">Saving…</p>}
            </div>

            {/* Risks */}
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500 mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-rose-500" />
                {lang === 'uk' ? 'Ризики' : lang === 'ru' ? 'Риски' : 'Risks'}
                {(stage.risks || []).length > 0 && (
                  <span className="text-rose-600 font-bold">({stage.risks.length})</span>
                )}
              </p>
              {(stage.risks || []).map((r) => {
                const sev = SEVERITY_THEME[r.severity] || SEVERITY_THEME.medium;
                return (
                  <div key={r.id} className="flex items-start gap-1.5 mb-1" data-testid={`stage-risk-${r.id}`}>
                    <span className={`text-[10px] px-1.5 rounded ${sev.bg} ${sev.text} font-semibold`}>{r.severity}</span>
                    <p className="text-[11.5px] text-zinc-700 flex-1 leading-snug">{r.label}</p>
                    <button onClick={() => removeRisk(r.id)} className="text-zinc-400 hover:text-rose-500" title="Remove">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}
              <div className="flex gap-1 mt-1">
                <input
                  value={newRisk.label}
                  onChange={(e) => setNewRisk({ ...newRisk, label: e.target.value })}
                  placeholder={lang === 'uk' ? 'Новий ризик…' : 'New risk…'}
                  className="flex-1 text-[11px] px-2 py-1 rounded border border-zinc-200 outline-none focus:border-[#4F46E5]"
                  data-testid={`stage-risk-input-${stage.key}`}
                />
                <select
                  value={newRisk.severity}
                  onChange={(e) => setNewRisk({ ...newRisk, severity: e.target.value })}
                  className="text-[11px] px-1 py-1 rounded border border-zinc-200"
                >
                  <option value="low">low</option>
                  <option value="medium">med</option>
                  <option value="high">high</option>
                </select>
                <button onClick={addRisk}
                  className="px-2 py-1 rounded bg-zinc-900 text-white text-[11px] hover:bg-zinc-700"
                  data-testid={`stage-risk-add-${stage.key}`}>
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Transitions history */}
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500 mb-1 flex items-center gap-1">
                <History className="w-3 h-3" />
                {lang === 'uk' ? 'Історія' : lang === 'ru' ? 'История' : 'History'}
              </p>
              <ul className="space-y-0.5">
                {(stage.transitions || []).slice(-5).reverse().map((tr, idx) => (
                  <li key={idx} className="text-[10.5px] text-zinc-500 leading-snug">
                    <span className="font-mono">{(tr.at || '').slice(5, 16).replace('T', ' ')}</span>
                    {' · '}
                    <span className="text-zinc-700">{tr.from || '∅'}</span>
                    {' → '}
                    <span className="text-zinc-900 font-semibold">{tr.to}</span>
                    {tr.by ? <span className="text-zinc-400"> · {tr.by.split('@')[0]}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const SalesPipelineBoard = ({ roadmap, lang, onChanged }) => {
  if (!roadmap) return null;
  const stages = roadmap.stages || [];
  const currentIdx = roadmap.current_stage_index ?? -1;
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-4" data-testid="sales-pipeline-board">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="text-sm font-semibold text-zinc-900">{roadmap.title || 'Sales Pipeline'}</h4>
          <p className="text-[11px] text-zinc-500">
            {lang === 'uk' ? 'Етап' : 'Stage'} {Math.max(currentIdx + 1, 1)}/{stages.length}
            {' · '}{roadmap.progress_pct || 0}%
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-32 h-2 bg-zinc-100 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500" style={{ width: `${roadmap.progress_pct || 0}%` }} />
          </div>
        </div>
      </div>
      <div className="overflow-x-auto -mx-1 px-1 pb-2">
        <div className="flex gap-3 items-stretch">
          {stages.map((s, idx) => (
            <StageCard
              key={s.key}
              stage={s}
              roadmapId={roadmap.id}
              lang={lang}
              isCurrent={idx === currentIdx}
              onChanged={onChanged}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default SalesPipelineBoard;
