// IBAN-first Invoices / Payments (contract -> issue IBAN -> client proof -> confirm)
// Client is shown as "Company — email" (email links to Customer 360). Search is
// backend-driven (email / company / name / № / contract / request).
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Receipt, Plus, AlertTriangle, CheckCircle2, Clock, Search, FileDown, ExternalLink, Sparkles, History, FileSignature, ShieldCheck } from "lucide-react";
import { CrmAPI, FilesAPI, openStoredFile } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import DocumentTimeline from "@/components/portal/DocumentTimeline";
import CustomerLabel from "@/components/portal/CustomerLabel";
import { StatusPill, InvoiceDialog, ManageDrawer, money } from "@/components/portal/InvoiceManage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

export default function CrmInvoices() {
  useSeo("Рахунки · CRM", "Рахунки / Оплата по IBAN · договір, виставлення, підтвердження.");
  const { user } = useAuth();
  const canCreate = ["admin", "master_admin", "owner", "team_lead", "manager"].includes(user?.role);
  const [list, setList] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [overdue, setOverdue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(false);
  const [manage, setManage] = useState(null);

  const load = useCallback(async (searchQ = "") => {
    setLoading(true);
    try {
      const [m, a, o] = await Promise.all([
        CrmAPI.managerInvoicesMy(searchQ ? { q: searchQ } : {}),
        CrmAPI.invoiceAnalytics().catch(() => ({})),
        CrmAPI.invoicesOverdue().catch(() => ({})),
      ]);
      setList(m.items || m.data || []);
      setAnalytics(a.analytics || null);
      setOverdue(o.data || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Debounced backend search
  useEffect(() => {
    const t = setTimeout(() => { load(q.trim()); }, 350);
    return () => clearTimeout(t);
  }, [q, load]);

  useEffect(() => {
    if (manage) {
      const fresh = list.find((x) => x.id === manage.id);
      if (fresh && fresh !== manage) setManage(fresh);
    }
  }, [list]); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => ({
    all: list.length,
    sent: list.filter((x) => x.status === "sent").length,
    awaiting: list.filter((x) => x.status === "awaiting_confirmation").length,
    pending: list.filter((x) => x.status === "pending").length,
    paid: list.filter((x) => x.status === "paid").length,
  }), [list]);

  const filtered = useMemo(() => {
    let r = list;
    if (tab === "awaiting") r = r.filter((x) => x.status === "awaiting_confirmation");
    else if (tab !== "all") r = r.filter((x) => x.status === tab);
    return r;
  }, [list, tab]);

  const [pdfBusy, setPdfBusy] = useState(null);
  const [historyInv, setHistoryInv] = useState(null);
  const generatePdf = async (inv) => {
    setPdfBusy(inv.id);
    try {
      const r = await FilesAPI.generateInvoice(inv.id);
      toast.success("PDF рахунку згенеровано");
      setList((prev) => prev.map((x) => (x.id === inv.id ? { ...x, file_id: r.file?.url || x.file_id } : x)));
      if (r.file?.id) openStoredFile(r.file.id);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося згенерувати PDF"); } finally { setPdfBusy(null); }
  };

  const ana = analytics || {};
  return (
    <div data-testid="portal-crm-invoices">
      <PageHeader title="Рахунки" subtitle="Договір → виставлення IBAN → підтвердження оплати" actions={canCreate && <Button onClick={() => setDialog(true)} className="gap-2" data-testid="inv-create-button"><Plus className="h-4 w-4" /> Новий рахунок</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Receipt} label="Усього" value={ana.total ?? list.length} testid="inv-kpi-total" />
        <StatCard icon={Clock} label="На перевірці" value={counts.awaiting} testid="inv-kpi-awaiting" />
        <StatCard icon={CheckCircle2} label="Оплачено" value={ana.paid ?? counts.paid} testid="inv-kpi-paid" />
        <StatCard icon={AlertTriangle} label="Прострочено" value={ana.overdue ?? overdue.length} testid="inv-kpi-overdue" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="all" data-testid="inv-tab-all">Усі ({counts.all})</TabsTrigger>
            <TabsTrigger value="pending" data-testid="inv-tab-pending">Чернетки ({counts.pending})</TabsTrigger>
            <TabsTrigger value="sent" data-testid="inv-tab-sent">До сплати ({counts.sent})</TabsTrigger>
            <TabsTrigger value="awaiting" data-testid="inv-tab-awaiting">На перевірці ({counts.awaiting})</TabsTrigger>
            <TabsTrigger value="paid" data-testid="inv-tab-paid">Оплачено ({counts.paid})</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук: email, компанія, ім'я, №, договір, заявка…" className="pl-9" data-testid="inv-search" />
        </div>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
          : filtered.length === 0 ? <EmptyState icon={Receipt} title="Рахунків немає" hint="Створіть перший рахунок або змініть фільтр." action={canCreate && <Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Створити</Button>} testid="inv-empty" />
          : (
            <Table>
              <TableHeader><TableRow><TableHead>№</TableHead><TableHead>Клієнт</TableHead><TableHead className="text-right">Сума</TableHead><TableHead>Створено</TableHead><TableHead>Статус</TableHead><TableHead className="w-[260px] text-right">Дії</TableHead></TableRow></TableHeader>
              <TableBody>{filtered.map((inv) => (
                <TableRow key={inv.id} data-testid="inv-row">
                  <TableCell className="font-mono text-xs text-slate-700">{inv.number || inv.id?.slice(-8)}</TableCell>
                  <TableCell className="max-w-[260px]"><CustomerLabel customer={inv.customer || inv} /></TableCell>
                  <TableCell className="text-right font-mono font-semibold text-slate-900">{money(inv.amount || inv.total, inv.currency || "UAH")}</TableCell>
                  <TableCell className="text-sm text-slate-500">{fmtDate(inv.created_at)}</TableCell>
                  <TableCell><StatusPill s={inv.status} /></TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button size="sm" className="gap-1.5" onClick={() => setManage(inv)} data-testid="inv-manage">
                        {inv.status === "awaiting_confirmation" ? <><ShieldCheck className="h-3.5 w-3.5" /> Перевірити</> : <><FileSignature className="h-3.5 w-3.5" /> Керувати</>}
                      </Button>
                      <Button variant="ghost" size="icon" title="Історія" onClick={() => setHistoryInv(inv)} data-testid="inv-open-history"><History className="h-4 w-4" /></Button>
                      {inv.file_id && <Button variant="ghost" size="icon" title="Відкрити PDF" onClick={() => openStoredFile(inv.file_id)}><ExternalLink className="h-4 w-4" /></Button>}
                      <Button variant="ghost" size="icon" title="Згенерувати PDF" onClick={() => generatePdf(inv)} disabled={pdfBusy === inv.id} data-testid="inv-generate-pdf">{pdfBusy === inv.id ? <FileDown className="h-4 w-4 animate-pulse" /> : <Sparkles className="h-4 w-4" />}</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          )}
      </div>

      <InvoiceDialog open={dialog} onOpenChange={setDialog} onSaved={() => load(q.trim())} />
      <ManageDrawer invoice={manage} onClose={() => setManage(null)} onChanged={() => load(q.trim())} />

      <Dialog open={!!historyInv} onOpenChange={(o) => !o && setHistoryInv(null)}>
        <DialogContent className="max-w-2xl" data-testid="inv-history-dialog">
          <DialogHeader>
            <DialogTitle>Історія документа · {historyInv?.number || historyInv?.id}</DialogTitle>
            <DialogDescription>Життєвий цикл, версії та переходи статусів цього рахунку.</DialogDescription>
          </DialogHeader>
          {historyInv && <div className="pt-2"><DocumentTimeline entityType="invoice" entityId={historyInv.id} onChanged={() => load(q.trim())} /></div>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
