import React, { useEffect, useMemo, useState, useCallback } from "react";
import { Banknote, Plus, Pencil, Trash2, Calculator, Sparkles, AlertTriangle } from "lucide-react";
import { AdminAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { money } from "@/lib/wasteMeta";
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

const CONTAINER_OPTS = [
  { value: "any", label: "Будь-яка тара" },
  { value: "provided", label: "Тара клієнта" },
  { value: "needed", label: "Потрібна наша" },
];

const EMPTY = {
  wasteCode: "",
  region: "*",
  minWeight: 0,
  maxWeight: "",
  containerType: "any",
  transportRequired: false,
  urgent: false,
  pricePerKg: "",
  minimumCharge: 0,
  containerPerKg: "",
  transportFlat: "",
  transportPerKg: "",
  urgentSurchargePct: "",
  currency: "UAH",
  notes: "",
  active: true,
};

function toPayload(f) {
  const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
  const out = {
    wasteCode: (f.wasteCode || "").trim() || "*",
    region: (f.region || "*").trim().toLowerCase() || "*",
    minWeight: Number(f.minWeight) || 0,
    maxWeight: num(f.maxWeight),
    containerType: f.containerType || "any",
    transportRequired: !!f.transportRequired,
    urgent: !!f.urgent,
    pricePerKg: Number(f.pricePerKg),
    minimumCharge: Number(f.minimumCharge) || 0,
    containerPerKg: num(f.containerPerKg),
    transportFlat: num(f.transportFlat),
    transportPerKg: num(f.transportPerKg),
    urgentSurchargePct: num(f.urgentSurchargePct),
    currency: f.currency || "UAH",
    notes: (f.notes || "").trim() || null,
    active: !!f.active,
  };
  // strip nulls of override fields so backend keeps defaults
  ["maxWeight", "containerPerKg", "transportFlat", "transportPerKg", "urgentSurchargePct"].forEach((k) => {
    if (out[k] === null) delete out[k];
  });
  return out;
}

function PriceRuleDialog({ open, onOpenChange, initial, meta, codeOptions, onSaved }) {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const isEdit = !!initial?.id;
  useEffect(() => {
    if (!open) return;
    if (initial) {
      setF({
        ...EMPTY, ...initial,
        maxWeight: initial.maxWeight ?? "",
        containerPerKg: initial.containerPerKg ?? "",
        transportFlat: initial.transportFlat ?? "",
        transportPerKg: initial.transportPerKg ?? "",
        urgentSurchargePct: initial.urgentSurchargePct ?? "",
        notes: initial.notes ?? "",
      });
    } else {
      setF(EMPTY);
    }
  }, [open, initial]);
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }));
  const setEv = (k) => (e) => set(k)(e.target.value);
  const submit = async () => {
    if (!f.pricePerKg || Number(f.pricePerKg) <= 0) return toast.error("Вкажіть ціну за кг (pricePerKg)");
    if (!f.wasteCode.trim()) return toast.error("Вкажіть код відходу або *");
    setBusy(true);
    try {
      const payload = toPayload(f);
      const r = isEdit ? await AdminAPI.updatePriceRule(initial.id, payload) : await AdminAPI.createPriceRule(payload);
      toast.success(isEdit ? "Правило оновлено" : "Правило створено");
      onSaved && onSaved(r.rule);
      onOpenChange(false);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Не вдалося зберегти правило";
      toast.error(msg);
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="pricing-dialog">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Редагувати правило" : "Нове правило ціноутворення"}</DialogTitle>
          <DialogDescription>Тариф = max(pricePerKg × вага, minimumCharge) + тара + транспорт + регіональний коеф. + терміновість.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5 sm:col-span-2">
            <Label>Код відходу *</Label>
            <Input list="price-rule-codes" value={f.wasteCode} onChange={setEv("wasteCode")} placeholder="напр., 18 01 03* (або * для всіх)" data-testid="pricing-wastecode-input" />
            <datalist id="price-rule-codes">{(codeOptions || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</datalist>
          </div>
          <div className="grid gap-1.5">
            <Label>Регіон</Label>
            <Select value={f.region} onValueChange={set("region")}><SelectTrigger data-testid="pricing-region-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="*">Усі регіони</SelectItem>
                {(meta?.regions || []).map((r) => <SelectItem key={r.key} value={r.key}>{r.name} (×{r.factor})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Тип тари</Label>
            <Select value={f.containerType} onValueChange={set("containerType")}><SelectTrigger data-testid="pricing-container-select"><SelectValue /></SelectTrigger>
              <SelectContent>{CONTAINER_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Min вага, кг</Label>
            <Input type="number" inputMode="decimal" value={f.minWeight} onChange={setEv("minWeight")} data-testid="pricing-minweight-input" />
          </div>
          <div className="grid gap-1.5">
            <Label>Max вага, кг (порожньо = ∞)</Label>
            <Input type="number" inputMode="decimal" value={f.maxWeight} onChange={setEv("maxWeight")} placeholder="—" data-testid="pricing-maxweight-input" />
          </div>
          <div className="grid gap-1.5">
            <Label>Ціна за кг (грн) *</Label>
            <Input type="number" inputMode="decimal" value={f.pricePerKg} onChange={setEv("pricePerKg")} data-testid="pricing-perkg-input" />
          </div>
          <div className="grid gap-1.5">
            <Label>Мінімальна партія (грн)</Label>
            <Input type="number" inputMode="decimal" value={f.minimumCharge} onChange={setEv("minimumCharge")} data-testid="pricing-mincharge-input" />
          </div>
          <div className="sm:col-span-2 rounded-xl border border-dashed border-[hsl(var(--border))] p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Опціональні перевизначення логістики</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5"><Label className="text-xs">Тара / кг (грн)</Label><Input type="number" value={f.containerPerKg} onChange={setEv("containerPerKg")} placeholder="за замовч. 1.5" /></div>
              <div className="grid gap-1.5"><Label className="text-xs">Транспорт base (грн)</Label><Input type="number" value={f.transportFlat} onChange={setEv("transportFlat")} placeholder="за замовч. 1500" /></div>
              <div className="grid gap-1.5"><Label className="text-xs">Транспорт / кг (грн)</Label><Input type="number" value={f.transportPerKg} onChange={setEv("transportPerKg")} placeholder="за замовч. 2.0" /></div>
              <div className="grid gap-1.5"><Label className="text-xs">Терміновість, частка</Label><Input type="number" step="0.05" value={f.urgentSurchargePct} onChange={setEv("urgentSurchargePct")} placeholder="за замовч. 0.25" /></div>
            </div>
          </div>
          <div className="grid gap-1.5 sm:col-span-2"><Label>Нотатки</Label><Textarea rows={2} value={f.notes} onChange={setEv("notes")} /></div>
          <div className="flex items-center gap-2 sm:col-span-2">
            <Switch checked={f.active} onCheckedChange={(v) => set("active")(v)} data-testid="pricing-active-switch" />
            <span className="text-sm text-slate-600">Правило активне</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={busy} data-testid="pricing-submit">{busy ? "Збереження…" : isEdit ? "Зберегти" : "Створити"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Tester({ meta, codeOptions }) {
  const [code, setCode] = useState("");
  const [weight, setWeight] = useState(50);
  const [region, setRegion] = useState("kyiv");
  const [container, setContainer] = useState("provided");
  const [transport, setTransport] = useState(false);
  const [urgent, setUrgent] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (!code.trim()) return toast.error("Оберіть код для прорахунку");
    setBusy(true);
    try {
      const r = await AdminAPI.price({ code: code.trim(), weight: Number(weight) || 0, region, container, transport, urgent });
      setResult(r);
    } catch { toast.error("Не вдалося порахувати"); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5" data-testid="pricing-tester">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Calculator className="h-4 w-4 text-[hsl(var(--primary))]" /> Тест-прорахунок</div>
      <p className="mt-1 text-xs text-slate-500">Перевірте, як правила застосовуються до реальних параметрів.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5 sm:col-span-2"><Label className="text-xs">Код відходу</Label>
          <Input list="tester-codes" value={code} onChange={(e) => setCode(e.target.value)} placeholder="напр., 18 01 03*" data-testid="pricing-tester-code" />
          <datalist id="tester-codes">{(codeOptions || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</datalist>
        </div>
        <div className="grid gap-1.5"><Label className="text-xs">Вага, кг</Label><Input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} data-testid="pricing-tester-weight" /></div>
        <div className="grid gap-1.5"><Label className="text-xs">Регіон</Label>
          <Select value={region} onValueChange={setRegion}><SelectTrigger data-testid="pricing-tester-region"><SelectValue /></SelectTrigger>
            <SelectContent>{(meta?.regions || []).map((r) => <SelectItem key={r.key} value={r.key}>{r.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5"><Label className="text-xs">Тара</Label>
          <Select value={container} onValueChange={setContainer}><SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="provided">Клієнта</SelectItem><SelectItem value="needed">Наша</SelectItem></SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-[hsl(var(--border))] px-3 py-2"><span className="text-xs text-slate-600">Транспорт</span><Switch checked={transport} onCheckedChange={setTransport} data-testid="pricing-tester-transport" /></div>
        <div className="flex items-center justify-between rounded-lg border border-[hsl(var(--border))] px-3 py-2"><span className="text-xs text-slate-600">Терміновість</span><Switch checked={urgent} onCheckedChange={setUrgent} data-testid="pricing-tester-urgent" /></div>
      </div>
      <Button onClick={run} disabled={busy} className="mt-4 w-full gap-2" data-testid="pricing-tester-run"><Sparkles className="h-4 w-4" /> {busy ? "Розрахунок…" : "Порахувати"}</Button>
      {result?.ok === false && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#991B1B]"><AlertTriangle className="h-4 w-4" /> {result.reason || "Код не знайдено"}</div>
      )}
      {result?.ok && (
        <div className="mt-4 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-4" data-testid="pricing-tester-result">
          <div className="flex items-baseline justify-between">
            <div className="text-sm font-medium text-slate-700">{result.name}</div>
            <div className="text-xs uppercase tracking-wide text-slate-500">{result.source === "rule" ? "за правилом" : "дефолт"}</div>
          </div>
          <div className="mt-2 text-3xl font-semibold text-[hsl(var(--primary))]">{money(result.price)} <span className="text-base font-normal text-slate-500">{result.currency}</span></div>
          <div className="mt-3 space-y-1.5 text-sm">
            {(result.breakdown || []).map((b, i) => (
              <div key={i} className="flex justify-between"><span className="text-slate-600">{b.label}</span><span className="font-mono text-slate-800">{money(b.amount)}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Pricing() {
  useSeo("Тарифи та ціноутворення", "Адмін: правила ціноутворення для утилізації небезпечних відходів.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState({ open: false, initial: null });
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, m, c] = await Promise.all([
        AdminAPI.priceRules(),
        AdminAPI.pricingMeta(),
        AdminAPI.codes({ limit: 500 }),
      ]);
      setRows(r.items || []);
      setMeta(m || null);
      setCodes(c.items || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const stats = useMemo(() => ({
    total: rows.length,
    active: rows.filter((r) => r.active !== false).length,
    codes: new Set(rows.map((r) => r.wasteCode)).size,
  }), [rows]);

  const handleDelete = async (rule) => {
    try {
      await AdminAPI.deletePriceRule(rule.id);
      toast.success("Правило видалено");
      setRows((p) => p.filter((x) => x.id !== rule.id));
    } catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  const handleSeed = async () => {
    try {
      const r = await AdminAPI.seedPriceRules();
      toast.success(r.seeded ? `Створено ${r.created} прикладів` : "Демо-правила вже існують");
      load();
    } catch { toast.error("Не вдалося наповнити демо-правилами"); }
  };

  return (
    <div data-testid="portal-pricing">
      <PageHeader
        title="Тарифи та ціноутворення"
        subtitle="Тарифи на утилізацію: код · регіон · вага · тара · логістика"
        actions={isAdmin && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleSeed} className="gap-2" data-testid="pricing-seed-button"><Sparkles className="h-4 w-4" /> Демо-правила</Button>
            <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2" data-testid="pricing-create-button"><Plus className="h-4 w-4" /> Нове правило</Button>
          </div>
        )}
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Banknote} label="Усього правил" value={stats.total} testid="pricing-kpi-total" />
        <StatCard icon={Sparkles} label="Активні" value={stats.active} testid="pricing-kpi-active" />
        <StatCard icon={Calculator} label="Унікальних кодів" value={stats.codes} testid="pricing-kpi-codes" />
        <StatCard label="Валюта" value={meta?.currency || "UAH"} hint={meta ? `Term.: +${Math.round((meta.defaults?.urgent_surcharge_pct || 0.25) * 100)}%` : ""} testid="pricing-kpi-currency" />
      </div>

      {/* Global pricing defaults — admin-editable (urgent %, container fee, transport) */}
      <PricingDefaultsCard isAdmin={isAdmin} meta={meta} onSaved={() => load()} />

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2 overflow-hidden rounded-2xl border border-[hsl(var(--border))] bg-white">
          {loading ? (
            <div className="p-4"><TableSkeleton rows={6} /></div>
          ) : rows.length === 0 ? (
            <EmptyState icon={Banknote} title="Правил немає" hint="Додайте перше правило або згенеруйте демо-набір." action={isAdmin && <div className="flex gap-2"><Button onClick={handleSeed} variant="secondary" className="gap-2"><Sparkles className="h-4 w-4" /> Демо</Button><Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2"><Plus className="h-4 w-4" /> Створити</Button></div>} testid="pricing-empty" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Код</TableHead>
                  <TableHead>Регіон</TableHead>
                  <TableHead>Вагова смуга</TableHead>
                  <TableHead>Тара</TableHead>
                  <TableHead className="text-right">грн/кг</TableHead>
                  <TableHead className="text-right">Min, грн</TableHead>
                  <TableHead>Стан</TableHead>
                  <TableHead>Оновлено</TableHead>
                  {isAdmin && <TableHead className="w-20"></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id} data-testid="pricing-row">
                    <TableCell className="whitespace-nowrap font-mono text-sm font-semibold text-slate-900">{r.wasteCode}</TableCell>
                    <TableCell className="whitespace-nowrap text-slate-600">{r.region === "*" ? "усі" : r.region}</TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-xs text-slate-500">{r.minWeight}–{r.maxWeight ?? "∞"} кг</TableCell>
                    <TableCell className="whitespace-nowrap text-slate-500">{CONTAINER_OPTS.find((c) => c.value === r.containerType)?.label || r.containerType}</TableCell>
                    <TableCell className="whitespace-nowrap text-right font-mono font-semibold text-slate-900">{money(r.pricePerKg)}</TableCell>
                    <TableCell className="whitespace-nowrap text-right text-slate-600">{r.minimumCharge ? money(r.minimumCharge) : "—"}</TableCell>
                    <TableCell>{r.active === false ? <span className="inline-flex items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-2 py-0.5 text-xs text-slate-500">Вимкнено</span> : <span className="inline-flex items-center rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-2 py-0.5 text-xs font-medium text-[#065F46]">Активне</span>}</TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-slate-500">{fmtDate(r.updated_at || r.created_at)}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setDialog({ open: true, initial: r })} data-testid="pricing-edit-button"><Pencil className="h-4 w-4" /></Button>
                          <Button variant="ghost" size="icon" onClick={() => setConfirmDel(r)} data-testid="pricing-delete-button"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
        <Tester meta={meta} codeOptions={codes} />
      </div>

      <PriceRuleDialog open={dialog.open} onOpenChange={(v) => setDialog((p) => ({ ...p, open: v }))} initial={dialog.initial} meta={meta} codeOptions={codes} onSaved={() => load()} />
      <AlertDialog open={!!confirmDel} onOpenChange={(v) => !v && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Видалити правило?</AlertDialogTitle><AlertDialogDescription>Дія незворотна. Правило для коду <span className="font-mono">{confirmDel?.wasteCode}</span> буде видалено.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Скасувати</AlertDialogCancel><AlertDialogAction onClick={() => handleDelete(confirmDel)} data-testid="pricing-confirm-delete">Видалити</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════════
//  Admin-editable global pricing defaults (urgent % + container + transport)
// ══════════════════════════════════════════════════════════════════════════
function PricingDefaultsCard({ isAdmin, meta, onSaved }) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (meta?.defaults) {
      setForm({
        urgent_surcharge_pct: meta.defaults.urgent_surcharge_pct ?? 0.25,
        container_fee_per_kg: meta.defaults.container_fee_per_kg ?? 1.5,
        transport_base:       meta.defaults.transport_base       ?? 1500,
        transport_per_kg:     meta.defaults.transport_per_kg     ?? 2,
      });
    }
  }, [meta]);

  const d = meta?.defaults || {};
  const urgentPct = Math.round((d.urgent_surcharge_pct || 0) * 100);

  const setField = (k) => (e) => {
    const v = e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const save = async () => {
    if (!form) return;
    setBusy(true);
    try {
      await AdminAPI.updatePricingDefaults({
        urgent_surcharge_pct: Number(form.urgent_surcharge_pct) || 0,
        container_fee_per_kg: Number(form.container_fee_per_kg) || 0,
        transport_base:       Number(form.transport_base)       || 0,
        transport_per_kg:     Number(form.transport_per_kg)     || 0,
      });
      toast.success("Глобальні дефолти оновлено");
      setExpanded(false);
      onSaved?.();
    } catch {
      toast.error("Не вдалося зберегти");
    } finally { setBusy(false); }
  };

  const reset = () => {
    if (meta?.defaults) {
      setForm({
        urgent_surcharge_pct: meta.defaults.urgent_surcharge_pct ?? 0.25,
        container_fee_per_kg: meta.defaults.container_fee_per_kg ?? 1.5,
        transport_base:       meta.defaults.transport_base       ?? 1500,
        transport_per_kg:     meta.defaults.transport_per_kg     ?? 2,
      });
    }
  };

  return (
    <div className="mb-6 rounded-2xl border border-[hsl(var(--border))] bg-white p-5" data-testid="pricing-defaults-card">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Sparkles className="h-4 w-4 text-[hsl(var(--primary))]" />
            Глобальні дефолти ціноутворення
          </div>
          <p className="mt-1 text-xs text-slate-500 max-w-2xl">
            Застосовуються, коли конкретне <span className="font-medium">правило</span> не задає власне значення.
            Терміновість — це % надбавки до вартості утилізації після регіонального коефіцієнта.
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            {expanded ? (
              <>
                <Button variant="secondary" onClick={() => { reset(); setExpanded(false); }} disabled={busy}>Скасувати</Button>
                <Button onClick={save} disabled={busy} data-testid="pricing-defaults-save">
                  {busy ? "Збереження…" : "Зберегти"}
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setExpanded(true)} className="gap-2" data-testid="pricing-defaults-edit">
                <Pencil className="h-4 w-4" /> Редагувати
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <DefaultCell
          label="Терміновість"
          value={`+${urgentPct}%`}
          hint="Надбавка до основної вартості"
          editing={expanded}
          input={
            <div className="flex items-center gap-2">
              <Input
                type="number" step="0.01" min="0" max="5"
                value={form?.urgent_surcharge_pct ?? ""}
                onChange={setField("urgent_surcharge_pct")}
                data-testid="pd-urgent" className="w-full" />
              <span className="text-xs text-slate-500 whitespace-nowrap">частка (0.25 = 25%)</span>
            </div>
          }
        />
        <DefaultCell
          label="Тара (грн/кг)"
          value={money(d.container_fee_per_kg || 0)}
          hint="Плата за нашу тару"
          editing={expanded}
          input={
            <Input
              type="number" step="0.1" min="0"
              value={form?.container_fee_per_kg ?? ""}
              onChange={setField("container_fee_per_kg")}
              data-testid="pd-container" />
          }
        />
        <DefaultCell
          label="Транспорт: база"
          value={`${money(d.transport_base || 0)} грн`}
          hint="Фіксована подача"
          editing={expanded}
          input={
            <Input
              type="number" step="50" min="0"
              value={form?.transport_base ?? ""}
              onChange={setField("transport_base")}
              data-testid="pd-transport-base" />
          }
        />
        <DefaultCell
          label="Транспорт: грн/кг"
          value={money(d.transport_per_kg || 0)}
          hint="Змінна частина за вагою"
          editing={expanded}
          input={
            <Input
              type="number" step="0.1" min="0"
              value={form?.transport_per_kg ?? ""}
              onChange={setField("transport_per_kg")}
              data-testid="pd-transport-perkg" />
          }
        />
      </div>

      {!isAdmin && (
        <p className="mt-3 text-xs text-slate-400">Редагування доступне лише адміністраторам.</p>
      )}
    </div>
  );
}

function DefaultCell({ label, value, hint, editing, input }) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      {editing ? (
        <div className="mt-2">{input}</div>
      ) : (
        <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
      )}
      <div className="mt-1 text-[11px] text-slate-500">{hint}</div>
    </div>
  );
}
