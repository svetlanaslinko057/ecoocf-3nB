/**
 * Content Pages list — Phase D1.
 *
 * Filters: status, kind, lang, free-text search.
 * Actions: new page, open editor, quick-transition (draft/review/publish/archive).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Plus, MagnifyingGlass, PencilSimple, Trash, Eye, ArrowClockwise,
  Circle, CheckCircle, Archive, DotsThreeVertical,
} from '@phosphor-icons/react';
import { contentApi } from './contentApi';
import { Card, CardHeader, CardBody, Field, Input, Select, Button, Skeleton } from '../seo/_shared';

const STATUS_META = {
  draft:     { label: 'Чернетка',   color: 'bg-[#F4F4F5] text-[#3F3F46] border-[#E4E4E7]', icon: Circle },
  review:    { label: 'На рев’ю',   color: 'bg-amber-50 text-amber-800 border-amber-200',      icon: DotsThreeVertical },
  published: { label: 'Опубліковано', color: 'bg-emerald-50 text-emerald-800 border-emerald-200', icon: CheckCircle },
  archived:  { label: 'Архів',        color: 'bg-rose-50 text-rose-800 border-rose-200',        icon: Archive },
};

const KINDS = [
  { value: '',          label: '— всі типи —' },
  { value: 'page',      label: 'Page' },
  { value: 'service',   label: 'Service' },
  { value: 'industry',  label: 'Industry' },
  { value: 'landing',   label: 'Landing' },
  { value: 'blog',      label: 'Blog' },
  { value: 'waste_code', label: 'Waste code' },
];

export default function ContentPagesList() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState({ status: '', kind: '', lang: '', q: '' });
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newPage, setNewPage] = useState({ path: '', lang: 'uk', kind: 'page', title: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.status) params.status = filters.status;
      if (filters.kind) params.kind = filters.kind;
      if (filters.lang) params.lang = filters.lang;
      if (filters.q) params.q = filters.q;
      const r = await contentApi.listPages(params);
      setItems(r.items || []);
    } catch (e) {
      toast.error(`Не вдалося завантажити сторінки: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const doCreate = async () => {
    if (!newPage.path) {
      toast.error('Шлях обов’язковий');
      return;
    }
    setCreating(true);
    try {
      const r = await contentApi.createPage({
        ...newPage,
        blocks: [{ type: 'hero', title: newPage.title || newPage.path }],
      });
      toast.success('Сторінку створено');
      setShowCreate(false);
      setNewPage({ path: '', lang: 'uk', kind: 'page', title: '' });
      navigate(`/app/content/pages/${r.page.id}`);
    } catch (e) {
      toast.error(e.message || 'Помилка');
    } finally {
      setCreating(false);
    }
  };

  const doTransition = async (page, status) => {
    try {
      await contentApi.transitionPage(page.id, status);
      toast.success(`Статус змінено → ${STATUS_META[status]?.label || status}`);
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const doDelete = async (page) => {
    if (!window.confirm(`Видалити сторінку ${page.path}?`)) return;
    try {
      await contentApi.deletePage(page.id);
      toast.success('Видалено');
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const filtered = useMemo(() => items, [items]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Сторінки"
          subtitle="Керуйте всіма публічними CMS-сторінками — чернетки, рев’ю, опубліковані, архів."
          icon={MagnifyingGlass}
          right={
            <Button variant="primary" onClick={() => setShowCreate((s) => !s)} data-testid="content-create-toggle">
              <Plus size={13} weight="bold" /> Нова сторінка
            </Button>
          }
        />
        <CardBody>
          {showCreate ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4 p-3 rounded-xl bg-emerald-50/60 border border-emerald-200">
              <Field label="Шлях" required hint="/services/battery-utilization">
                <Input value={newPage.path} onChange={(e) => setNewPage({ ...newPage, path: e.target.value })} placeholder="/services/..." data-testid="content-new-path" />
              </Field>
              <Field label="Мова">
                <Select value={newPage.lang} onChange={(e) => setNewPage({ ...newPage, lang: e.target.value })} data-testid="content-new-lang">
                  <option value="uk">Ukrainian</option>
                  <option value="en">English</option>
                </Select>
              </Field>
              <Field label="Тип">
                <Select value={newPage.kind} onChange={(e) => setNewPage({ ...newPage, kind: e.target.value })}>
                  {KINDS.filter((k) => k.value).map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                </Select>
              </Field>
              <Field label="Заголовок" hint="використається в першому hero-блоці">
                <Input value={newPage.title} onChange={(e) => setNewPage({ ...newPage, title: e.target.value })} placeholder="Утилізація..." />
              </Field>
              <div className="sm:col-span-2 lg:col-span-4 flex items-center justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowCreate(false)} disabled={creating}>Скасувати</Button>
                <Button variant="primary" onClick={doCreate} disabled={creating} data-testid="content-new-submit">
                  {creating ? 'Створюю…' : 'Створити чернетку'}
                </Button>
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <Field label="Статус">
              <Select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} data-testid="filter-status">
                <option value="">— всі —</option>
                {Object.entries(STATUS_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
              </Select>
            </Field>
            <Field label="Тип">
              <Select value={filters.kind} onChange={(e) => setFilters({ ...filters, kind: e.target.value })} data-testid="filter-kind">
                {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </Select>
            </Field>
            <Field label="Мова">
              <Select value={filters.lang} onChange={(e) => setFilters({ ...filters, lang: e.target.value })} data-testid="filter-lang">
                <option value="">— всі —</option>
                <option value="uk">Ukrainian</option>
                <option value="en">English</option>
              </Select>
            </Field>
            <Field label="Пошук">
              <Input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="тайтл, шлях, slug…" data-testid="filter-q" />
            </Field>
          </div>

          {loading ? (
            <Skeleton />
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-[13px] text-[#71717A]">
              Порожньо. Натисніть &laquo;Нова сторінка&raquo; щоб почати.
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-[#E4E4E7]">
              <table className="w-full text-[13px]">
                <thead className="bg-[#FAFAFA] text-[11px] font-medium text-[#71717A] uppercase">
                  <tr>
                    <th className="text-left px-4 py-2.5">Сторінка</th>
                    <th className="text-left px-4 py-2.5">Тип</th>
                    <th className="text-left px-4 py-2.5">Мова</th>
                    <th className="text-left px-4 py-2.5">Статус</th>
                    <th className="text-left px-4 py-2.5">Блоків</th>
                    <th className="text-left px-4 py-2.5">Оновлено</th>
                    <th className="text-right px-4 py-2.5">Дії</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F4F4F5]">
                  {filtered.map((p) => {
                    const s = STATUS_META[p.status] || STATUS_META.draft;
                    const StatusIcon = s.icon;
                    return (
                      <tr key={p.id} className="hover:bg-[#FAFAFA] transition">
                        <td className="px-4 py-3">
                          <div className="font-medium text-[#18181B]">{p.title || p.slug || p.path}</div>
                          <div className="text-[11.5px] text-[#71717A] mt-0.5">{p.path}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-[#F4F4F5] text-[#3F3F46] border border-[#E4E4E7]">
                            {p.kind || 'page'}
                          </span>
                        </td>
                        <td className="px-4 py-3 uppercase text-[11.5px] text-[#3F3F46]">{p.lang}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11.5px] font-medium border ${s.color}`}>
                            <StatusIcon size={10} weight="fill" /> {s.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[#3F3F46]">{(p.blocks || []).length}</td>
                        <td className="px-4 py-3 text-[11.5px] text-[#71717A]">
                          {p.updated_at ? new Date(p.updated_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <a
                              href={`${p.path}?lang=${p.lang}`}
                              target="_blank"
                              rel="noreferrer"
                              title="Відкрити публічну"
                              className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center text-[#3F3F46]"
                            >
                              <Eye size={14} weight="bold" />
                            </a>
                            <button
                              onClick={() => navigate(`/app/content/pages/${p.id}`)}
                              title="Редагувати"
                              data-testid={`content-edit-${p.id}`}
                              className="h-8 w-8 rounded-md hover:bg-emerald-50 inline-flex items-center justify-center text-emerald-700"
                            >
                              <PencilSimple size={14} weight="bold" />
                            </button>
                            <QuickTransition page={p} onGo={(st) => doTransition(p, st)} />
                            <button
                              onClick={() => doDelete(p)}
                              title="Видалити"
                              className="h-8 w-8 rounded-md hover:bg-rose-50 inline-flex items-center justify-center text-rose-600"
                            >
                              <Trash size={14} weight="bold" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-3 flex items-center justify-between text-[11.5px] text-[#71717A]">
            <div>Знайдено: <strong>{filtered.length}</strong></div>
            <button onClick={load} className="inline-flex items-center gap-1 hover:text-emerald-700" data-testid="content-refresh">
              <ArrowClockwise size={11} weight="bold" /> Оновити
            </button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function QuickTransition({ page, onGo }) {
  const [open, setOpen] = useState(false);
  const options = [
    { s: 'draft',     l: 'В чернетку' },
    { s: 'review',    l: 'На рев’ю' },
    { s: 'published', l: 'Опублікувати' },
    { s: 'archived',  l: 'Архівувати' },
  ].filter((o) => o.s !== page.status);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        title="Змінити статус"
        className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center text-[#3F3F46]"
      >
        <DotsThreeVertical size={16} weight="bold" />
      </button>
      {open ? (
        <>
          <button className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-9 z-50 min-w-[160px] rounded-lg border border-[#E4E4E7] bg-white shadow-lg py-1">
            {options.map((o) => (
              <button
                key={o.s}
                onClick={() => { setOpen(false); onGo(o.s); }}
                className="w-full text-left px-3 py-2 text-[12.5px] hover:bg-[#F4F4F5]"
              >
                {o.l}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
