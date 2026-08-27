import React, { useEffect, useRef, useState } from "react";
import { Search, Loader2, Plus, Trash2, ClipboardList } from "lucide-react";
import { WasteAPI, PortalAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { HazardBadge } from "@/components/common";

/**
 * Portal create-request dialog (authenticated). Posts to PortalAPI.createRequest.
 * @param company optional preset { id, name } — hides company picker.
 */
export function CreateRequestDialog({ open, onOpenChange, company = null, onCreated }) {
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(company?.id || "");
  const [objects, setObjects] = useState([]);
  const [objectId, setObjectId] = useState("");
  const [items, setItems] = useState([]);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [q, setQ] = useState("");
  const [opts, setOpts] = useState([]);
  const [searching, setSearching] = useState(false);
  const [openList, setOpenList] = useState(false);
  const boxRef = useRef(null);
  const tmr = useRef(null);

  useEffect(() => {
    if (open) {
      setCompanyId(company?.id || "");
      setItems([]); setComment(""); setObjectId(company?.objectId || ""); setQ("");
    }
  }, [open, company]);

  useEffect(() => {
    if (open && !company) {
      PortalAPI.companies({ limit: 300 }).then((r) => setCompanies(r.items || [])).catch(() => setCompanies([]));
    }
  }, [open, company]);

  useEffect(() => {
    if (companyId) {
      PortalAPI.objects({ company_id: companyId }).then((r) => setObjects(r.items || [])).catch(() => setObjects([]));
    } else {
      setObjects([]);
    }
  }, [companyId]);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpenList(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (tmr.current) clearTimeout(tmr.current);
    if (!q.trim()) { setOpts([]); return; }
    setSearching(true);
    tmr.current = setTimeout(async () => {
      try { const r = await WasteAPI.search(q.trim(), 8); setOpts(r.items || []); setOpenList(true); }
      catch { setOpts([]); } finally { setSearching(false); }
    }, 250);
    return () => tmr.current && clearTimeout(tmr.current);
  }, [q]);

  const addItem = (it) => {
    setItems((p) => (p.some((x) => x.waste_code === it.code) ? p : [...p, { waste_code: it.code, name: it.name, qty: "", hazardous: it.hazardous }]));
    setQ(""); setOpts([]); setOpenList(false);
  };
  const removeItem = (code) => setItems((p) => p.filter((x) => x.waste_code !== code));
  const setQty = (code, v) => setItems((p) => p.map((x) => (x.waste_code === code ? { ...x, qty: v } : x)));

  const submit = async () => {
    if (!companyId) return toast.error("Оберіть компанію");
    if (!items.length) return toast.error("Додайте хоча б один код відходу");
    setSubmitting(true);
    try {
      await PortalAPI.createRequest({
        company_id: companyId,
        object_id: objectId || null,
        comment,
        items: items.map((i) => ({ waste_code: i.waste_code, name: i.name, qty: i.qty ? Number(i.qty) : null })),
      });
      toast.success("Заявку створено");
      onOpenChange(false);
      onCreated && onCreated();
    } catch {
      toast.error("Не вдалося створити заявку");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="portal-request-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ClipboardList className="h-5 w-5 text-[hsl(var(--primary))]" /> Нова заявка</DialogTitle>
          <DialogDescription>{company ? `Компанія: ${company.name}` : "Оберіть компанію та додайте коди відходів."}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          {!company && (
            <div className="grid gap-1.5">
              <Label>Компанія *</Label>
              <Select value={companyId} onValueChange={setCompanyId}>
                <SelectTrigger data-testid="request-company-select"><SelectValue placeholder="Оберіть компанію" /></SelectTrigger>
                <SelectContent>
                  {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          {objects.length > 0 && (
            <div className="grid gap-1.5">
              <Label>Об’єкт (необов’язково)</Label>
              <Select value={objectId} onValueChange={setObjectId}>
                <SelectTrigger data-testid="request-object-select"><SelectValue placeholder="Без прив’язки до об’єкта" /></SelectTrigger>
                <SelectContent>
                  {objects.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid gap-1.5">
            <Label>Коди відходів *</Label>
            <div className="relative" ref={boxRef}>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => opts.length && setOpenList(true)}
                placeholder="Пошук: ртутні лампи, батарейки, 18 01 03*…" data-testid="request-waste-search"
                className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white pl-9 pr-9 text-sm outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]/30"
              />
              {searching && <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate-400" />}
              {openList && opts.length > 0 && (
                <div className="absolute z-30 mt-2 max-h-[240px] w-full overflow-auto rounded-xl border border-[hsl(var(--border))] bg-white p-2 shadow-xl">
                  {opts.map((it) => (
                    <button key={it.code} type="button" onClick={() => addItem(it)} data-testid="request-waste-option"
                      className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left hover:bg-[hsl(var(--secondary))]/60">
                      <span className="min-w-0"><span className="font-mono text-sm font-semibold text-[hsl(var(--primary))]">{it.code}</span><span className="ml-2 text-xs text-slate-500">{(it.name || "").slice(0, 36)}</span></span>
                      <Plus className="h-4 w-4 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {items.length > 0 && (
            <div className="space-y-2">
              {items.map((it) => (
                <div key={it.waste_code} className="flex items-center gap-2 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 p-2.5" data-testid="request-item-row">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2"><span className="font-mono text-sm font-semibold text-[hsl(var(--primary))]">{it.waste_code}</span><HazardBadge hazardous={it.hazardous} /></div>
                    <div className="truncate text-xs text-slate-500">{it.name}</div>
                  </div>
                  <Input type="number" value={it.qty} onChange={(e) => setQty(it.waste_code, e.target.value)} placeholder="кг" className="h-9 w-24" data-testid="request-item-qty" />
                  <Button type="button" variant="ghost" size="icon" onClick={() => removeItem(it.waste_code)} data-testid="request-item-remove"><Trash2 className="h-4 w-4 text-slate-400" /></Button>
                </div>
              ))}
            </div>
          )}

          <div className="grid gap-1.5">
            <Label>Коментар</Label>
            <Textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} data-testid="request-comment" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={submitting} data-testid="request-submit">{submitting ? "Збереження…" : "Створити заявку"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
