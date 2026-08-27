/**
 * ContentPageEditor — Phase D1 block-based composer.
 *
 * Three-pane layout:
 *   Left  : block palette (12 types) + version history button
 *   Mid   : block list (drag-and-drop reorder via up/down arrows)
 *   Right : per-block edit form + page-level SEO / CMS tabs
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ArrowLeft, FloppyDisk, Eye, Circle, CheckCircle, Archive, DotsThreeVertical,
  ArrowUp, ArrowDown, Trash, Plus, ClockCounterClockwise, Warning,
} from '@phosphor-icons/react';
import { contentApi, BACKEND_URL } from './contentApi';
import { BLOCK_META } from './Blocks';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Select, Button, Skeleton } from '../seo/_shared';
import VersionHistoryPanel from './VersionHistoryPanel';
import UniversalTimeline from '@/components/unified/UniversalTimeline';

const STATUS_META = {
  draft:     { label: 'Чернетка',   color: 'bg-[#F4F4F5] text-[#3F3F46] border-[#E4E4E7]',   icon: Circle },
  review:    { label: 'На рев’ю',   color: 'bg-amber-50 text-amber-800 border-amber-200',        icon: DotsThreeVertical },
  published: { label: 'Опубліковано', color: 'bg-emerald-50 text-emerald-800 border-emerald-200', icon: CheckCircle },
  archived:  { label: 'Архів',        color: 'bg-rose-50 text-rose-800 border-rose-200',            icon: Archive },
};

// Merge helper: React-Router state → draft copy.
const clonePage = (p) => JSON.parse(JSON.stringify(p || {}));

export default function ContentPageEditor() {
  const { pageId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(null);   // server copy
  const [draft, setDraft] = useState(null); // editing copy
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [rightTab, setRightTab] = useState('block');
  const [showHistory, setShowHistory] = useState(false);

  const dirty = useMemo(() => JSON.stringify(page) !== JSON.stringify(draft), [page, draft]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await contentApi.getPage(pageId);
      setPage(r.page);
      setDraft(clonePage(r.page));
    } catch (e) {
      toast.error(e.message);
      navigate('/app/content/pages');
    } finally {
      setLoading(false);
    }
  }, [pageId, navigate]);

  useEffect(() => { load(); }, [load]);

  const doSave = async () => {
    if (!dirty) return;
    setSaving(true);
    try {
      const r = await contentApi.updatePage(pageId, {
        title: draft.title,
        summary: draft.summary,
        slug: draft.slug,
        kind: draft.kind,
        blocks: draft.blocks || [],
        seo: draft.seo || {},
        cms: draft.cms || {},
      });
      setPage(r.page);
      setDraft(clonePage(r.page));
      toast.success('Збережено');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const doTransition = async (status) => {
    if (dirty) {
      if (!window.confirm('Є незбережені зміни. Зберегти та змінити статус?')) return;
      await doSave();
    }
    try {
      await contentApi.transitionPage(pageId, status);
      toast.success(`Статус → ${STATUS_META[status]?.label || status}`);
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const addBlock = (type) => {
    const next = clonePage(draft);
    next.blocks = next.blocks || [];
    const blk = { type };
    // sensible defaults so validators keep the block on save
    if (type === 'hero') blk.title = 'Новий заголовок';
    if (type === 'rich_text') blk.html = '<p></p>';
    if (type === 'cta') { blk.title = 'Клікабельна дія'; blk.button_label = 'Контакти'; blk.button_href = '/contacts'; }
    if (type === 'stats') blk.items = [{ value: '100', suffix: '%', label: '' }];
    if (type === 'process') blk.steps = [];
    if (type === 'cards') blk.cards = [];
    if (type === 'gallery') blk.items = [];
    if (type === 'faq') blk.items = [];
    if (type === 'table') { blk.headers = []; blk.rows = []; }
    if (type === 'related_links') blk.items = [];
    if (type === 'quote') blk.text = '';
    if (type === 'image') { blk.url = ''; blk.alt = ''; }
    next.blocks.push(blk);
    setDraft(next);
    setSelectedIdx(next.blocks.length - 1);
    setRightTab('block');
  };

  const moveBlock = (idx, dir) => {
    const next = clonePage(draft);
    const j = idx + dir;
    if (j < 0 || j >= next.blocks.length) return;
    [next.blocks[idx], next.blocks[j]] = [next.blocks[j], next.blocks[idx]];
    setDraft(next);
    setSelectedIdx(j);
  };

  const deleteBlock = (idx) => {
    if (!window.confirm('Видалити блок?')) return;
    const next = clonePage(draft);
    next.blocks.splice(idx, 1);
    setDraft(next);
    setSelectedIdx(Math.max(0, Math.min(idx, next.blocks.length - 1)));
  };

  const patchBlock = (idx, patch) => {
    const next = clonePage(draft);
    next.blocks[idx] = { ...next.blocks[idx], ...patch };
    setDraft(next);
  };

  if (loading || !draft) return <Skeleton />;

  const status = STATUS_META[draft.status] || STATUS_META.draft;
  const StatusIcon = status.icon;
  const selectedBlock = draft.blocks?.[selectedIdx];
  const Editor = selectedBlock ? BLOCK_META[selectedBlock.type]?.Editor : null;

  const previewHref = `${BACKEND_URL}/api/prerender/render?path=${encodeURIComponent(draft.path)}&lang=${draft.lang}&force=1`;

  return (
    <div className="space-y-4">
      {/* Sticky top bar */}
      <div className="sticky top-0 z-30 -mx-1 mb-2 px-3 py-2 rounded-xl bg-white/95 backdrop-blur border border-[#E4E4E7] flex flex-wrap items-center gap-3">
        <button onClick={() => navigate('/app/content/pages')} className="h-8 px-2 rounded-md hover:bg-[#F4F4F5] inline-flex items-center gap-1 text-[13px]" data-testid="editor-back">
          <ArrowLeft size={13} weight="bold" /> Назад
        </button>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-[#18181B] truncate">{draft.title || draft.path}</div>
          <div className="text-[11.5px] text-[#71717A] mt-0.5 truncate">{draft.path} · v{draft.version} · {draft.lang}</div>
        </div>
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11.5px] font-medium border ${status.color}`}>
          <StatusIcon size={10} weight="fill" /> {status.label}
        </span>
        {dirty ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
            <Warning size={11} weight="fill" /> Незбережені зміни
          </span>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => setShowHistory(true)} data-testid="editor-history">
          <ClockCounterClockwise size={12} weight="bold" /> Історія
        </Button>
        <a href={previewHref} target="_blank" rel="noreferrer" className="h-8 px-3 rounded-md border border-[#E4E4E7] hover:bg-[#F4F4F5] inline-flex items-center gap-1 text-[12.5px]">
          <Eye size={12} weight="bold" /> Prerender
        </a>
        <TransitionButton status={draft.status} onGo={doTransition} />
        <Button variant="primary" onClick={doSave} disabled={!dirty || saving} data-testid="editor-save">
          <FloppyDisk size={13} weight="bold" /> {saving ? 'Зберігаю…' : 'Зберегти'}
        </Button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[220px_320px_1fr] gap-4">
        {/* PALETTE */}
        <Card>
          <CardHeader title="Палітра блоків" />
          <CardBody className="p-3">
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(BLOCK_META).map(([type, m]) => (
                <button
                  key={type}
                  onClick={() => addBlock(type)}
                  data-testid={`palette-add-${type}`}
                  className="px-2 py-2 rounded-lg border border-[#E4E4E7] bg-white text-left hover:bg-emerald-50 hover:border-emerald-200 transition"
                >
                  <div className="text-[12.5px] font-semibold text-[#18181B]">{m.label}</div>
                  <div className="text-[10.5px] text-[#71717A] mt-0.5">{m.hint}</div>
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* BLOCK LIST */}
        <Card>
          <CardHeader title={`Блоки · ${(draft.blocks || []).length}`} />
          <CardBody className="p-2">
            {(draft.blocks || []).length === 0 ? (
              <div className="py-8 text-center text-[12px] text-[#71717A]">Оберіть блок зі списку ліворуч</div>
            ) : (
              <ul className="space-y-1.5">
                {(draft.blocks || []).map((b, i) => {
                  const meta = BLOCK_META[b.type];
                  const label = b.title || b.text || (b.items && b.items[0]?.question) || meta?.label || b.type;
                  return (
                    <li key={i}>
                      <div
                        className={`group flex items-start gap-2 p-2 rounded-lg cursor-pointer transition ${selectedIdx === i ? 'bg-emerald-50 border border-emerald-200' : 'border border-transparent hover:bg-[#F4F4F5]'}`}
                        onClick={() => { setSelectedIdx(i); setRightTab('block'); }}
                        data-testid={`block-item-${i}`}
                      >
                        <div className="text-[10px] font-mono text-[#71717A] mt-0.5 w-6">#{i + 1}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[11px] uppercase tracking-wider font-semibold text-emerald-700">{meta?.label || b.type}</div>
                          <div className="text-[12px] text-[#18181B] truncate">{label}</div>
                        </div>
                        <div className="flex flex-col opacity-0 group-hover:opacity-100 transition">
                          <button onClick={(e) => { e.stopPropagation(); moveBlock(i, -1); }} className="h-4 w-4 text-[#71717A] hover:text-emerald-700"><ArrowUp size={11} weight="bold" /></button>
                          <button onClick={(e) => { e.stopPropagation(); moveBlock(i, 1); }} className="h-4 w-4 text-[#71717A] hover:text-emerald-700"><ArrowDown size={11} weight="bold" /></button>
                        </div>
                        <button onClick={(e) => { e.stopPropagation(); deleteBlock(i); }} className="opacity-0 group-hover:opacity-100 text-[#71717A] hover:text-rose-600 transition"><Trash size={12} weight="bold" /></button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* RIGHT PANE */}
        <div className="space-y-3">
          <div className="flex items-center gap-1 rounded-lg bg-[#F4F4F5] p-1 border border-[#E4E4E7] w-fit text-[12px]">
            {[
              { k: 'block', l: 'Block' },
              { k: 'seo',   l: 'SEO' },
              { k: 'cms',   l: 'CMS meta' },
            ].map((t) => (
              <button
                key={t.k}
                onClick={() => setRightTab(t.k)}
                data-testid={`right-tab-${t.k}`}
                className={`px-3 py-1 rounded-md ${rightTab === t.k ? 'bg-white shadow-sm text-emerald-800 font-medium' : 'text-[#3F3F46] hover:text-[#18181B]'}`}
              >
                {t.l}
              </button>
            ))}
          </div>

          {rightTab === 'block' && selectedBlock ? (
            <Card>
              <CardHeader title={`${BLOCK_META[selectedBlock.type]?.label || selectedBlock.type} — блок #${selectedIdx + 1}`} />
              <CardBody>
                {Editor ? <Editor value={selectedBlock} onChange={(patch) => patchBlock(selectedIdx, patch)} /> : (
                  <div className="text-[13px] text-[#71717A]">Редактор для {selectedBlock.type} не визначено.</div>
                )}
              </CardBody>
            </Card>
          ) : null}

          {rightTab === 'seo' ? (
            <Card>
              <CardHeader title="SEO для цієї сторінки" subtitle="Перекриває стандартні значення з SEO Center" />
              <CardBody className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label="SEO Title"><Input value={draft.seo?.title || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), title: e.target.value } })} /></Field>
                  <Field label="OG image URL"><Input value={draft.seo?.og_image || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), og_image: e.target.value } })} /></Field>
                  <Field className="md:col-span-2" label="SEO Description"><Textarea rows={2} value={draft.seo?.description || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), description: e.target.value } })} /></Field>
                  <Field className="md:col-span-2" label="Keywords (через кому)"><Input value={draft.seo?.keywords || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), keywords: e.target.value } })} /></Field>
                  <Field label="Canonical override"><Input value={draft.seo?.canonical_override || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), canonical_override: e.target.value } })} /></Field>
                  <Field label="Robots"><Input value={draft.seo?.robots || ''} onChange={(e) => setDraft({ ...draft, seo: { ...(draft.seo || {}), robots: e.target.value } })} placeholder="index,follow" /></Field>
                </div>
              </CardBody>
            </Card>
          ) : null}

          {rightTab === 'cms' ? (
            <Card>
              <CardHeader title="CMS meta" subtitle="Параметри автора, теги, cover" />
              <CardBody className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label="Title"><Input value={draft.title || ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></Field>
                  <Field label="Slug"><Input value={draft.slug || ''} onChange={(e) => setDraft({ ...draft, slug: e.target.value })} /></Field>
                  <Field className="md:col-span-2" label="Summary"><Textarea rows={2} value={draft.summary || ''} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} /></Field>
                  <Field label="Kind"><Select value={draft.kind || 'page'} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
                    <option value="page">page</option><option value="service">service</option>
                    <option value="industry">industry</option><option value="landing">landing</option>
                    <option value="blog">blog</option><option value="waste_code">waste_code</option>
                  </Select></Field>
                  <Field label="Category"><Input value={draft.cms?.category || ''} onChange={(e) => setDraft({ ...draft, cms: { ...(draft.cms || {}), category: e.target.value } })} /></Field>
                  <Field className="md:col-span-2" label="Cover image URL"><Input value={draft.cms?.cover_image_url || ''} onChange={(e) => setDraft({ ...draft, cms: { ...(draft.cms || {}), cover_image_url: e.target.value } })} /></Field>
                </div>
                <p className="text-[11.5px] text-[#71717A]">Автор / експерт (EEAT) буде додано в Phase D3.</p>
              </CardBody>
            </Card>
          ) : null}

          {rightTab === 'block' && !selectedBlock ? (
            <Card><CardBody>
              <div className="text-[13px] text-[#71717A] py-8 text-center">Оберіть блок або додайте новий з палітри.</div>
            </CardBody></Card>
          ) : null}
        </div>
      </div>

      {/* Phase D1.5 — Universal Timeline (comments · files · changes · events) */}
      {pageId && (
        <div className="mt-4">
          <UniversalTimeline entityType="content_page" entityId={pageId} title="Історія сторінки" />
        </div>
      )}

      {showHistory ? (
        <VersionHistoryPanel
          pageId={pageId}
          onClose={() => setShowHistory(false)}
          onRestored={() => { setShowHistory(false); load(); }}
        />
      ) : null}
    </div>
  );
}

function TransitionButton({ status, onGo }) {
  const [open, setOpen] = useState(false);
  const options = [
    { s: 'draft',     l: 'В чернетку' },
    { s: 'review',    l: 'На рев’ю' },
    { s: 'published', l: 'Опублікувати' },
    { s: 'archived',  l: 'Архівувати' },
  ].filter((o) => o.s !== status);
  return (
    <div className="relative">
      <Button variant="secondary" size="sm" onClick={() => setOpen(!open)} data-testid="editor-transition">
        Змінити статус
      </Button>
      {open ? (
        <>
          <button className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-9 z-50 min-w-[180px] rounded-lg border border-[#E4E4E7] bg-white shadow-lg py-1">
            {options.map((o) => (
              <button
                key={o.s}
                onClick={() => { setOpen(false); onGo(o.s); }}
                data-testid={`editor-transition-${o.s}`}
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
