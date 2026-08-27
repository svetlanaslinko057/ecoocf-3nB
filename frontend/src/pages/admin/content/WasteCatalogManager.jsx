/**
 * WasteCatalogManager — Content Center → «Каталог відходів».
 *
 * Fully manages the public catalog block (category cards on /waste and the
 * homepage): create / edit / delete categories, pick an icon, upload a cover
 * photo, set UA + EN names and descriptions, drag-to-reorder, toggle
 * visibility and assign which waste codes belong to each category.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import {
  Plus, PencilSimple, Trash, X, ArrowClockwise, MagnifyingGlass,
  SquaresFour, Check, DotsSixVertical, UploadSimple, Image as ImageIcon,
} from '@phosphor-icons/react';
import { WasteCategoryAdminAPI, mediaUrl } from '@/lib/api';
import { iconByName, ICON_KEYS } from '@/lib/wasteMeta';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Button, Toggle, Skeleton } from '../seo/_shared';

const EMPTY_CAT = {
  key: '', name_uk: '', name_en: '', icon: 'shield-alert',
  desc_uk: '', desc_en: '', image_url: '',
  synonyms: [], order: null, active: true, codes: [],
};

export default function WasteCatalogManager() {
  const [loading, setLoading] = useState(true);
  const [cats, setCats] = useState([]);
  const [allCodes, setAllCodes] = useState([]);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, c] = await Promise.all([
        WasteCategoryAdminAPI.list(),
        WasteCategoryAdminAPI.allCodes(),
      ]);
      setCats(r.categories || []);
      setAllCodes(c.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || 'Помилка завантаження');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openNew = () => setEditing({ ...EMPTY_CAT, synonyms: [], codes: [] });
  const openEdit = (cat) => setEditing({
    ...EMPTY_CAT,
    ...cat,
    synonyms: Array.isArray(cat.synonyms) ? cat.synonyms : [],
    codes: Array.isArray(cat.codes) ? cat.codes : [],
  });

  const doSave = async (draft) => {
    if (!draft.name_uk?.trim() && !draft.name_en?.trim()) {
      toast.error('Вкажіть назву (UA або EN)');
      return;
    }
    setSaving(true);
    try {
      const body = {
        name_uk: draft.name_uk?.trim() || '',
        name_en: draft.name_en?.trim() || '',
        icon: draft.icon || 'shield-alert',
        desc_uk: draft.desc_uk || '',
        desc_en: draft.desc_en || '',
        image_url: draft.image_url || '',
        synonyms: draft.synonyms || [],
        active: !!draft.active,
        codes: draft.codes || [],
      };
      if (draft.order !== null && draft.order !== '' && draft.order !== undefined) {
        body.order = Number(draft.order);
      }
      if (draft.key) {
        await WasteCategoryAdminAPI.update(draft.key, body);
      } else {
        await WasteCategoryAdminAPI.create(body);
      }
      toast.success('Категорію збережено');
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || 'Не вдалося зберегти');
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async (cat) => {
    if (!window.confirm(`Видалити категорію «${cat.name_uk || cat.name_en}»?\nКоди залишаться в довіднику, але стануть без категорії.`)) return;
    try {
      await WasteCategoryAdminAPI.remove(cat.key);
      toast.success('Категорію видалено');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || 'Не вдалося видалити');
    }
  };

  const onDragEnd = async (result) => {
    if (!result.destination || result.destination.index === result.source.index) return;
    const next = Array.from(cats);
    const [moved] = next.splice(result.source.index, 1);
    next.splice(result.destination.index, 0, moved);
    setCats(next.map((c, i) => ({ ...c, order: i + 1 })));
    try {
      await WasteCategoryAdminAPI.reorder(next.map((c) => c.key));
    } catch (e) {
      toast.error('Не вдалося змінити порядок');
      load();
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Каталог відходів"
          subtitle="Категорії публічного каталогу: іконка, обкладинка, назви + описи (UA/EN) та прикріплені коди. Перетягуйте, щоб змінити порядок."
          icon={SquaresFour}
          right={
            <Button variant="primary" onClick={openNew} data-testid="catalog-create">
              <Plus size={13} weight="bold" /> Нова категорія
            </Button>
          }
        />
        <CardBody>
          {loading ? <Skeleton /> : cats.length === 0 ? (
            <div className="py-16 text-center text-[13px] text-[#71717A]">Ще немає категорій</div>
          ) : (
            <DragDropContext onDragEnd={onDragEnd}>
              <Droppable droppableId="catalog-cats">
                {(dp) => (
                  <div ref={dp.innerRef} {...dp.droppableProps} className="space-y-2" data-testid="catalog-list">
                    {cats.map((cat, idx) => {
                      const Icon = iconByName(cat.icon);
                      const cover = mediaUrl(cat.image_url);
                      return (
                        <Draggable key={cat.key} draggableId={cat.key} index={idx}>
                          {(dr, snap) => (
                            <div
                              ref={dr.innerRef}
                              {...dr.draggableProps}
                              data-testid={`catalog-card-${cat.key}`}
                              className={`rounded-xl border bg-white p-2.5 flex items-center gap-3 transition ${snap.isDragging ? 'border-emerald-400 shadow-lg' : 'border-[#E4E4E7] hover:border-emerald-300'}`}
                            >
                              <button
                                {...dr.dragHandleProps}
                                className="shrink-0 h-8 w-6 inline-flex items-center justify-center text-[#A1A1AA] hover:text-emerald-600 cursor-grab active:cursor-grabbing"
                                title="Перетягнути"
                                data-testid={`catalog-drag-${cat.key}`}
                              >
                                <DotsSixVertical size={16} weight="bold" />
                              </button>

                              {cover ? (
                                <img src={cover} alt="" className="shrink-0 h-12 w-12 rounded-lg object-cover border border-[#E4E4E7]" />
                              ) : (
                                <span className="shrink-0 h-12 w-12 rounded-lg bg-emerald-50 border border-emerald-100 inline-flex items-center justify-center text-emerald-700">
                                  <Icon size={22} />
                                </span>
                              )}

                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-[14px] font-semibold text-[#18181B] truncate">{cat.name_uk || cat.name_en}</span>
                                  {!cat.active && <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-50 text-rose-700 border border-rose-200">прих.</span>}
                                </div>
                                <div className="text-[12px] text-[#71717A] truncate">{cat.name_en || '—'} · <span className="font-mono text-[#A1A1AA]">{cat.key}</span></div>
                              </div>

                              <div className="hidden sm:flex items-center gap-1.5 text-[11.5px] shrink-0">
                                <span className="px-2 py-0.5 rounded-full bg-[#F4F4F5] text-[#3F3F46]">{cat.count} код.</span>
                                {cat.hazardous_count > 0 && (
                                  <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">{cat.hazardous_count} небезп.</span>
                                )}
                                <span className="px-2 py-0.5 rounded-full bg-[#F4F4F5] text-[#71717A] font-mono">#{cat.order}</span>
                              </div>

                              <div className="flex items-center gap-1 shrink-0">
                                <button onClick={() => openEdit(cat)} className="h-8 px-2.5 rounded-md hover:bg-emerald-50 text-emerald-700 inline-flex items-center gap-1 text-[12px] font-medium" data-testid={`catalog-edit-${cat.key}`}>
                                  <PencilSimple size={13} weight="bold" /> <span className="hidden md:inline">Редагувати</span>
                                </button>
                                <button onClick={() => doDelete(cat)} className="h-8 w-8 rounded-md hover:bg-rose-50 text-rose-600 inline-flex items-center justify-center" data-testid={`catalog-delete-${cat.key}`}>
                                  <Trash size={13} weight="bold" />
                                </button>
                              </div>
                            </div>
                          )}
                        </Draggable>
                      );
                    })}
                    {dp.placeholder}
                  </div>
                )}
              </Droppable>
            </DragDropContext>
          )}

          <div className="mt-4 flex items-center justify-between text-[11.5px] text-[#71717A]">
            <div>Категорій: <strong>{cats.length}</strong></div>
            <button onClick={load} className="inline-flex items-center gap-1 hover:text-emerald-700">
              <ArrowClockwise size={11} weight="bold" /> Оновити
            </button>
          </div>
        </CardBody>
      </Card>

      {editing ? (
        <CategoryEditModal
          initial={editing}
          allCodes={allCodes}
          saving={saving}
          onSave={doSave}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}

function CategoryEditModal({ initial, allCodes, saving, onSave, onClose }) {
  const [draft, setDraft] = useState(initial);
  const [codeQuery, setCodeQuery] = useState('');
  const [hazOnly, setHazOnly] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));

  const selected = useMemo(() => new Set(draft.codes || []), [draft.codes]);
  const toggleCode = (code) => {
    const next = new Set(selected);
    next.has(code) ? next.delete(code) : next.add(code);
    set({ codes: Array.from(next) });
  };

  const filteredCodes = useMemo(() => {
    const q = codeQuery.trim().toLowerCase();
    return (allCodes || []).filter((c) => {
      if (hazOnly && !c.hazardous) return false;
      if (!q) return true;
      return (c.code || '').toLowerCase().includes(q) || (c.name || '').toLowerCase().includes(q);
    }).slice(0, 400);
  }, [allCodes, codeQuery, hazOnly]);

  const onPickFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const r = await WasteCategoryAdminAPI.uploadImage(file);
      set({ image_url: r?.asset?.url || '' });
      toast.success('Обкладинку завантажено');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Не вдалося завантажити зображення');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const PreviewIcon = iconByName(draft.icon);
  const cover = mediaUrl(draft.image_url);

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-4xl bg-white rounded-2xl border border-[#E4E4E7] flex flex-col max-h-[92vh]" data-testid="catalog-modal">
        <header className="flex items-center gap-3 px-5 py-3.5 border-b border-[#E4E4E7]">
          <span className="h-9 w-9 rounded-lg bg-emerald-50 border border-emerald-100 inline-flex items-center justify-center text-emerald-700">
            <PreviewIcon size={18} />
          </span>
          <h3 className="flex-1 text-[15px] font-semibold text-[#18181B]">{initial.key ? 'Редагувати категорію' : 'Нова категорія'}</h3>
          <button onClick={onClose} className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center"><X size={15} weight="bold" /></button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── Left: meta ── */}
          <div className="space-y-4 min-w-0">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Назва (українською)" required>
                <Input value={draft.name_uk} onChange={(e) => set({ name_uk: e.target.value })} placeholder="Медичні відходи" data-testid="catalog-name-uk" />
              </Field>
              <Field label="Назва (English)" required>
                <Input value={draft.name_en} onChange={(e) => set({ name_en: e.target.value })} placeholder="Medical waste" data-testid="catalog-name-en" />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <Field label="Опис (українською)" hint="Показується клієнту на сторінці категорії">
                <Textarea rows={2} value={draft.desc_uk} onChange={(e) => set({ desc_uk: e.target.value })} placeholder="Що належить до цієї категорії, як здавати…" data-testid="catalog-desc-uk" />
              </Field>
              <Field label="Опис (English)">
                <Textarea rows={2} value={draft.desc_en} onChange={(e) => set({ desc_en: e.target.value })} placeholder="What belongs here, how to hand over…" data-testid="catalog-desc-en" />
              </Field>
            </div>

            <Field label="Обкладинка категорії" hint="Фото показується на картці каталогу та у шапці сторінки категорії">
              <div className="flex items-center gap-3">
                <div className="shrink-0 h-16 w-16 rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] overflow-hidden inline-flex items-center justify-center text-[#A1A1AA]">
                  {cover ? <img src={cover} alt="" className="h-full w-full object-cover" /> : <ImageIcon size={22} />}
                </div>
                <div className="flex items-center gap-2">
                  <input ref={fileRef} type="file" accept="image/*" onChange={onPickFile} className="hidden" data-testid="catalog-image-input" />
                  <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()} disabled={uploading} data-testid="catalog-image-upload">
                    <UploadSimple size={13} weight="bold" /> {uploading ? 'Завантаження…' : (cover ? 'Замінити' : 'Завантажити')}
                  </Button>
                  {cover ? (
                    <Button variant="danger" size="sm" onClick={() => set({ image_url: '' })}>Прибрати</Button>
                  ) : null}
                </div>
              </div>
            </Field>

            <Field label="Іконка" hint="Показується, коли немає обкладинки">
              <div className="rounded-xl border border-[#E4E4E7] p-2.5 grid grid-cols-8 gap-1.5 max-h-[140px] overflow-y-auto" data-testid="catalog-icon-grid">
                {ICON_KEYS.map((name) => {
                  const IcoC = iconByName(name);
                  const active = draft.icon === name;
                  return (
                    <button
                      key={name}
                      type="button"
                      title={name}
                      onClick={() => set({ icon: name })}
                      data-testid={`catalog-icon-${name}`}
                      className={`aspect-square rounded-lg inline-flex items-center justify-center border transition ${active ? 'bg-emerald-600 border-emerald-600 text-white' : 'bg-white border-[#E4E4E7] text-[#52525B] hover:border-emerald-300 hover:text-emerald-700'}`}
                    >
                      <IcoC size={18} />
                    </button>
                  );
                })}
              </div>
            </Field>

            <div className="grid grid-cols-2 gap-3 items-end">
              <Field label="Порядок" hint="Або перетягніть у списку">
                <Input type="number" value={draft.order ?? ''} onChange={(e) => set({ order: e.target.value })} placeholder="авто" data-testid="catalog-order" />
              </Field>
              <div className="pb-1.5">
                <Toggle checked={draft.active} onChange={(v) => set({ active: v })} label="Показувати на сайті" dataTestid="catalog-active" />
              </div>
            </div>

            <Field label="Синоніми (через кому)" hint="Використовуються для пошуку у довіднику">
              <Input
                value={(draft.synonyms || []).join(', ')}
                onChange={(e) => set({ synonyms: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                placeholder="медицина, лікарня, клініка"
                data-testid="catalog-synonyms"
              />
            </Field>

            {initial.key ? <div className="text-[11px] text-[#A1A1AA] font-mono">key: {initial.key}</div> : null}
          </div>

          {/* ── Right: code assignment ── */}
          <div className="flex flex-col min-h-0 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[12px] font-medium text-[#3F3F46]">Коди відходів у категорії</div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11.5px] font-semibold" data-testid="catalog-selected-count">
                обрано: {selected.size}
              </span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <div className="relative flex-1">
                <MagnifyingGlass size={13} weight="bold" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
                <Input className="pl-8" value={codeQuery} onChange={(e) => setCodeQuery(e.target.value)} placeholder="Пошук за кодом або назвою…" data-testid="catalog-code-search" />
              </div>
              <label className="inline-flex items-center gap-1.5 text-[12px] text-[#3F3F46] cursor-pointer select-none whitespace-nowrap">
                <input type="checkbox" checked={hazOnly} onChange={(e) => setHazOnly(e.target.checked)} className="accent-emerald-600" />
                небезпечні
              </label>
            </div>
            <div className="flex-1 min-h-[220px] max-h-[420px] overflow-y-auto rounded-xl border border-[#E4E4E7] divide-y divide-[#F4F4F5]" data-testid="catalog-code-list">
              {filteredCodes.length === 0 ? (
                <div className="py-12 text-center text-[12px] text-[#A1A1AA]">Нічого не знайдено</div>
              ) : filteredCodes.map((c) => {
                const on = selected.has(c.code);
                return (
                  <button
                    key={c.code}
                    type="button"
                    onClick={() => toggleCode(c.code)}
                    data-testid={`catalog-code-${c.code}`}
                    className={`w-full text-left px-3 py-2 flex items-center gap-2.5 min-w-0 transition ${on ? 'bg-emerald-50/60' : 'hover:bg-[#FAFAFA]'}`}
                  >
                    <span className={`shrink-0 rounded border inline-flex items-center justify-center ${on ? 'bg-emerald-600 border-emerald-600 text-white' : 'border-[#D4D4D8] text-transparent'}`} style={{ height: 18, width: 18 }}>
                      <Check size={12} weight="bold" />
                    </span>
                    <span className="font-mono text-[12.5px] text-[#18181B] shrink-0">{c.code}</span>
                    {c.hazardous ? <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-amber-800 border border-amber-200">небезп.</span> : null}
                    <span className="text-[12px] text-[#52525B] truncate">{c.name}</span>
                  </button>
                );
              })}
            </div>
            <div className="mt-1.5 text-[11px] text-[#A1A1AA]">Показано до 400 кодів. Уточніть пошук, якщо не бачите потрібний.</div>
          </div>
        </div>

        <footer className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[#E4E4E7]">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Скасувати</Button>
          <Button variant="primary" onClick={() => onSave(draft)} disabled={saving} data-testid="catalog-modal-save">
            {saving ? 'Збереження…' : 'Зберегти'}
          </Button>
        </footer>
      </div>
    </div>
  );
}
