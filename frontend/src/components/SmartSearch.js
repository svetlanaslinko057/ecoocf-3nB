import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, ArrowRight, FileText, Loader2 } from "lucide-react";
import { WasteAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { HazardBadge } from "@/components/common";
import { RequestDialog } from "@/components/RequestDialog";

export function SmartSearch({ size = "lg" }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [openList, setOpenList] = useState(false);
  const [dialog, setDialog] = useState({ open: false, code: "", name: "" });
  const navigate = useNavigate();
  const boxRef = useRef(null);
  const tmr = useRef(null);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpenList(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (tmr.current) clearTimeout(tmr.current);
    if (!q.trim()) { setItems([]); return; }
    setLoading(true);
    tmr.current = setTimeout(async () => {
      try {
        const res = await WasteAPI.search(q.trim(), 8);
        setItems(res.items || []);
        setOpenList(true);
      } catch { setItems([]); }
      finally { setLoading(false); }
    }, 250);
    return () => tmr.current && clearTimeout(tmr.current);
  }, [q]);

  const h = size === "lg" ? "h-14 text-base" : "h-12 text-sm";
  return (
    <div className="relative w-full" ref={boxRef}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => items.length && setOpenList(true)}
          placeholder="Напр., ртутні лампи, батарейки, медичні відходи…"
          className={`w-full rounded-2xl border border-[hsl(var(--border))] bg-white pl-12 pr-12 ${h} shadow-sm outline-none ring-0 transition-shadow focus:border-[hsl(var(--ring))] focus:ring-2 focus:ring-[hsl(var(--ring))]/30`}
          data-testid="smart-search-input"
        />
        {loading && <Loader2 className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-slate-400" />}
      </div>
      {openList && items.length > 0 && (
        <div className="absolute z-30 mt-2 max-h-[380px] w-full overflow-auto rounded-2xl border border-[hsl(var(--border))] bg-white p-2 shadow-xl">
          {items.map((it) => (
            <div key={it.code} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 hover:bg-[hsl(var(--secondary))]/60" data-testid="smart-search-result-item">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-[hsl(var(--primary))]">{it.code}</span>
                  <HazardBadge hazardous={it.hazardous} />
                </div>
                <div className="truncate text-xs text-slate-500">{it.name}</div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button size="sm" variant="ghost" onClick={() => navigate(`/waste-code/${it.slug}`)} title="Сторінка коду"><FileText className="h-4 w-4" /></Button>
                <Button size="sm" onClick={() => setDialog({ open: true, code: it.code, name: it.name })} data-testid="smart-search-create-request-button">Заявка <ArrowRight className="ml-1 h-4 w-4" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {openList && !loading && q.trim() && items.length === 0 && (
        <div className="absolute z-30 mt-2 w-full rounded-2xl border border-[hsl(var(--border))] bg-white p-4 text-sm text-slate-500 shadow-xl">
          Нічого не знайдено. <button className="font-medium text-[hsl(var(--primary))] underline" onClick={() => setDialog({ open: true, code: q, name: q })}>Створити заявку вручну</button>
        </div>
      )}
      <RequestDialog open={dialog.open} onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))} prefillCode={dialog.code} prefillName={dialog.name} />
    </div>
  );
}
