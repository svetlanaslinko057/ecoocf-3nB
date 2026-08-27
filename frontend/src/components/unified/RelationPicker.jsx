// RelationPicker — Phase D1.5 (Universal Relation Picker).
// One reusable component to link any admin entity to another (related waste
// code, company, service/content page, FAQ, page…). Instead of typing IDs, the
// user searches and selects. Powered by UnifiedAPI.relations (read-only).
//
// Usage:
//   <RelationPicker open={open} type="waste_code" onClose={...}
//                   onSelect={(item) => setRelated(item)} />
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, Search, Loader2, Link2, Check } from "lucide-react";
import { UnifiedAPI } from "@/lib/api";

const DEFAULT_TYPES = [
  { type: "waste_code", label: "Код відходу" },
  { type: "company", label: "Компанія" },
  { type: "content_page", label: "Сторінка" },
  { type: "faq", label: "FAQ" },
  { type: "blog", label: "Стаття" },
  { type: "seo_page", label: "SEO-сторінка" },
];

export default function RelationPicker({
  open,
  onClose,
  onSelect,
  type: fixedType,          // if provided → locks the entity type
  allowedTypes,             // optional subset of types to offer
  title = "Обрати зв'язок",
}) {
  const typeOptions = useMemo(() => {
    if (fixedType) return DEFAULT_TYPES.filter((t) => t.type === fixedType);
    if (allowedTypes) return DEFAULT_TYPES.filter((t) => allowedTypes.includes(t.type));
    return DEFAULT_TYPES;
  }, [fixedType, allowedTypes]);

  const [activeType, setActiveType] = useState(fixedType || (typeOptions[0]?.type));
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const debounceRef = useRef(null);

  const load = useCallback(async (t, query) => {
    if (!t) return;
    setLoading(true);
    try {
      const data = await UnifiedAPI.relations(t, query || "", 30);
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) { setSelected(null); setQ(""); setActiveType(fixedType || typeOptions[0]?.type); }
  }, [open, fixedType, typeOptions]);

  useEffect(() => {
    if (!open || !activeType) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(activeType, q), 220);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [open, activeType, q, load]);

  const confirm = () => { if (selected) { onSelect?.({ ...selected, type: activeType }); onClose?.(); } };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
         onClick={onClose} data-testid="relation-picker-overlay">
      <div className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
           onClick={(e) => e.stopPropagation()} data-testid="relation-picker">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h3 className="flex items-center gap-2 text-base font-semibold text-slate-800"><Link2 className="h-4 w-4 text-[#0E5E3A]" />{title}</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700" aria-label="Закрити"><X className="h-5 w-5" /></button>
        </div>

        {/* Type tabs (hidden when a fixed type is enforced) */}
        {!fixedType && typeOptions.length > 1 && (
          <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-4 py-2.5" data-testid="relation-picker-types">
            {typeOptions.map((t) => (
              <button
                key={t.type}
                type="button"
                onClick={() => { setActiveType(t.type); setSelected(null); }}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${activeType === t.type ? "bg-[#0E5E3A] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {/* Search */}
        <div className="border-b border-slate-100 px-4 py-3">
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Почніть вводити для пошуку…"
              className="w-full bg-transparent text-sm outline-none"
              data-testid="relation-picker-search"
              autoFocus
            />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2" data-testid="relation-picker-list">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-slate-400"><Loader2 className="h-5 w-5 animate-spin" /></div>
          ) : items.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-slate-400">Нічого не знайдено</div>
          ) : (
            items.map((it) => {
              const isSel = selected?.id === it.id;
              return (
                <button
                  key={it.id}
                  type="button"
                  onClick={() => setSelected(it)}
                  onDoubleClick={() => { onSelect?.({ ...it, type: activeType }); onClose?.(); }}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${isSel ? "bg-[#F4FBEF]" : "hover:bg-slate-50"}`}
                  data-testid="relation-picker-item"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800">{it.title}</span>
                    <span className="block truncate text-[11px] text-slate-400">{it.subtitle}</span>
                  </span>
                  {isSel && <Check className="h-4 w-4 shrink-0 text-[#0E5E3A]" />}
                </button>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-5 py-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">Скасувати</button>
          <button
            type="button"
            onClick={confirm}
            disabled={!selected}
            className="rounded-xl bg-[#0E5E3A] px-4 py-2 text-sm font-medium text-white hover:bg-[#0b4d30] disabled:opacity-50"
            data-testid="relation-picker-confirm"
          >
            Прив'язати
          </button>
        </div>
      </div>
    </div>
  );
}
