/**
 * SeoPages — Page Metadata Manager: CRUD per route (path, title/desc/kw
 * per language, canonical/robots override, OG/Twitter overrides, schema
 * type, FAQ, breadcrumbs, sitemap changefreq/priority, excluded flag).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  FileText, Plus, Trash, MagnifyingGlass, PencilSimple, X,
  Question as QuestionIcon,
} from '@phosphor-icons/react';
import { seoApi } from './seoApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Select, Toggle, Button, Skeleton } from './_shared';

const emptyPage = (path = '') => ({
  path,
  _uk: { title: '', description: '', keywords: '' },
  _en: { title: '', description: '', keywords: '' },
  canonical_override: '',
  robots_override: '',
  og_title: '',
  og_description: '',
  og_image: '',
  twitter_title: '',
  twitter_description: '',
  schema_type: '',
  changefreq: 'monthly',
  priority: '0.5',
  excluded: false,
  faq: [],
  breadcrumbs: [],
});

const PageEditor = ({ open, initial, onClose, onSaved }) => {
  const [draft, setDraft] = useState(initial || emptyPage());
  const [saving, setSaving] = useState(false);

  useEffect(() => { setDraft(initial || emptyPage()); }, [initial]);
  if (!open) return null;

  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));
  const setLang = (lang, k, v) => setDraft(d => ({ ...d, [lang]: { ...(d[lang] || {}), [k]: v } }));
  const addFaq = () => setDraft(d => ({ ...d, faq: [...(d.faq || []), { q: '', a: '' }] }));
  const setFaq = (i, k, v) => setDraft(d => {
    const arr = [...(d.faq || [])];
    arr[i] = { ...arr[i], [k]: v };
    return { ...d, faq: arr };
  });
  const rmFaq = (i) => setDraft(d => ({ ...d, faq: (d.faq || []).filter((_, idx) => idx !== i) }));

  const save = async () => {
    if (!draft.path || !draft.path.startsWith('/')) {
      toast.error('Path має починатися з /');
      return;
    }
    setSaving(true);
    try {
      await seoApi.upsertPage(draft);
      toast.success('Збережено');
      onSaved();
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 bg-black/40" onClick={onClose}>
      <div className="w-full max-w-4xl bg-white rounded-2xl border border-[#E4E4E7] max-h-[92vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-[#E4E4E7] flex items-center gap-3">
          <FileText size={16} weight="bold" className="text-[#3F3F46]" />
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-semibold text-[#18181B] truncate">
              {initial?.path ? `Редагування: ${initial.path}` : 'Нова сторінка'}
            </div>
            <div className="text-[11.5px] text-[#71717A]">Всі поля — override. Порожнє → використовується базове значення.</div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-[#F4F4F5] flex items-center justify-center"><X size={14} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          <Field label="Path" hint="Починається з /. Наприклад: /waste, /calculator, /waste-code/lamps.">
            <Input value={draft.path || ''} onChange={e => set('path', e.target.value)} placeholder="/services" data-testid="seo-page-path" disabled={!!initial?.path} />
          </Field>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Українська (uk)" icon={FileText} />
              <CardBody className="space-y-3">
                <Field label="Title"><Input value={draft._uk?.title || ''} onChange={e => setLang('_uk', 'title', e.target.value)} /></Field>
                <Field label="Description"><Textarea value={draft._uk?.description || ''} onChange={e => setLang('_uk', 'description', e.target.value)} /></Field>
                <Field label="Keywords"><Input value={draft._uk?.keywords || ''} onChange={e => setLang('_uk', 'keywords', e.target.value)} /></Field>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="English (en)" icon={FileText} />
              <CardBody className="space-y-3">
                <Field label="Title"><Input value={draft._en?.title || ''} onChange={e => setLang('_en', 'title', e.target.value)} /></Field>
                <Field label="Description"><Textarea value={draft._en?.description || ''} onChange={e => setLang('_en', 'description', e.target.value)} /></Field>
                <Field label="Keywords"><Input value={draft._en?.keywords || ''} onChange={e => setLang('_en', 'keywords', e.target.value)} /></Field>
              </CardBody>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader title="OpenGraph та Twitter override" icon={FileText} />
              <CardBody className="grid gap-3 grid-cols-2">
                <Field label="OG Title"><Input value={draft.og_title || ''} onChange={e => set('og_title', e.target.value)} /></Field>
                <Field label="OG Description"><Input value={draft.og_description || ''} onChange={e => set('og_description', e.target.value)} /></Field>
                <Field className="col-span-2" label="OG image (URL)"><Input value={draft.og_image || ''} onChange={e => set('og_image', e.target.value)} placeholder="https://... або /path/image.png" /></Field>
                <Field label="Twitter Title"><Input value={draft.twitter_title || ''} onChange={e => set('twitter_title', e.target.value)} /></Field>
                <Field label="Twitter Description"><Input value={draft.twitter_description || ''} onChange={e => set('twitter_description', e.target.value)} /></Field>
              </CardBody>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader title="Robots і схема" icon={FileText} />
              <CardBody className="grid gap-3 grid-cols-2">
                <Field label="Canonical override (URL)"><Input value={draft.canonical_override || ''} onChange={e => set('canonical_override', e.target.value)} /></Field>
                <Field label="Robots override" hint="Напр.: noindex,nofollow"><Input value={draft.robots_override || ''} onChange={e => set('robots_override', e.target.value)} /></Field>
                <Field label="Schema type" hint="WebPage / Service / FAQPage / Article / інше"><Input value={draft.schema_type || ''} onChange={e => set('schema_type', e.target.value)} /></Field>
                <Field label="Changefreq">
                  <Select value={draft.changefreq || 'monthly'} onChange={e => set('changefreq', e.target.value)}>
                    {['always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never'].map(f => <option key={f} value={f}>{f}</option>)}
                  </Select>
                </Field>
                <Field label="Priority" hint="0.0–1.0"><Input value={draft.priority || '0.5'} onChange={e => set('priority', e.target.value)} /></Field>
                <Field label="Lastmod override" hint="YYYY-MM-DD (порожнє = авто)"><Input value={draft.lastmod || ''} onChange={e => set('lastmod', e.target.value)} placeholder="2026-01-01" /></Field>
                <div className="col-span-2 pt-2">
                  <Toggle checked={!!draft.excluded} onChange={v => set('excluded', v)} label="Виключити з sitemap.xml" hint="URL не буде публікуватися в sitemap. Meta залишається." />
                </div>
              </CardBody>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader
                title="FAQ (FAQPage schema)"
                subtitle="Кожен Q/A автоматично потрапляє в JSON-LD FAQPage та rich results."
                icon={QuestionIcon}
                right={<Button size="sm" variant="secondary" onClick={addFaq}><Plus size={12} weight="bold" /> Додати пару</Button>}
              />
              <CardBody className="space-y-3">
                {(draft.faq || []).length === 0 ? (
                  <div className="text-[12px] text-[#71717A]">FAQ не додано.</div>
                ) : (draft.faq || []).map((row, i) => (
                  <div key={i} className="flex gap-2">
                    <div className="flex-1 space-y-2">
                      <Input placeholder="Питання" value={row.q || ''} onChange={e => setFaq(i, 'q', e.target.value)} />
                      <Textarea placeholder="Відповідь" value={row.a || ''} onChange={e => setFaq(i, 'a', e.target.value)} />
                    </div>
                    <button onClick={() => rmFaq(i)} className="w-8 h-8 rounded-lg hover:bg-rose-50 text-rose-600 flex items-center justify-center shrink-0"><Trash size={13} /></button>
                  </div>
                ))}
              </CardBody>
            </Card>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-[#E4E4E7] flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Скасувати</Button>
          <Button variant="primary" onClick={save} disabled={saving} data-testid="seo-page-save">
            {saving ? 'Зберігаю…' : 'Зберегти'}
          </Button>
        </div>
      </div>
    </div>
  );
};

const SeoPages = () => {
  const [items, setItems] = useState([]);
  const [known, setKnown] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null | 'new' | pageDoc

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const j = await seoApi.listPages(q);
      setItems(j.items || []);
      setKnown(j.known_routes || []);
    } catch (e) { toast.error(`Завантаження: ${e.message}`); }
    finally { setLoading(false); }
  }, [q]);
  useEffect(() => { load(); }, [load]);

  const del = async (path) => {
    if (!window.confirm(`Видалити override для ${path}?`)) return;
    try {
      await seoApi.deletePage(path);
      toast.success('Видалено');
      load();
    } catch (e) { toast.error(e.message); }
  };

  const known_not_defined = useMemo(() => {
    const defined = new Set(items.map(i => i.path));
    return (known || []).filter(p => !defined.has(p));
  }, [known, items]);

  return (
    <div data-testid="seo-pages-tab">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Фільтр по path…"
            className="w-full h-9 pl-8 pr-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] text-[#18181B] focus:outline-none focus:border-emerald-500"
            data-testid="seo-pages-search"
          />
        </div>
        <Button variant="primary" onClick={() => setEditing('new')} data-testid="seo-pages-add"><Plus size={13} weight="bold" /> Додати сторінку</Button>
      </div>

      <Card>
        <CardHeader
          title={`Перевизначення метаданих (${items.length})`}
          subtitle="Це override над базовим registry. Порожні поля використовують базові значення."
          icon={FileText}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="text-[#71717A]">
              <tr className="text-left">
                <th className="px-5 py-2 font-medium">Path</th>
                <th className="px-3 py-2 font-medium">Title (uk)</th>
                <th className="px-3 py-2 font-medium">Changefreq</th>
                <th className="px-3 py-2 font-medium">Priority</th>
                <th className="px-3 py-2 font-medium">Sitemap</th>
                <th className="px-3 py-2 font-medium">Оновлено</th>
                <th className="px-5 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="px-5 py-6 text-center text-[#71717A]">Завантаження…</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={7} className="px-5 py-6 text-center text-[#71717A]">Ще немає перевизначень. Натисніть «Додати сторінку».</td></tr>
              ) : items.map(row => (
                <tr key={row.path} className="border-t border-[#F4F4F5] hover:bg-[#FAFAFA]">
                  <td className="px-5 py-2 font-mono text-[12px] text-[#18181B]">{row.path}</td>
                  <td className="px-3 py-2 text-[#3F3F46] max-w-xs truncate">{row._uk?.title || row.title || <span className="text-[#A1A1AA]">—</span>}</td>
                  <td className="px-3 py-2 text-[#71717A]">{row.changefreq || <span className="text-[#A1A1AA]">—</span>}</td>
                  <td className="px-3 py-2 text-[#71717A]">{row.priority || <span className="text-[#A1A1AA]">—</span>}</td>
                  <td className="px-3 py-2">
                    {row.excluded
                      ? <span className="text-[11.5px] font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded">excluded</span>
                      : <span className="text-[11.5px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">included</span>}
                  </td>
                  <td className="px-3 py-2 text-[11.5px] text-[#71717A]">{row.updated_at ? new Date(row.updated_at).toLocaleString() : '—'}</td>
                  <td className="px-5 py-2 text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button size="sm" variant="secondary" onClick={() => setEditing(row)} data-testid={`seo-page-edit-${row.path.replace(/\//g, '_')}`}><PencilSimple size={11} /></Button>
                      <Button size="sm" variant="danger" onClick={() => del(row.path)}><Trash size={11} /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {known_not_defined.length > 0 ? (
        <Card className="mt-4">
          <CardHeader title="Швидко додати" subtitle="Маршрути з реєстру, для яких немає override." />
          <CardBody className="flex flex-wrap gap-2">
            {known_not_defined.map(p => (
              <button
                key={p}
                onClick={() => setEditing(emptyPage(p))}
                className="px-2.5 py-1 rounded-md border border-[#E4E4E7] text-[12px] text-[#3F3F46] hover:bg-[#F4F4F5] font-mono"
              >
                + {p}
              </button>
            ))}
          </CardBody>
        </Card>
      ) : null}

      <PageEditor
        open={!!editing}
        initial={editing === 'new' ? emptyPage() : editing}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load(); }}
      />
    </div>
  );
};

export default SeoPages;
