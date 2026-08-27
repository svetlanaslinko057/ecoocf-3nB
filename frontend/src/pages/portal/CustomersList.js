import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Users, FileArchive, Loader2, CheckSquare } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/sonner";
import CustomerLabel from "@/components/portal/CustomerLabel";

function fmtDate(v) {
  if (!v) return "—";
  try { return new Date(v).toLocaleDateString("uk-UA"); } catch { return String(v).slice(0, 10); }
}

export default function CustomersList() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(() => new Set());
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async (query) => {
    setItems(null);
    try {
      const r = await api.get("/customers", { params: { q: query || "", limit: 100 } });
      const list = r.data?.items || r.data?.data || [];
      setItems(list);
      setTotal(r.data?.total ?? list.length);
    } catch (e) {
      setItems([]);
      toast.error("Не вдалося завантажити клієнтів");
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(q), 300);
    return () => clearTimeout(t);
  }, [q, load]);

  const toggle = (id) => setSelected((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const pageIds = useMemo(() => (items || []).map((c) => c.id), [items]);
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const toggleAll = () => setSelected((prev) => {
    const next = new Set(prev);
    if (allOnPageSelected) pageIds.forEach((id) => next.delete(id));
    else pageIds.forEach((id) => next.add(id));
    return next;
  });

  const exportSelected = async () => {
    const ids = Array.from(selected);
    if (!ids.length) return;
    setExporting(true);
    try {
      const r = await api.post("/customers/cards.zip", { customer_ids: ids }, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/zip" }));
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
      a.href = url; a.download = `customer-cards-${stamp}.zip`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      const exported = r.headers?.["x-exported-count"];
      toast.success(`Експортовано карток: ${exported || ids.length} (ZIP)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося сформувати архів");
    } finally { setExporting(false); }
  };

  return (
    <div data-testid="portal-customers-list">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><Users className="h-6 w-6 text-emerald-600" /> Клієнти</h1>
          <p className="text-sm text-slate-500">Наскрізний реєстр клієнтів. Оберіть кількох, щоб вивантажити картки одним ZIP-архівом.</p>
        </div>
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Пошук: email, компанія, ім'я, телефон…"
            className="pl-9"
            data-testid="customers-search"
          />
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="mb-3 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5" data-testid="customers-bulk-bar">
          <div className="flex items-center gap-2 text-sm font-medium text-emerald-800">
            <CheckSquare className="h-4 w-4" /> Обрано: {selected.size}
            <button className="ml-2 text-xs font-normal text-emerald-700 underline" onClick={() => setSelected(new Set())} data-testid="customers-clear-sel">скинути</button>
          </div>
          <Button size="sm" className="gap-1.5" onClick={exportSelected} disabled={exporting} data-testid="customers-bulk-export">
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileArchive className="h-4 w-4" />}
            {exporting ? "Формуємо ZIP…" : `Експортувати обрані (${selected.size}) — ZIP`}
          </Button>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox checked={allOnPageSelected} onCheckedChange={toggleAll} aria-label="Обрати всіх" data-testid="customers-select-all" />
              </TableHead>
              <TableHead>Клієнт</TableHead>
              <TableHead>Компанія</TableHead>
              <TableHead>Телефон</TableHead>
              <TableHead>Створено</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items === null ? (
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}><TableCell colSpan={5}><div className="h-6 animate-pulse rounded bg-slate-100" /></TableCell></TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={5} className="py-10 text-center text-sm text-slate-400">Клієнтів не знайдено</TableCell></TableRow>
            ) : (
              items.map((c) => (
                <TableRow key={c.id} data-state={selected.has(c.id) ? "selected" : undefined} data-testid="customers-row" className="cursor-pointer" onClick={() => navigate(`/app/customers/${c.id}`)}>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox checked={selected.has(c.id)} onCheckedChange={() => toggle(c.id)} aria-label="Обрати клієнта" data-testid="customers-row-check" />
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}><CustomerLabel customer={c} /></TableCell>
                  <TableCell className="text-sm text-slate-600">{c.company_name || c.companyName || c.company || "—"}</TableCell>
                  <TableCell className="text-sm text-slate-600">{c.phone || "—"}</TableCell>
                  <TableCell className="text-sm text-slate-500">{fmtDate(c.created_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      {items !== null && (
        <div className="mt-2 text-xs text-slate-400">Показано {items.length} із {total}</div>
      )}
    </div>
  );
}
