/**
 * MediaLibrary — Phase D1.
 *
 * Grid view of uploaded images/PDFs. Upload via drag-and-drop OR file input.
 * Click an asset to edit alt/caption/tags/focus point. Copy URL for pasting
 * into block editors.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  UploadSimple, MagnifyingGlass, Copy, Trash, FileText, X, ArrowClockwise,
} from '@phosphor-icons/react';
import { contentApi, BACKEND_URL } from './contentApi';
import { Card, CardHeader, CardBody, Field, Input, Textarea, Button, Skeleton } from '../seo/_shared';

export default function MediaLibrary() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await contentApi.listMedia(q ? { q } : {});
      setItems(r.items || []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => { load(); }, [load]);

  const doUpload = async (file) => {
    setUploading(true);
    try {
      const r = await contentApi.uploadMedia(file);
      toast.success('Завантажено');
      setItems([r.asset, ...items]);
      setSelected(r.asset);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const doDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const f = e.dataTransfer.files?.[0];
    if (f) doUpload(f);
  };

  const doDelete = async (asset) => {
    if (!window.confirm(`Видалити ${asset.filename}?`)) return;
    try {
      await contentApi.deleteMedia(asset.id);
      setItems(items.filter((a) => a.id !== asset.id));
      if (selected?.id === asset.id) setSelected(null);
      toast.success('Видалено');
    } catch (e) {
      toast.error(e.message);
    }
  };

  const doSaveMeta = async (patch) => {
    if (!selected) return;
    try {
      const r = await contentApi.updateMedia(selected.id, patch);
      setItems(items.map((a) => (a.id === selected.id ? r.asset : a)));
      setSelected(r.asset);
      toast.success('Збережено');
    } catch (e) {
      toast.error(e.message);
    }
  };

  const copyUrl = (url) => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(`${BACKEND_URL}${url}`).then(
      () => toast.success('URL скопійовано'),
      () => toast.error('Не вдалося…')
    );
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Медіа-бібліотека"
          subtitle="Зображення та PDF, доступні через CDN-подібний ендпойнт /api/media/{id}"
          icon={UploadSimple}
          right={
            <div className="flex items-center gap-2">
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="пошук" className="w-40" data-testid="media-search" />
              <input ref={fileRef} type="file" accept="image/*,application/pdf" onChange={(e) => e.target.files?.[0] && doUpload(e.target.files[0])} className="hidden" data-testid="media-file-input" />
              <Button variant="primary" onClick={() => fileRef.current?.click()} disabled={uploading} data-testid="media-upload-btn">
                <UploadSimple size={13} weight="bold" /> {uploading ? 'Завантаження…' : 'Завантажити'}
              </Button>
            </div>
          }
        />
        <CardBody
          onDragOver={(e) => e.preventDefault()}
          onDrop={doDrop}
        >
          {loading ? <Skeleton /> : items.length === 0 ? (
            <div className="py-16 text-center text-[13px] text-[#71717A] border-2 border-dashed border-[#E4E4E7] rounded-xl">
              Порожньо. Перетягніть файл або натисніть &laquo;Завантажити&raquo;.
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {items.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setSelected(a)}
                  data-testid={`media-item-${a.id}`}
                  className={`text-left rounded-xl border overflow-hidden transition ${selected?.id === a.id ? 'border-emerald-500 ring-2 ring-emerald-200' : 'border-[#E4E4E7] hover:border-emerald-300'}`}
                >
                  <div className="aspect-video bg-[#F4F4F5] flex items-center justify-center overflow-hidden">
                    {a.mime?.startsWith('image/') ? (
                      <img src={`${BACKEND_URL}${a.url}`} alt={a.alt || a.filename} className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <FileText size={30} className="text-[#71717A]" />
                    )}
                  </div>
                  <div className="p-2">
                    <div className="text-[11.5px] font-medium text-[#18181B] truncate">{a.filename}</div>
                    <div className="text-[10.5px] text-[#71717A]">{a.width && a.height ? `${a.width}×${a.height}` : a.mime} · {(a.size / 1024).toFixed(0)} kB</div>
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="mt-3 flex items-center justify-between text-[11.5px] text-[#71717A]">
            <div>Асетів: <strong>{items.length}</strong></div>
            <button onClick={load} className="inline-flex items-center gap-1 hover:text-emerald-700">
              <ArrowClockwise size={11} weight="bold" /> Оновити
            </button>
          </div>
        </CardBody>
      </Card>

      {selected ? (
        <MediaDetail
          asset={selected}
          onClose={() => setSelected(null)}
          onSave={doSaveMeta}
          onDelete={() => doDelete(selected)}
          onCopy={() => copyUrl(selected.url)}
        />
      ) : null}
    </div>
  );
}

function MediaDetail({ asset, onClose, onSave, onDelete, onCopy }) {
  const [draft, setDraft] = useState(asset);
  useEffect(() => { setDraft(asset); }, [asset.id]);

  const patch = (p) => setDraft({ ...draft, ...p });

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-stretch justify-end" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-[520px] h-full bg-white flex flex-col border-l border-[#E4E4E7]">
        <header className="flex items-center gap-2 px-4 py-3 border-b border-[#E4E4E7]">
          <h3 className="flex-1 text-[14px] font-semibold truncate">{asset.filename}</h3>
          <button onClick={onCopy} className="h-8 px-2 rounded-md hover:bg-[#F4F4F5] text-[12px] inline-flex items-center gap-1 text-emerald-700">
            <Copy size={12} weight="bold" /> URL
          </button>
          <button onClick={onClose} className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center">
            <X size={14} weight="bold" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {asset.mime?.startsWith('image/') ? (
            <img src={`${BACKEND_URL}${asset.url}`} alt={draft.alt || draft.filename} className="w-full rounded-lg border border-[#E4E4E7]" />
          ) : null}
          <Field label="Alt text" required><Input value={draft.alt || ''} onChange={(e) => patch({ alt: e.target.value })} /></Field>
          <Field label="Caption"><Textarea rows={2} value={draft.caption || ''} onChange={(e) => patch({ caption: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Author"><Input value={draft.author || ''} onChange={(e) => patch({ author: e.target.value })} /></Field>
            <Field label="Copyright"><Input value={draft.copyright || ''} onChange={(e) => patch({ copyright: e.target.value })} /></Field>
            <Field label="Focus X (%)"><Input type="number" value={draft.focus_x ?? 50} min={0} max={100} onChange={(e) => patch({ focus_x: +e.target.value })} /></Field>
            <Field label="Focus Y (%)"><Input type="number" value={draft.focus_y ?? 50} min={0} max={100} onChange={(e) => patch({ focus_y: +e.target.value })} /></Field>
          </div>
          <Field label="Tags" hint="вводить через кому">
            <Input
              value={(draft.tags || []).join(', ')}
              onChange={(e) => patch({ tags: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
            />
          </Field>
          <div className="text-[11px] text-[#71717A]">
            URL: <code>{BACKEND_URL}{asset.url}</code>
          </div>
        </div>
        <footer className="flex items-center gap-2 px-4 py-3 border-t border-[#E4E4E7]">
          <Button variant="danger" onClick={onDelete}><Trash size={12} weight="bold" /> Видалити</Button>
          <div className="flex-1" />
          <Button variant="primary" onClick={() => onSave({
            alt: draft.alt, caption: draft.caption, author: draft.author, copyright: draft.copyright,
            focus_x: draft.focus_x, focus_y: draft.focus_y, tags: draft.tags,
          })} data-testid="media-detail-save">
            Зберегти
          </Button>
        </footer>
      </div>
    </div>
  );
}
