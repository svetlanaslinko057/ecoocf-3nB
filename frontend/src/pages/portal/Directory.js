import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { Database, Plus, Pencil, Trash2, Search, Download, Upload, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { AdminAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { HAZARD_CLASS_LABEL, categoryIcon, money } from "@/lib/wasteMeta";
import { PageHeader, EmptyState, TableSkeleton, StatCard } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
import { toast } from "@/components/ui/sonner";

const HAZARD_OPTS = [
  { value: "_none", label: "Без класу" },
  { value: "1", label: "I — надзвичайно небезп." },
  { value: "2", label: "II — високонебезп." },
  { value: "3", label: "III — помірно небезп." },
  { value: "4", label: "IV — малонебезп." },
];

const EMPTY = {
  code: "", name: "", category: "other_hazard", hazardous: false, hazard_class: "_none",
  human_names: "", description: "", storage: "", transport: "", utilization_process: "",
  required_docs: "", price_from: "", price_unit: "kg", min_order_kg: 0,
  requires_container: false, requires_transport: true,
  license_allowed: true, service_available: true, notes: "",
};

function CodeDialog({ open, onOpenChange, initial, categories, onSaved }) {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const isEdit = !!initial?.code;
  useEffect(() => {
    if (!open) return;
    if (initial) {
      setF({
        ...EMPTY, ...initial,
        hazard_class: initial.hazard_class != null ? String(initial.hazard_class) : "_none",
        human_names: Array.isArray(initial.human_names) ? initial.human_names.join(", ") : (initial.human_names || ""),
        required_docs: Array.isArray(initial.required_docs) ? initial.required_docs.join(", ") : (initial.required_docs || ""),
        price_from: initial.price_from ?? "",
        min_order_kg: initial.min_order_kg ?? 0,
      });
    } else {
      setF(EMPTY);
    }
  }, [open, initial]);
  const setEv = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const submit = async () => {
    if (!f.code.trim()) return toast.error("Вкажіть код");
    if (!f.name.trim()) return toast.error("Вкажіть назву");
    setBusy(true);
    try {
      const payload = {
        code: f.code.trim(),
        name: f.name.trim(),
        category: f.category,
        hazardous: !!f.hazardous,
        hazard_class: f.hazard_class === "_none" ? null : Number(f.hazard_class),
        human_names: (f.human_names || "").split(",").map((s) => s.trim()).filter(Boolean),
        description: f.description.trim() || null,
        storage: f.storage.trim() || null,
        transport: f.transport.trim() || null,
        utilization_process: f.utilization_process.trim() || null,
        required_docs: (f.required_docs || "").split(",").map((s) => s.trim()).filter(Boolean),
        price_from: f.price_from === "" ? null : Number(f.price_from),
        price_unit: f.price_unit || "kg",
        min_order_kg: Number(f.min_order_kg) || 0,
        requires_container: !!f.requires_container,
        requires_transport: !!f.requires_transport,
        license_allowed: !!f.license_allowed,
        service_available: !!f.service_available,
        notes: f.notes.trim() || null,
      };
      if (isEdit) {
        await AdminAPI.updateCode(initial.code, payload);
      } else {
        await AdminAPI.createCode(payload);
      }
      toast.success(isEdit ? "Код оновлено" : "Код створено");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти");
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="directory-dialog">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Редагувати ${initial.code}` : "Новий код відходу"}</DialogTitle>
          <DialogDescription>Поля синхронізовані з публічним довідником і калькулятором.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Код *</Label>
            <Input value={f.code} onChange={setEv("code")} disabled={isEdit} placeholder="напр., 18 01 03*" data-testid="directory-code-input" />
          </div>
          <div className="grid gap-1.5">
            <Label>Категорія *</Label>
            <Select value={f.category} onValueChange={(v) => setF((p) => ({ ...p, category: v }))}>
              <SelectTrigger data-testid="directory-category-select"><SelectValue /></SelectTrigger>
              <SelectContent>{(categories || []).map((c) => <SelectItem key={c.key} value={c.key}>{c.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Назва *</Label><Input value={f.name} onChange={setEv("name")} data-testid="directory-name-input" /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Народні назви (через кому)</Label><Input value={f.human_names} onChange={setEv("human_names")} placeholder="напр., старі ноутбуки, ПК, монітори" data-testid="directory-humannames-input" /></div>
          <div className="grid gap-1.5"><Label>Клас небезпеки</Label>
            <Select value={f.hazard_class} onValueChange={(v) => setF((p) => ({ ...p, hazard_class: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{HAZARD_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 py-2">
            <span className="text-sm text-slate-700">Небезпечний (*)</span>
            <Switch checked={f.hazardous} onCheckedChange={(v) => setF((p) => ({ ...p, hazardous: v }))} data-testid="directory-hazardous-switch" />
          </div>
          <div className="grid gap-1.5"><Label>Ціна від (грн / {f.price_unit})</Label><Input type="number" inputMode="decimal" value={f.price_from} onChange={setEv("price_from")} data-testid="directory-price-input" /></div>
          <div className="grid gap-1.5"><Label>Мін. партія, кг</Label><Input type="number" value={f.min_order_kg} onChange={setEv("min_order_kg")} data-testid="directory-minorder-input" /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Опис</Label><Textarea rows={2} value={f.description} onChange={setEv("description")} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Зберігання</Label><Textarea rows={2} value={f.storage} onChange={setEv("storage")} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Транспортування</Label><Textarea rows={2} value={f.transport} onChange={setEv("transport")} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Процес утилізації</Label><Textarea rows={2} value={f.utilization_process} onChange={setEv("utilization_process")} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Документи (через кому)</Label><Input value={f.required_docs} onChange={setEv("required_docs")} placeholder="Договір, Акт приймання-передачі, Акт утилізації" /></div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] px-3 py-2"><span className="text-sm text-slate-700">Потрібна тара</span><Switch checked={f.requires_container} onCheckedChange={(v) => setF((p) => ({ ...p, requires_container: v }))} /></div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] px-3 py-2"><span className="text-sm text-slate-700">Потрібен спецтранспорт</span><Switch checked={f.requires_transport} onCheckedChange={(v) => setF((p) => ({ ...p, requires_transport: v }))} /></div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] px-3 py-2"><span className="text-sm text-slate-700">Дозволено за ліцензією</span><Switch checked={f.license_allowed} onCheckedChange={(v) => setF((p) => ({ ...p, license_allowed: v }))} /></div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] px-3 py-2"><span className="text-sm text-slate-700">Послуга доступна</span><Switch checked={f.service_available} onCheckedChange={(v) => setF((p) => ({ ...p, service_available: v }))} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Нотатки</Label><Textarea rows={2} value={f.notes} onChange={setEv("notes")} /></div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={busy} data-testid="directory-submit">{busy ? "Збереження…" : isEdit ? "Зберегти" : "Створити"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Directory() {
  useSeo("Довідник відходів", "Адмін: створення, редагування, імпорт/експорт кодів.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [categories, setCategories] = useState([]);
  const [totals, setTotals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("_all");
  const [haz, setHaz] = useState("_all");
  const [acc, setAcc] = useState("_all");
  const [dialog, setDialog] = useState({ open: false, initial: null });
  const [confirmDel, setConfirmDel] = useState(null);
  const [togglingCode, setTogglingCode] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 500 };
      if (q.trim()) params.q = q.trim();
      if (cat !== "_all") params.category = cat;
      if (haz !== "_all") params.hazardous = haz === "yes";
      if (acc !== "_all") params.accepted = acc === "yes";
      const [c, cats] = await Promise.all([AdminAPI.codes(params), AdminAPI.categories()]);
      setRows(c.items || []);
      setCategories(cats.categories || []);
      try { setTotals(await AdminAPI.adminStats()); } catch { /* empty */ }
    } catch { /* empty */ } finally { setLoading(false); }
  }, [q, cat, haz, acc]);

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const stats = useMemo(() => ({
    total: totals?.codes ?? rows.length,
    haz: totals?.hazardous ?? rows.filter((r) => r.hazardous).length,
    licensed: totals?.accepted ?? rows.filter((r) => r.accepted).length,
    cats: categories.length || new Set(rows.map((r) => r.category)).size,
  }), [totals, rows, categories]);

  const toggleAccept = async (item, next) => {
    setTogglingCode(item.code);
    // оптимістично
    setRows((p) => p.map((x) => (x.code === item.code ? { ...x, accepted: next } : x)));
    try {
      const r = await AdminAPI.upsertLicense({
        waste_code: item.code,
        allowed: next,
        license_number: "1247-ОР",
        valid_until: "2030-12-31T00:00:00+00:00",
        notes: item.notes || item.name,
      });
      const realAccepted = !!r.accepted;
      setRows((p) => p.map((x) => (x.code === item.code ? { ...x, accepted: realAccepted } : x)));
      try { setTotals(await AdminAPI.adminStats()); } catch { /* empty */ }
      toast.success(next ? `Код ${item.code} додано до ліцензованих (приймаємо)` : `Код ${item.code} вилучено з ліцензованих`);
    } catch (e) {
      // відкат
      setRows((p) => p.map((x) => (x.code === item.code ? { ...x, accepted: !next } : x)));
      toast.error(e?.response?.data?.detail || "Не вдалося змінити статус");
    } finally { setTogglingCode(null); }
  };

  const handleDelete = async (item) => {
    try {
      await AdminAPI.deleteCode(item.code);
      toast.success("Код видалено");
      setRows((p) => p.filter((x) => x.code !== item.code));
    } catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eco-waste-codes-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success(`Експортовано ${rows.length} кодів`);
  };

  const exportCsv = () => {
    const cols = ["code", "name", "category", "hazardous", "hazard_class", "price_from", "min_order_kg", "license_allowed", "service_available"];
    const esc = (v) => {
      if (v === null || v === undefined) return "";
      const s = String(v).replace(/"/g, '""');
      return /[",\n;]/.test(s) ? `"${s}"` : s;
    };
    const lines = [cols.join(",")].concat(rows.map((r) => cols.map((c) => esc(r[c])).join(",")));
    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eco-waste-codes-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("CSV збережено");
  };

  const onImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      if (!Array.isArray(data)) throw new Error("not array");
      const res = await AdminAPI.importCodes(data);
      toast.success(`Імпортовано: створено ${res.created}, оновлено ${res.updated}`);
      load();
    } catch (err) {
      toast.error("Невалідний JSON або помилка імпорту");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleReseed = async () => {
    try {
      const r = await AdminAPI.reseedCodes(false);
      toast.success(r.seeded ? `Засіяно: створ. ${r.created}, оновл. ${r.updated}` : "Каталог уже наповнено");
      load();
    } catch { toast.error("Не вдалося засіяти"); }
  };

  return (
    <div data-testid="portal-directory">
      <PageHeader
        title="Довідник відходів"
        subtitle="Каталог кодів: створення, редагування, імпорт/експорт"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={exportCsv} className="gap-2" data-testid="directory-export-csv"><Download className="h-4 w-4" /> CSV</Button>
            <Button variant="secondary" onClick={exportJson} className="gap-2" data-testid="directory-export-json"><Download className="h-4 w-4" /> JSON</Button>
            {isAdmin && (
              <>
                <input ref={fileRef} type="file" accept="application/json,.json" onChange={onImportFile} className="hidden" data-testid="directory-import-file" />
                <Button variant="secondary" onClick={() => fileRef.current?.click()} className="gap-2" data-testid="directory-import-button"><Upload className="h-4 w-4" /> Імпорт JSON</Button>
                <Button variant="secondary" onClick={handleReseed} className="gap-2" data-testid="directory-reseed-button"><RefreshCw className="h-4 w-4" /> Re-seed</Button>
                <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2" data-testid="directory-create-button"><Plus className="h-4 w-4" /> Новий код</Button>
              </>
            )}
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Database} label="Усього кодів (нацперелік)" value={stats.total} testid="directory-kpi-total" />
        <StatCard icon={ShieldAlert} label="Небезпечні (*)" value={stats.haz} testid="directory-kpi-haz" />
        <StatCard icon={ShieldCheck} label="Ліцензовано (приймаємо)" value={stats.licensed} testid="directory-kpi-licensed" />
        <StatCard icon={Database} label="Категорій у вибірці" value={stats.cats} testid="directory-kpi-cats" />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr,180px,180px,180px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Код, назва або народна назва…" className="pl-9" data-testid="directory-search" />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger data-testid="directory-cat-filter"><SelectValue placeholder="Категорія" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Усі категорії</SelectItem>
            {categories.map((c) => <SelectItem key={c.key} value={c.key}>{c.name} ({c.count})</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={haz} onValueChange={setHaz}>
          <SelectTrigger data-testid="directory-haz-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Усі (небезпеч. і ні)</SelectItem>
            <SelectItem value="yes">Тільки небезпечні</SelectItem>
            <SelectItem value="no">Тільки безпечні</SelectItem>
          </SelectContent>
        </Select>
        <Select value={acc} onValueChange={setAcc}>
          <SelectTrigger data-testid="directory-acc-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Усі (ліц. і ні)</SelectItem>
            <SelectItem value="yes">Тільки ліцензовані</SelectItem>
            <SelectItem value="no">Поза ліцензією</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={8} /></div>
        ) : rows.length === 0 ? (
          <EmptyState icon={Database} title="За фільтрами нічого не знайдено" hint="Очистіть фільтри або створіть новий код." testid="directory-empty" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Код</TableHead>
                <TableHead>Назва</TableHead>
                <TableHead>Категорія</TableHead>
                <TableHead>Клас</TableHead>
                <TableHead className="text-right">Ціна від</TableHead>
                <TableHead>Стан</TableHead>
                <TableHead className="text-center">Приймаємо</TableHead>
                <TableHead>Оновлено</TableHead>
                {isAdmin && <TableHead className="w-20"></TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const Icon = categoryIcon(r.category);
                return (
                  <TableRow key={r.code} data-testid="directory-row">
                    <TableCell className="font-mono text-sm text-slate-900">{r.code}</TableCell>
                    <TableCell className="max-w-md truncate text-slate-700">{r.name}</TableCell>
                    <TableCell><span className="inline-flex items-center gap-1.5 text-sm text-slate-600"><Icon className="h-4 w-4 text-[hsl(var(--primary))]" /> {r.category_name || r.category}</span></TableCell>
                    <TableCell className="text-xs text-slate-500">{r.hazard_class ? HAZARD_CLASS_LABEL[r.hazard_class] : "—"}</TableCell>
                    <TableCell className="text-right font-mono text-slate-800">{r.price_from != null ? `${money(r.price_from)} грн/${r.price_unit || "kg"}` : "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.hazardous && <span className="inline-flex rounded-md border border-[#FDE68A] bg-[#FFFBEB] px-1.5 py-0.5 text-[10px] font-medium text-[#92400E]">небезп.</span>}
                        {r.accepted
                          ? <span className="inline-flex rounded-md border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">ліцензовано</span>
                          : <span className="inline-flex rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-1.5 py-0.5 text-[10px] text-slate-500">поза ліц.</span>}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={!!r.accepted}
                        disabled={!isAdmin || togglingCode === r.code}
                        onCheckedChange={(v) => toggleAccept(r, v)}
                        data-testid="directory-accept-switch"
                        aria-label={`Приймаємо ${r.code}`}
                      />
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">{fmtDate(r.updated_at || r.created_at)}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setDialog({ open: true, initial: r })} data-testid="directory-edit-button"><Pencil className="h-4 w-4" /></Button>
                          <Button variant="ghost" size="icon" onClick={() => setConfirmDel(r)} data-testid="directory-delete-button"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      <CodeDialog open={dialog.open} onOpenChange={(v) => setDialog((p) => ({ ...p, open: v }))} initial={dialog.initial} categories={categories} onSaved={load} />
      <AlertDialog open={!!confirmDel} onOpenChange={(v) => !v && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Видалити код {confirmDel?.code}?</AlertDialogTitle><AlertDialogDescription>Цей код зникне з публічного довідника та калькулятора. Дія незворотна.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Скасувати</AlertDialogCancel><AlertDialogAction onClick={() => handleDelete(confirmDel)} data-testid="directory-confirm-delete">Видалити</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
