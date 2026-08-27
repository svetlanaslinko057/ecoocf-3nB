import React, { useEffect, useState, useCallback, useMemo } from "react";
import { ShieldCheck, Plus, Pencil, Trash2, Search, AlertTriangle, CheckCircle2, XCircle, Calendar, RefreshCw } from "lucide-react";
import { AdminAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { PageHeader, EmptyState, TableSkeleton, StatCard } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
import { toast } from "@/components/ui/sonner";

function isExpired(iso) {
  if (!iso) return false;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return false;
  return d.getTime() < Date.now();
}
function daysUntil(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return Math.round((d.getTime() - Date.now()) / 86400000);
}

function LicenseDialog({ open, onOpenChange, initial, codeOptions, onSaved }) {
  const [f, setF] = useState({ waste_code: "", allowed: true, license_number: "", valid_until: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const isEdit = !!initial?.id;
  useEffect(() => {
    if (!open) return;
    if (initial) {
      setF({
        waste_code: initial.waste_code || "",
        allowed: initial.allowed !== false,
        license_number: initial.license_number || "",
        valid_until: (initial.valid_until || "").slice(0, 10),
        notes: initial.notes || "",
      });
    } else {
      setF({ waste_code: "", allowed: true, license_number: "", valid_until: "", notes: "" });
    }
  }, [open, initial]);
  const submit = async () => {
    if (!f.waste_code.trim()) return toast.error("Вкажіть код відходу");
    setBusy(true);
    try {
      await AdminAPI.upsertLicense({
        waste_code: f.waste_code.trim(),
        allowed: !!f.allowed,
        license_number: f.license_number.trim() || null,
        valid_until: f.valid_until ? new Date(f.valid_until).toISOString() : null,
        notes: f.notes.trim() || null,
      });
      toast.success(isEdit ? "Запис оновлено" : "Запис створено");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти");
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="license-dialog">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Редагувати ліцензію" : "Додати ліцензію для коду"}</DialogTitle>
          <DialogDescription>Менеджер бачитиме автоматичне рішення про прийом для цього коду.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Код відходу *</Label>
            <Input list="license-codes" value={f.waste_code} onChange={(e) => setF((p) => ({ ...p, waste_code: e.target.value }))} disabled={isEdit} placeholder="напр., 18 01 03*" data-testid="license-code-input" />
            <datalist id="license-codes">{(codeOptions || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</datalist>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 py-2">
            <div>
              <div className="text-sm font-medium text-slate-800">Можемо приймати</div>
              <div className="text-xs text-slate-500">Дозвіл на цей код у нашій ліцензії</div>
            </div>
            <Switch checked={f.allowed} onCheckedChange={(v) => setF((p) => ({ ...p, allowed: v }))} data-testid="license-allowed-switch" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Номер ліцензії</Label><Input value={f.license_number} onChange={(e) => setF((p) => ({ ...p, license_number: e.target.value }))} data-testid="license-number-input" /></div>
            <div className="grid gap-1.5"><Label>Діє до</Label><Input type="date" value={f.valid_until} onChange={(e) => setF((p) => ({ ...p, valid_until: e.target.value }))} data-testid="license-until-input" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Нотатки</Label><Textarea rows={2} value={f.notes} onChange={(e) => setF((p) => ({ ...p, notes: e.target.value }))} /></div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={busy} data-testid="license-submit">{busy ? "Збереження…" : isEdit ? "Зберегти" : "Створити"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Licenses() {
  useSeo("Реєстр ліцензій", "Матриця ліцензій: які коди ми можемо приймати.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState({ open: false, initial: null });
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [l, c] = await Promise.all([AdminAPI.licenses(), AdminAPI.codes({ limit: 2000 })]);
      setRows(l.items || []);
      setCodes(c.items || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSeed = async () => {
    try {
      const r = await AdminAPI.seedLicenses(false);
      toast.success(r.seeded ? `Засіяно ліцензований набір: ${r.created} кодів` : `Перелік уже наповнено (${r.count}). Перераховано прийняття: ${r.accepted_codes}`);
      load();
    } catch { toast.error("Не вдалося засіяти перелік"); }
  };

  const codeMap = useMemo(() => {
    const m = new Map();
    codes.forEach((c) => m.set(c.code, c));
    return m;
  }, [codes]);

  const filtered = useMemo(() => {
    if (!q.trim()) return rows;
    const ql = q.toLowerCase();
    return rows.filter((r) => (r.waste_code || "").toLowerCase().includes(ql) || (codeMap.get(r.waste_code)?.name || "").toLowerCase().includes(ql) || (r.license_number || "").toLowerCase().includes(ql));
  }, [rows, q, codeMap]);

  const stats = useMemo(() => {
    const accepted = rows.filter((r) => r.allowed !== false && !isExpired(r.valid_until)).length;
    const expiring = rows.filter((r) => {
      const d = daysUntil(r.valid_until);
      return d !== null && d >= 0 && d <= 30;
    }).length;
    const expired = rows.filter((r) => isExpired(r.valid_until)).length;
    return { total: rows.length, accepted, expiring, expired };
  }, [rows]);

  const handleDelete = async (item) => {
    try {
      await AdminAPI.deleteLicense(item.id);
      toast.success("Запис видалено");
      setRows((p) => p.filter((x) => x.id !== item.id));
    } catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  return (
    <div data-testid="portal-licenses">
      <PageHeader
        title="Реєстр ліцензій"
        subtitle="Які коди небезпечних відходів ми можемо приймати"
        actions={isAdmin && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={handleSeed} className="gap-2" data-testid="license-seed-button"><RefreshCw className="h-4 w-4" /> Засіяти набір</Button>
            <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2" data-testid="license-create-button"><Plus className="h-4 w-4" /> Додати запис</Button>
          </div>
        )}
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={ShieldCheck} label="Усього записів" value={stats.total} testid="license-kpi-total" />
        <StatCard icon={CheckCircle2} label="Можемо приймати" value={stats.accepted} testid="license-kpi-accepted" />
        <StatCard icon={Calendar} label="Спливає (30 днів)" value={stats.expiring} testid="license-kpi-expiring" />
        <StatCard icon={AlertTriangle} label="Прострочено" value={stats.expired} testid="license-kpi-expired" />
      </div>

      <div className="mb-4 relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук за кодом / номером ліцензії…" className="pl-9" data-testid="licenses-search" />
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={6} /></div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="Записів немає" hint="Додайте код-ліцензію, щоб менеджер бачив автоматичне рішення." action={isAdmin && <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2"><Plus className="h-4 w-4" /> Додати запис</Button>} testid="licenses-empty" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Код</TableHead>
                <TableHead>Назва</TableHead>
                <TableHead>Ліцензія</TableHead>
                <TableHead>Діє до</TableHead>
                <TableHead>Можемо приймати</TableHead>
                <TableHead>Оновлено</TableHead>
                {isAdmin && <TableHead className="w-20"></TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => {
                const expired = isExpired(r.valid_until);
                const accepted = r.allowed !== false && !expired;
                const d = daysUntil(r.valid_until);
                const expiringSoon = d !== null && d >= 0 && d <= 30;
                return (
                  <TableRow key={r.id} data-testid="license-row">
                    <TableCell className="whitespace-nowrap font-mono text-sm font-semibold text-slate-900">{r.waste_code}</TableCell>
                    <TableCell className="text-slate-600 max-w-xs truncate">{codeMap.get(r.waste_code)?.name || "—"}</TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-slate-600">{r.license_number || "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className={`text-sm ${expired ? "text-[#991B1B] font-medium" : expiringSoon ? "text-[#92400E] font-medium" : "text-slate-700"}`}>{fmtDate(r.valid_until)}</span>
                        {expired && <span className="text-xs text-[#991B1B]">прострочено</span>}
                        {!expired && expiringSoon && <span className="text-xs text-[#92400E]">≤ 30 днів</span>}
                      </div>
                    </TableCell>
                    <TableCell>
                      {accepted
                        ? <span className="inline-flex items-center gap-1 rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-2 py-0.5 text-xs font-medium text-[#065F46]"><CheckCircle2 className="h-3.5 w-3.5" /> Так</span>
                        : <span className="inline-flex items-center gap-1 rounded-md border border-[#FECACA] bg-[#FEF2F2] px-2 py-0.5 text-xs font-medium text-[#991B1B]"><XCircle className="h-3.5 w-3.5" /> Ні</span>}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-slate-500">{fmtDate(r.updated_at || r.created_at)}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setDialog({ open: true, initial: r })} data-testid="license-edit-button"><Pencil className="h-4 w-4" /></Button>
                          <Button variant="ghost" size="icon" onClick={() => setConfirmDel(r)} data-testid="license-delete-button"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button>
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

      <LicenseDialog open={dialog.open} onOpenChange={(v) => setDialog((p) => ({ ...p, open: v }))} initial={dialog.initial} codeOptions={codes} onSaved={load} />
      <AlertDialog open={!!confirmDel} onOpenChange={(v) => !v && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Видалити запис?</AlertDialogTitle><AlertDialogDescription>Менеджер більше не побачить автоматичне рішення для коду <span className="font-mono">{confirmDel?.waste_code}</span>.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Скасувати</AlertDialogCancel><AlertDialogAction onClick={() => handleDelete(confirmDel)} data-testid="license-confirm-delete">Видалити</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
