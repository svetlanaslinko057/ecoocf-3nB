/**
 * FAQManager — Phase D1.
 *
 * CRUD for FAQ items. Filters: group / page_path / lang / q.
 * FAQ items feed the `faq` block via `faq_group` reference OR the per-page
 * FAQ section (`page_path`). Every mutation invalidates prerender cache.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Plus, PencilSimple, Trash, MagnifyingGlass, ArrowClockwise, X } from '@phosphor-icons/react';
import { contentApi } from './contentApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Select, Button, Toggle, Skeleton } from '../seo/_shared';

const EMPTY_FAQ = {
  question: '', answer: '<p></p>', group: '', page_path: '',
  lang: 'uk', order: 100, published: true, tags: [],
};

export default function FAQManager() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState({ group: '', page_path: '', lang: '', q: '' });
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => v && (params[k] = v));
      const r = await contentApi.listFaq(params);
      setItems(r.items || []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const doSave = async () => {
    try {
      if (editing.id) {
        await contentApi.updateFaq(editing.id, editing);
      } else {
        await contentApi.createFaq(editing);
      }
      setEditing(null);
      toast.success('Збережено');
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const doDelete = async (faq) => {
    if (!window.confirm(`Видалити це питання?`)) return;
    try {
      await contentApi.deleteFaq(faq.id);
      toast.success('Видалено');
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="FAQ Engine"
          subtitle="CRUD для FAQ. Підключайте групи в блоки FAQ через faq_group."
          icon={MagnifyingGlass}
          right={
            <Button variant="primary" onClick={() => setEditing({ ...EMPTY_FAQ })} data-testid="faq-create">
              <Plus size={13} weight="bold" /> Нове питання
            </Button>
          }
        />
        <CardBody>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <Field label="Group"><Input value={filters.group} onChange={(e) => setFilters({ ...filters, group: e.target.value })} placeholder="battery-utilization" data-testid="faq-filter-group" /></Field>
            <Field label="Page path"><Input value={filters.page_path} onChange={(e) => setFilters({ ...filters, page_path: e.target.value })} placeholder="/services/battery..." /></Field>
            <Field label="Lang"><Select value={filters.lang} onChange={(e) => setFilters({ ...filters, lang: e.target.value })}><option value="">—</option><option value="uk">UK</option><option value="en">EN</option></Select></Field>
            <Field label="Search"><Input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="..." /></Field>
          </div>

          {loading ? <Skeleton /> : items.length === 0 ? (
            <div className="py-16 text-center text-[13px] text-[#71717A]">Жодного питання</div>
          ) : (
            <div className="space-y-2">
              {items.map((f) => (
                <div key={f.id} className="rounded-lg border border-[#E4E4E7] p-3 flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#F4F4F5] text-[#3F3F46]">#{f.order}</span>
                      {f.group ? <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200">{f.group}</span> : null}
                      {f.page_path ? <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#F4F4F5] text-[#3F3F46] font-mono">{f.page_path}</span> : null}
                      <span className="text-[10px] uppercase text-[#71717A]">{f.lang}</span>
                      {!f.published ? <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-50 text-rose-800">draft</span> : null}
                    </div>
                    <div className="text-[13px] font-semibold text-[#18181B]">{f.question}</div>
                    <div className="text-[12px] text-[#52525B] mt-1 line-clamp-2" dangerouslySetInnerHTML={{ __html: f.answer }} />
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setEditing({ ...f })} className="h-8 w-8 rounded-md hover:bg-emerald-50 text-emerald-700 inline-flex items-center justify-center" data-testid={`faq-edit-${f.id}`}>
                      <PencilSimple size={13} weight="bold" />
                    </button>
                    <button onClick={() => doDelete(f)} className="h-8 w-8 rounded-md hover:bg-rose-50 text-rose-600 inline-flex items-center justify-center">
                      <Trash size={13} weight="bold" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-3 flex items-center justify-between text-[11.5px] text-[#71717A]">
            <div>Питань: <strong>{items.length}</strong></div>
            <button onClick={load} className="inline-flex items-center gap-1 hover:text-emerald-700">
              <ArrowClockwise size={11} weight="bold" /> Оновити
            </button>
          </div>
        </CardBody>
      </Card>

      {editing ? (
        <FAQEditModal
          initial={editing}
          onChange={setEditing}
          onSave={doSave}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}

function FAQEditModal({ initial, onChange, onSave, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-2xl bg-white rounded-xl border border-[#E4E4E7] flex flex-col max-h-[92vh]">
        <header className="flex items-center gap-2 px-4 py-3 border-b border-[#E4E4E7]">
          <h3 className="flex-1 text-[14px] font-semibold">{initial.id ? 'Редагувати FAQ' : 'Нове питання'}</h3>
          <button onClick={onClose} className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center"><X size={14} weight="bold" /></button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <Field label="Question" required><Input value={initial.question} onChange={(e) => onChange({ ...initial, question: e.target.value })} data-testid="faq-modal-question" /></Field>
          <Field label="Answer (HTML)" required><Textarea rows={5} value={initial.answer} onChange={(e) => onChange({ ...initial, answer: e.target.value })} data-testid="faq-modal-answer" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Group"><Input value={initial.group} onChange={(e) => onChange({ ...initial, group: e.target.value })} placeholder="battery-utilization" /></Field>
            <Field label="Page path (optional)"><Input value={initial.page_path} onChange={(e) => onChange({ ...initial, page_path: e.target.value })} placeholder="/services/battery-utilization" /></Field>
            <Field label="Language"><Select value={initial.lang} onChange={(e) => onChange({ ...initial, lang: e.target.value })}><option value="uk">UK</option><option value="en">EN</option></Select></Field>
            <Field label="Order"><Input type="number" value={initial.order} onChange={(e) => onChange({ ...initial, order: +e.target.value })} /></Field>
          </div>
          <div className="pt-2">
            <Toggle checked={initial.published} onChange={(v) => onChange({ ...initial, published: v })} label="Опубліковано" hint="Тільки опубліковані FAQ видно ботам та публічним користувачам" />
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[#E4E4E7]">
          <Button variant="ghost" onClick={onClose}>Скасувати</Button>
          <Button variant="primary" onClick={onSave} data-testid="faq-modal-save">Зберегти</Button>
        </footer>
      </div>
    </div>
  );
}
