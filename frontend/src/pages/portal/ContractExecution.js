/**
 * ContractExecution — staff Contract Execution Engine console.
 * Route: /app/operations/contracts/:contractId
 *
 * Tabs: Фінанси (5 values) · Графік (Plan/Fact/Deviation + overrides + extra works)
 *       · Звіт еколога · Завершення (Completion Wizard).
 */
import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Wallet, TrendingUp, FileText, CheckCircle2, XCircle, Recycle, Plus, Trash2,
  Lock, RefreshCw, CalendarRange, Leaf, ArrowLeft, Download,
} from "lucide-react";
import { PortalAPI, api } from "@/lib/api";
import { PageHeader, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";

const money = (v, cur = "UAH") =>
  (v == null ? "—" : `${Number(v).toLocaleString("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`);
const kg = (v) => (v == null ? "0" : Number(v).toLocaleString("uk-UA", { maximumFractionDigits: 1 }));

const EXTRA_TYPES = [
  ["transport", "Транспорт"], ["urgent", "Терміновий виїзд"], ["packaging", "Додаткова тара"],
  ["lab", "Лабораторія"], ["sorting", "Сортування"], ["other", "Інші послуги"],
];
const PERIOD_TYPES = [["quarter", "Квартал"], ["month", "Місяць"], ["one_time", "Разовий"], ["custom", "Довільний"]];

function FinCard({ icon: Icon, label, value, cur, tone = "slate", hint }) {
  const tones = {
    slate: "border-slate-200 bg-white", green: "border-emerald-200 bg-emerald-50",
    blue: "border-blue-200 bg-blue-50", amber: "border-amber-200 bg-amber-50", red: "border-rose-200 bg-rose-50",
  };
  return (
    <div className={`rounded-2xl border p-4 ${tones[tone]}`} data-testid={`ce-fin-${label}`}>
      <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
        <Icon className="h-4 w-4" /> {label}
      </div>
      <div className="mt-2 text-[22px] font-bold text-slate-900">{money(value, cur)}</div>
      {hint ? <div className="mt-1 text-[12px] text-slate-500">{hint}</div> : null}
    </div>
  );
}

export default function ContractExecution() {
  const { contractId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [contract, setContract] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [fin, setFin] = useState({});
  const [reports, setReports] = useState([]);
  const [comp, setComp] = useState(null);
  const [acts, setActs] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const cur = contract?.currency || "UAH";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await PortalAPI.ceSchedule(contractId);
      setContract(s.contract || null);
      setPeriods(s.periods || []);
      setFin(s.financials || {});
      const [r, c, inv] = await Promise.all([
        PortalAPI.ceReports(contractId).catch(() => ({ items: [] })),
        PortalAPI.ceCompletionCheck(contractId).catch(() => null),
        PortalAPI.ceContractInvoices(contractId).catch(() => ({ items: [] })),
      ]);
      setReports(r.items || []);
      setComp(c || null);
      setInvoices(inv.items || []);
      const companyId = s.contract?.company_id;
      if (companyId) {
        const a = await PortalAPI.acts({ company_id: companyId, limit: 500 }).catch(() => ({ items: [] }));
        setActs((a.items || a || []).filter((x) => x.contract_id === contractId));
      } else {
        setActs([]);
      }
    } catch (e) {
      toast.error("Не вдалося завантажити договір");
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => { load(); }, [load]);

  const refreshFin = (f) => { if (f) setFin(f); };

  const genSchedule = async () => {
    try { const r = await PortalAPI.ceGenerate(contractId, { replace: true }); setPeriods(r.periods || []); refreshFin(r.financials); toast.success("Графік згенеровано"); }
    catch { toast.error("Помилка генерації графіка"); }
  };
  const freeze = async () => {
    try { const r = await PortalAPI.ceFreeze(contractId); refreshFin(r.financials); toast.success("Договірну суму зафіксовано"); }
    catch { toast.error("Помилка"); }
  };
  const recompute = async () => {
    try { const r = await PortalAPI.ceRecompute(contractId); refreshFin(r.financials); await load(); toast.success("Перераховано"); }
    catch { toast.error("Помилка"); }
  };

  const patchLine = async (periodId, code, patch) => {
    try {
      const r = await PortalAPI.cePatchLine(periodId, code, patch);
      setPeriods((prev) => prev.map((p) => (p.id === periodId ? r.period : p)));
      refreshFin(r.financials);
    } catch { toast.error("Не вдалося зберегти рядок"); }
  };
  const addExtra = async (periodId, body) => {
    try { const r = await PortalAPI.ceAddExtra(periodId, body); setPeriods((prev) => prev.map((p) => (p.id === periodId ? r.period : p))); refreshFin(r.financials); }
    catch { toast.error("Помилка"); }
  };
  const delExtra = async (periodId, extraId) => {
    try { const r = await PortalAPI.ceDelExtra(periodId, extraId); setPeriods((prev) => prev.map((p) => (p.id === periodId ? r.period : p))); refreshFin(r.financials); }
    catch { toast.error("Помилка"); }
  };

  const openPdf = async (reportId) => {
    try {
      const res = await api.get(`/waste/ecologist-reports/${reportId}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      window.open(url, "_blank");
    } catch { toast.error("Не вдалося відкрити PDF"); }
  };

  const invoicePeriod = async (periodId, basis) => {
    try {
      const r = await PortalAPI.ceInvoicePeriod(contractId, periodId, { basis });
      refreshFin(r.financials);
      setInvoices((await PortalAPI.ceContractInvoices(contractId)).items || []);
      toast.success(r.idempotent ? "Рахунок за період уже існує" : "Рахунок за період створено");
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося виставити рахунок"); }
  };
  const invoiceAct = async (actId) => {
    try {
      const r = await PortalAPI.ceInvoiceAct(contractId, actId);
      refreshFin(r.financials);
      setInvoices((await PortalAPI.ceContractInvoices(contractId)).items || []);
      toast.success(r.idempotent ? "Рахунок за акт уже існує" : "Рахунок за акт створено");
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося виставити рахунок за акт"); }
  };
  const invoiceStatus = async (invoiceId, status, amount_paid) => {
    try {
      const r = await PortalAPI.ceInvoiceStatus(contractId, invoiceId, amount_paid != null ? { status, amount_paid } : { status });
      refreshFin(r.financials);
      setInvoices((await PortalAPI.ceContractInvoices(contractId)).items || []);
      const c = await PortalAPI.ceCompletionCheck(contractId); setComp(c);
    } catch { toast.error("Не вдалося оновити рахунок"); }
  };
  const signReport = async (reportId) => {
    try { await PortalAPI.ceSignReport(reportId); await load(); toast.success("Звіт підписано (внутрішнє затвердження)"); }
    catch { toast.error("Не вдалося підписати звіт"); }
  };

  if (loading) return <div className="p-2"><TableSkeleton rows={8} /></div>;

  return (
    <div data-testid="contract-execution-page">
      <PageHeader
        title={`Виконання договору · ${contract?.number || contractId}`}
        subtitle={contract?.title || "Contract Execution Engine"}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate("/app/operations")} data-testid="ce-back"><ArrowLeft className="mr-1 h-4 w-4" />Операції</Button>
            <Button variant="outline" size="sm" onClick={recompute} data-testid="ce-recompute"><RefreshCw className="mr-1 h-4 w-4" />Перерахувати</Button>
          </div>
        }
      />

      <Tabs defaultValue="finance" className="mt-4 w-full">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="finance" data-testid="ce-tab-finance"><Wallet className="mr-1 h-4 w-4" />Фінанси</TabsTrigger>
          <TabsTrigger value="schedule" data-testid="ce-tab-schedule"><CalendarRange className="mr-1 h-4 w-4" />Графік ({periods.length})</TabsTrigger>
          <TabsTrigger value="invoices" data-testid="ce-tab-invoices"><FileText className="mr-1 h-4 w-4" />Рахунки ({invoices.length})</TabsTrigger>
          <TabsTrigger value="ecologist" data-testid="ce-tab-ecologist"><Leaf className="mr-1 h-4 w-4" />Звіт еколога ({reports.length})</TabsTrigger>
          <TabsTrigger value="completion" data-testid="ce-tab-completion"><CheckCircle2 className="mr-1 h-4 w-4" />Завершення</TabsTrigger>
        </TabsList>

        {/* ── FINANCE ─────────────────────────────────────────── */}
        <TabsContent value="finance" className="mt-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <FinCard icon={FileText} label="Договірна" value={fin.contract_value} cur={cur} tone="slate"
              hint={fin.contract_value_frozen ? "Зафіксовано" : "Орієнтовно (план)"} />
            <FinCard icon={TrendingUp} label="Виконано" value={fin.executed_value} cur={cur} tone="green"
              hint={`План: ${money(fin.planned_total, cur)}`} />
            <FinCard icon={FileText} label="Виставлено" value={fin.invoiced_value} cur={cur} tone="blue" />
            <FinCard icon={CheckCircle2} label="Оплачено" value={fin.paid_value} cur={cur} tone="green" />
            <FinCard icon={Wallet} label="Залишок" value={fin.remaining_value} cur={cur} tone="amber"
              hint={`До оплати: ${money(fin.outstanding_value, cur)}`} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={freeze} disabled={fin.contract_value_frozen} data-testid="ce-freeze">
              <Lock className="mr-1 h-4 w-4" />{fin.contract_value_frozen ? "Суму зафіксовано" : "Зафіксувати договірну суму"}
            </Button>
            {periods.length === 0 && (
              <Button size="sm" variant="secondary" onClick={genSchedule} data-testid="ce-gen-empty">
                <Plus className="mr-1 h-4 w-4" />Згенерувати графік
              </Button>
            )}
            <span className="text-[12px] text-slate-500">Дод. роботи: <b>{money(fin.extra_total, cur)}</b></span>
          </div>
        </TabsContent>

        {/* ── SCHEDULE ────────────────────────────────────────── */}
        <TabsContent value="schedule" className="mt-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-[13px] text-slate-500">
              Тип періоду: <b>{PERIOD_TYPES.find((t) => t[0] === (contract?.schedule_config?.period_type))?.[1] || "Квартал"}</b>
              {contract?.valid_from ? ` · ${contract.valid_from} → ${contract.valid_to || "—"}` : ""}
            </div>
            <Button size="sm" variant="outline" onClick={genSchedule} data-testid="ce-regen">
              <RefreshCw className="mr-1 h-4 w-4" />Перегенерувати графік
            </Button>
          </div>
          {periods.length === 0 ? (
            <EmptyState icon={CalendarRange} title="Графік не сформовано" hint="Натисніть «Перегенерувати графік», щоб створити періоди з дат договору." testid="ce-sched-empty" />
          ) : periods.map((p) => <PeriodBlock key={p.id} period={p} cur={cur} onLine={patchLine} onAddExtra={addExtra} onDelExtra={delExtra} onInvoice={invoicePeriod} />)}
        </TabsContent>

        {/* ── INVOICES & ACTS ─────────────────────────────────── */}
        <TabsContent value="invoices" className="mt-4">
          <InvoicesPanel acts={acts} invoices={invoices} cur={cur} onInvoiceAct={invoiceAct} onStatus={invoiceStatus} scope={contract?.financial_terms?.invoice_scope} />
        </TabsContent>

        {/* ── ECOLOGIST REPORTS ───────────────────────────────── */}
        <TabsContent value="ecologist" className="mt-4">
          <EcologistPanel contractId={contractId} periods={periods} reports={reports} onChange={load} onPdf={openPdf} onSign={signReport} cur={cur} />
        </TabsContent>

        {/* ── COMPLETION ──────────────────────────────────────── */}
        <TabsContent value="completion" className="mt-4">
          <CompletionPanel contractId={contractId} comp={comp} contract={contract} onDone={load} onRefresh={async () => { const c = await PortalAPI.ceCompletionCheck(contractId); setComp(c); }} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Period block: lines (plan/fact/deviation + overrides) + extra works ── */
function PeriodBlock({ period, cur, onLine, onAddExtra, onDelExtra, onInvoice }) {
  const t = period.totals || {};
  const [extraType, setExtraType] = useState("transport");
  const [extraAmt, setExtraAmt] = useState("");
  return (
    <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4" data-testid={`ce-period-${period.label}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[15px] font-bold text-slate-900">{period.label}
          <span className="ml-2 text-[12px] font-normal text-slate-500">{period.date_from} → {period.date_to}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[12px]">
          <span className="text-slate-500">План: <b className="text-slate-800">{money(t.planned_amount, cur)}</b></span>
          <span className="text-emerald-600">Факт: <b>{money(t.executed_amount, cur)}</b></span>
          <span className={Number(t.deviation_amount) < 0 ? "text-rose-600" : "text-slate-600"}>Відхил.: <b>{money(t.deviation_amount, cur)}</b></span>
          <Button size="sm" variant="outline" data-testid={`ce-invoice-period-${period.label}`} onClick={() => onInvoice(period.id, "planned")}>
            <FileText className="mr-1 h-3.5 w-3.5" />Виставити рахунок
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Код</TableHead><TableHead>Найменування</TableHead>
              <TableHead className="w-28">План, кг</TableHead>
              <TableHead className="w-32">Ціна, грн/кг</TableHead>
              <TableHead className="w-24 text-right">Факт, кг</TableHead>
              <TableHead className="text-right">План, сума</TableHead>
              <TableHead className="text-right">Факт, сума</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(period.lines || []).map((l) => (
              <TableRow key={l.waste_code} data-testid={`ce-line-${l.waste_code}`}>
                <TableCell className="font-mono text-[12px]">{l.waste_code}</TableCell>
                <TableCell className="text-[12px] text-slate-600">{l.name}</TableCell>
                <TableCell>
                  <Input type="number" defaultValue={l.planned_kg} className="h-8 w-24" data-testid={`ce-planned-${l.waste_code}`}
                    onBlur={(e) => { const v = parseFloat(e.target.value || 0); if (v !== Number(l.planned_kg)) onLine(period.id, l.waste_code, { planned_kg: v }); }} />
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Input type="number" step="0.01" defaultValue={l.price_per_kg ?? l.calc_price_per_kg ?? ""} className="h-8 w-20" data-testid={`ce-price-${l.waste_code}`}
                      onBlur={(e) => { const v = parseFloat(e.target.value || 0); if (v !== Number(l.price_per_kg)) onLine(period.id, l.waste_code, { price_per_kg: v }); }} />
                    {l.price_source === "manual"
                      ? <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700" title={`Розрахунок: ${l.calc_price_per_kg ?? "—"}`}>ручна</Badge>
                      : <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">розрах.</Badge>}
                  </div>
                </TableCell>
                <TableCell className="text-right text-[13px]">{kg(l.actual_kg)}</TableCell>
                <TableCell className="text-right text-[13px]">{money(l.planned_amount, cur)}</TableCell>
                <TableCell className="text-right text-[13px] font-medium text-emerald-700">{money(l.actual_amount, cur)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* extra works */}
      <div className="mt-3 rounded-xl bg-slate-50 p-3">
        <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">Додаткові роботи (окремі позиції)</div>
        <div className="space-y-1">
          {(period.extra_works || []).length === 0 && <div className="text-[12px] text-slate-400">Немає</div>}
          {(period.extra_works || []).map((e) => (
            <div key={e.id} className="flex items-center justify-between text-[13px]" data-testid={`ce-extra-${e.id}`}>
              <span>
                <Badge variant="outline" className="mr-2">{EXTRA_TYPES.find((x) => x[0] === e.type)?.[1] || e.label}</Badge>
                {e.stage === "executed" ? <span className="text-emerald-600">факт</span> : <span className="text-slate-400">план</span>}
                {e.source === "act" ? <span className="ml-1 text-[11px] text-slate-400">(з акту)</span> : null}
              </span>
              <span className="flex items-center gap-2">
                <b>{money(e.amount, cur)}</b>
                {e.source !== "act" && (
                  <button onClick={() => onDelExtra(period.id, e.id)} className="text-rose-500 hover:text-rose-700" data-testid={`ce-extra-del-${e.id}`}><Trash2 className="h-3.5 w-3.5" /></button>
                )}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select className="h-8 rounded-md border border-slate-300 bg-white px-2 text-[13px]" value={extraType} onChange={(e) => setExtraType(e.target.value)} data-testid={`ce-extra-type-${period.label}`}>
            {EXTRA_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <Input type="number" placeholder="Сума, грн" value={extraAmt} onChange={(e) => setExtraAmt(e.target.value)} className="h-8 w-32" data-testid={`ce-extra-amt-${period.label}`} />
          <Button size="sm" variant="outline" data-testid={`ce-extra-add-${period.label}`}
            onClick={() => { if (!extraAmt) return; onAddExtra(period.id, { type: extraType, amount: parseFloat(extraAmt), stage: "planned" }); setExtraAmt(""); }}>
            <Plus className="mr-1 h-3.5 w-3.5" />Додати
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ── Ecologist report panel ── */
function EcologistPanel({ contractId, periods, reports, onChange, onPdf, onSign, cur }) {
  const [scope, setScope] = useState("contract");
  const [periodId, setPeriodId] = useState("");
  const [name, setName] = useState("");
  const [license, setLicense] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [recs, setRecs] = useState("");
  const [busy, setBusy] = useState(false);

  const create = async (status) => {
    setBusy(true);
    try {
      const body = {
        scope_type: scope, status,
        period_ids: scope === "period" && periodId ? [periodId] : undefined,
        ecologist: { name, license_no: license },
        conclusion, recommendations: recs,
      };
      await PortalAPI.ceCreateReport(contractId, body);
      toast.success(status === "final" ? "Фінальний звіт сформовано" : "Чернетку збережено");
      setConclusion(""); setRecs("");
      onChange();
    } catch { toast.error("Помилка формування звіту"); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-[14px] font-bold text-slate-900">Сформувати звіт еколога</div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <select className="h-9 flex-1 rounded-md border border-slate-300 px-2 text-[13px]" value={scope} onChange={(e) => setScope(e.target.value)} data-testid="ce-rep-scope">
              <option value="contract">За весь договір</option>
              <option value="period">За період (квартал/місяць)</option>
            </select>
            {scope === "period" && (
              <select className="h-9 flex-1 rounded-md border border-slate-300 px-2 text-[13px]" value={periodId} onChange={(e) => setPeriodId(e.target.value)} data-testid="ce-rep-period">
                <option value="">— період —</option>
                {periods.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            )}
          </div>
          <div className="flex gap-2">
            <Input placeholder="ПІБ еколога" value={name} onChange={(e) => setName(e.target.value)} data-testid="ce-rep-name" />
            <Input placeholder="Ліцензія №" value={license} onChange={(e) => setLicense(e.target.value)} data-testid="ce-rep-license" />
          </div>
          <Textarea placeholder="Висновок еколога" value={conclusion} onChange={(e) => setConclusion(e.target.value)} data-testid="ce-rep-conclusion" />
          <Textarea placeholder="Рекомендації" value={recs} onChange={(e) => setRecs(e.target.value)} data-testid="ce-rep-recs" />
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={busy} onClick={() => create("draft")} data-testid="ce-rep-draft">Чернетка</Button>
            <Button size="sm" disabled={busy} onClick={() => create("final")} data-testid="ce-rep-final"><Leaf className="mr-1 h-4 w-4" />Сформувати (фінал)</Button>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-[14px] font-bold text-slate-900">Звіти ({reports.length})</div>
        {reports.length === 0 ? <EmptyState icon={Recycle} title="Звітів ще немає" hint="Сформуйте звіт зліва." testid="ce-rep-empty" /> : (
          <div className="space-y-2">
            {reports.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-xl border border-slate-100 p-3" data-testid={`ce-rep-row-${r.id}`}>
                <div>
                  <div className="text-[13px] font-semibold">{r.number} {r.status === "signed" ? <Badge className="ml-1 bg-slate-800">підписано</Badge> : r.status === "final" ? <Badge className="ml-1 bg-emerald-600">фінал</Badge> : <Badge variant="outline" className="ml-1">чернетка</Badge>}</div>
                  <div className="text-[12px] text-slate-500">Факт: {kg(r.actual_kg)} кг · Методи: {(r.utilization_methods || []).join(", ") || "—"}</div>
                  {r.status === "signed" && (
                    <div className="mt-1 text-[11px] text-slate-400" title={r.content_hash}>
                      v{r.version} · {r.signed_by} · {(r.signed_at || "").slice(0, 16).replace("T", " ")} · hash {String(r.content_hash || "").slice(0, 10)}… <span className="text-slate-400">(внутрішнє затвердження, не КЕП)</span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  {r.status !== "signed" && (
                    <Button size="sm" variant="secondary" onClick={() => onSign(r.id)} data-testid={`ce-rep-sign-${r.id}`}>Підписати</Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => onPdf(r.id)} data-testid={`ce-rep-pdf-${r.id}`}><Download className="mr-1 h-4 w-4" />PDF</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Invoices & acts panel ── */
const INV_STATUS_UK = { pending: "Очікує", partial: "Часткова", paid: "Оплачено", overdue: "Прострочено", cancelled: "Скасовано" };
function InvoicesPanel({ acts, invoices, cur, onInvoiceAct, onStatus, scope }) {
  const scopeLabel = { per_period: "за період", per_act: "за акт", final: "фінальний" }[scope] || "за період";
  const signedActs = (acts || []).filter((a) => ["signed", "archived"].includes(a.status));
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-2 text-[14px] font-bold text-slate-900">Підписані акти ({signedActs.length})</div>
        <div className="mb-3 text-[12px] text-slate-500">Тип виставлення за договором: <b>{scopeLabel}</b></div>
        {signedActs.length === 0 ? <EmptyState icon={Recycle} title="Немає підписаних актів" hint="Рахунок за акт стане доступним після підписання акту." testid="ce-inv-noacts" /> : (
          <div className="space-y-2">
            {signedActs.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-slate-100 p-3" data-testid={`ce-act-row-${a.id}`}>
                <div>
                  <div className="text-[13px] font-semibold">{a.number || "Акт"} · {a.act_date || ""}</div>
                  <div className="text-[12px] text-slate-500">{kg(a.total_weight_kg)} кг · {a.utilization_method || "—"}</div>
                </div>
                <Button size="sm" variant="outline" onClick={() => onInvoiceAct(a.id)} data-testid={`ce-invoice-act-${a.id}`}>
                  <FileText className="mr-1 h-4 w-4" />Рахунок за акт
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 text-[14px] font-bold text-slate-900">Рахунки договору ({invoices.length})</div>
        {invoices.length === 0 ? <EmptyState icon={FileText} title="Рахунків ще немає" hint="Виставте рахунок за період (вкладка «Графік») або за акт." testid="ce-inv-empty" /> : (
          <div className="space-y-2">
            {invoices.map((inv) => (
              <div key={inv.id} className="rounded-xl border border-slate-100 p-3" data-testid={`ce-invoice-${inv.id}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[13px] font-semibold">{inv.invoice_number || inv.number || inv.id}
                      <Badge variant="outline" className="ml-2">{inv.invoice_scope === "per_act" ? "за акт" : inv.invoice_scope === "final" ? "фінал" : "за період"}</Badge>
                    </div>
                    <div className="text-[12px] text-slate-500">{money(inv.amount ?? inv.total, cur)} · <b className={inv.status === "paid" ? "text-emerald-600" : inv.status === "cancelled" ? "text-slate-400" : "text-amber-600"}>{INV_STATUS_UK[inv.status] || inv.status}</b>{inv.amount_paid != null ? ` · оплачено ${money(inv.amount_paid, cur)}` : ""}</div>
                  </div>
                </div>
                {inv.status !== "cancelled" && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => onStatus(inv.id, "paid")} data-testid={`ce-inv-paid-${inv.id}`}>Оплачено</Button>
                    <Button size="sm" variant="outline" onClick={() => { const v = window.prompt("Сума часткової оплати:"); if (v) onStatus(inv.id, "partial", parseFloat(v)); }} data-testid={`ce-inv-partial-${inv.id}`}>Часткова</Button>
                    <Button size="sm" variant="ghost" className="text-rose-500" onClick={() => onStatus(inv.id, "cancelled")} data-testid={`ce-inv-cancel-${inv.id}`}>Скасувати</Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Completion wizard ── */
function CompletionPanel({ contractId, comp, contract, onDone, onRefresh }) {
  const [busy, setBusy] = useState(false);
  if (!comp) return <EmptyState icon={CheckCircle2} title="Немає даних перевірки" hint="Оновіть сторінку." testid="ce-comp-empty" />;
  const closeContract = async () => {
    setBusy(true);
    try { await PortalAPI.ceComplete(contractId, true); toast.success("Договір закрито"); onDone(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не можна закрити договір"); }
    finally { setBusy(false); }
  };
  const closed = contract?.status === "closed";
  return (
    <div className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-5" data-testid="ce-completion">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-[15px] font-bold text-slate-900">Майстер завершення договору</div>
        <Button size="sm" variant="ghost" onClick={onRefresh}><RefreshCw className="h-4 w-4" /></Button>
      </div>
      <div className="space-y-2">
        {comp.checks.map((c) => (
          <div key={c.key} className="flex items-center justify-between rounded-xl border border-slate-100 p-3" data-testid={`ce-check-${c.key}`}>
            <span className="flex items-center gap-2 text-[13px]">
              {c.ok ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-rose-500" />}
              {c.label}
            </span>
            <span className="text-[12px] text-slate-500">{c.detail}</span>
          </div>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-3">
        <Button disabled={!comp.can_close || busy || closed} onClick={closeContract} data-testid="ce-complete-btn">
          <CheckCircle2 className="mr-1 h-4 w-4" />{closed ? "Договір закрито" : "Підтвердити та закрити договір"}
        </Button>
        {!comp.ready && !closed && <span className="text-[12px] text-rose-500">Виконайте всі пункти, щоб закрити договір</span>}
      </div>
    </div>
  );
}
