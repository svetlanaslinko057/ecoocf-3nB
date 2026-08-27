// MediaPickerDialog — Phase D1.5 (Universal Media Picker).
// A single, reusable media browser + uploader that ANY editor can open to pick
// an asset from the shared Media Library (`/api/admin/media`). Additive: it does
// not replace the standalone Media Library page — it wraps the same API.
//
// Usage:
//   const [open, setOpen] = useState(false);
//   <MediaPickerDialog open={open} onClose={() => setOpen(false)}
//                      onSelect={(asset) => setImage(asset.url)} />
import React, { useCallback, useEffect, useRef, useState } from "react";
import { X, Upload, Search, ImageOff, Check, Loader2 } from "lucide-react";
import { contentApi, BACKEND_URL } from "@/pages/admin/content/contentApi";

const mediaSrc = (url) => (url && url.startsWith("http") ? url : `${BACKEND_URL}${url || ""}`);

export default function MediaPickerDialog({ open, onClose, onSelect, accept = "image/*" }) {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  const load = useCallback(async (query = "") => {
    setLoading(true); setError("");
    try {
      const data = await contentApi.listMedia(query ? { q: query } : {});
      setItems(data.items || []);
    } catch (e) {
      setError(e.message || "Помилка завантаження");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) { setSelected(null); setQ(""); load(""); }
  }, [open, load]);

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const res = await contentApi.uploadMedia(file);
      if (res?.asset) { setItems((prev) => [res.asset, ...prev]); setSelected(res.asset); }
    } catch (err) {
      setError(err.message || "Помилка завантаження файлу");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const confirm = () => { if (selected) { onSelect?.(selected); onClose?.(); } };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
         onClick={onClose} data-testid="media-picker-overlay">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
           onClick={(e) => e.stopPropagation()} data-testid="media-picker">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h3 className="text-base font-semibold text-slate-800">Медіа-бібліотека</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700" aria-label="Закрити">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-slate-200 px-3 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(q)}
              placeholder="Пошук за назвою / тегом…"
              className="w-full bg-transparent text-sm outline-none"
              data-testid="media-picker-search"
            />
          </div>
          <button type="button" onClick={() => load(q)} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">Шукати</button>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-xl bg-[#0E5E3A] px-3 py-2 text-sm font-medium text-white hover:bg-[#0b4d30] disabled:opacity-60"
            data-testid="media-picker-upload-btn"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Завантажити
          </button>
          <input ref={fileRef} type="file" accept={accept} className="hidden" onChange={onUpload} data-testid="media-picker-file-input" />
        </div>

        {error && <div className="mx-5 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

        {/* Grid */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex h-40 items-center justify-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : items.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-slate-400">
              <ImageOff className="h-8 w-8" />
              <span className="text-sm">Бібліотека порожня — завантажте перший файл</span>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4" data-testid="media-picker-grid">
              {items.map((a) => {
                const isSel = selected?.id === a.id;
                const isImg = (a.mime || "").startsWith("image/");
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setSelected(a)}
                    onDoubleClick={() => { onSelect?.(a); onClose?.(); }}
                    className={`group relative overflow-hidden rounded-xl border-2 transition-all ${isSel ? "border-[#0E5E3A] ring-2 ring-[#5BC47A]/30" : "border-slate-100 hover:border-slate-300"}`}
                    data-testid="media-picker-item"
                  >
                    <div className="flex aspect-square items-center justify-center bg-slate-50">
                      {isImg ? (
                        <img src={mediaSrc(a.url)} alt={a.alt || a.filename} className="h-full w-full object-cover" loading="lazy" />
                      ) : (
                        <span className="px-2 text-center text-[11px] text-slate-400">{a.filename}</span>
                      )}
                    </div>
                    {isSel && (
                      <span className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[#0E5E3A] text-white">
                        <Check className="h-3.5 w-3.5" />
                      </span>
                    )}
                    <div className="truncate px-2 py-1 text-left text-[11px] text-slate-500">{a.filename}</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
          <span className="text-xs text-slate-400">{selected ? `Вибрано: ${selected.filename}` : "Оберіть файл або двічі клікніть"}</span>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">Скасувати</button>
            <button
              type="button"
              onClick={confirm}
              disabled={!selected}
              className="rounded-xl bg-[#0E5E3A] px-4 py-2 text-sm font-medium text-white hover:bg-[#0b4d30] disabled:opacity-50"
              data-testid="media-picker-confirm"
            >
              Обрати
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
