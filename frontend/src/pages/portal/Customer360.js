// Customer 360 (staff) — end-to-end history of ONE client (contact person).
// Distinct from Company 360 (the legal entity) but cross-linked to it.
// Reuses existing aggregation endpoints; no new invoice/contract engine.
import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft, Mail, Phone, Building2, Hash, User, ShieldCheck, Clock, Receipt,
  FileText, FileSignature, ClipboardList, Recycle, MessageSquare, Plus,
  ExternalLink, Sparkles, FileDown, Landmark, AlertTriangle, CheckCircle2, Send, Bell, Upload,
  Trash2, Download, Cpu, HardDriveUpload,
} from "lucide-react";
import { CrmAPI, FilesAPI, openStoredFile, api } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDate, fmtDateTime } from "@/lib/portalMeta";
import { StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { StatusPill, InvoiceDialog, ManageDrawer, money } from "@/components/portal/InvoiceManage";
import { toCustomerDTO } from "@/lib/customerLabel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { toast } from "@/components/ui/sonner";

const StatusChip = ({ s }) => <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-700">{s || "—"}</span>;

// Reusable drag & drop + click upload zone
function DropZone({ onFile, busy, testid, hint }) {
  const [over, setOver] = React.useState(false);
  const ref = React.useRef(null);
  return (
    <div
      onClick={() => ref.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer?.files?.[0]; if (f) onFile(f); }}
      className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-4 text-sm transition ${over ? "border-emerald-500 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-500 hover:border-emerald-300 hover:bg-emerald-50/40"}`}
      data-testid={testid}
    >
      <input ref={ref} type="file" className="hidden" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.xls,.xlsx" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      <Upload className={`h-4 w-4 ${busy ? "animate-pulse" : ""}`} />
      <span>{busy ? "Завантаження…" : (hint || "Перетягніть файл сюди або натисніть, щоб обрати")}</span>
    </div>
  );
}

export default function Customer360() {
  const { id } = useParams();
  useSeo("Клієнт · CRM", "Наскрізна історія клієнта — заявки, рахунки, документи, договори, акти.");

  const [customer, setCustomer] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const [tab, setTab] = useState("overview");

  // tab datasets
  const [requests, setRequests] = useState(null);
  const [invoices, setInvoices] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [contracts, setContracts] = useState(null);
  const [acts, setActs] = useState(null);
  const [activity, setActivity] = useState(null);

  const [invDialog, setInvDialog] = useState(false);
  const [manage, setManage] = useState(null);
  const [comment, setComment] = useState("");
  const [pdfBusy, setPdfBusy] = useState(null);
  const [cardBusy, setCardBusy] = useState(false);
  const [debtBusy, setDebtBusy] = useState(false);
  const [actFilter, setActFilter] = useState("all");
  const [uploadingKind, setUploadingKind] = useState(null);
  const [showActForm, setShowActForm] = useState(false);
  const [showReportForm, setShowReportForm] = useState(false);
  const [delDialog, setDelDialog] = useState(null); // { kind, fileId, title, reason }
  const [delBusy, setDelBusy] = useState(false);
  const [ecoContracts, setEcoContracts] = useState([]);

  const reloadAfterUpload = async (kind) => {
    if (kind === "document") { const d = await CrmAPI.customerDocuments(id); setDocuments(d.items || []); }
    else {
      const r = await CrmAPI.customerEcoActs(id); setActs(r);
      // keep the general Documents view in sync (same File Layer)
      try { const d = await CrmAPI.customerDocuments(id); setDocuments(d.items || []); } catch {}
    }
  };

  const uploadFile = async (kind, file, meta) => {
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) { toast.error("Файл завеликий (макс. 25 МБ)"); return; }
    setUploadingKind(kind);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("purpose", kind);              // act | ecologist_report | document
      fd.append("entity_type", "customer");
      fd.append("entity_id", id);
      fd.append("title", (meta && meta.title) || file.name);
      if (meta && Object.keys(meta).length) fd.append("meta", JSON.stringify(meta));
      await FilesAPI.upload(fd);
      await reloadAfterUpload(kind);
      const labels = { act: "Акт завантажено", ecologist_report: "Звіт еколога завантажено", document: "Документ завантажено" };
      toast.success(labels[kind] || "Файл завантажено");
      if (kind === "ecologist_report") setShowReportForm(false);
      if (kind === "act") setShowActForm(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося завантажити файл");
    } finally {
      setUploadingKind(null);
    }
  };

  // Open the confirm dialog for a manual upload deletion.
  const askDeleteFile = (kind, file) => {
    setDelDialog({ kind, fileId: file.file_id || file.id, title: file.title || file.filename || "файл", reason: "" });
  };

  const confirmDeleteFile = async () => {
    if (!delDialog?.fileId) return;
    setDelBusy(true);
    try {
      await api.delete(`/customers/${id}/files/${delDialog.fileId}`, { data: { reason: delDialog.reason || undefined } });
      await reloadAfterUpload(delDialog.kind);
      toast.success("Файл видалено");
      setDelDialog(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося видалити файл");
    } finally { setDelBusy(false); }
  };

  const sendDebtReminder = async () => {
    setDebtBusy(true);
    try {
      const r = await api.post(`/customers/${id}/debt-reminder`, {});
      const d = r.data || {};
      if (d.delivered) toast.success(d.message || "Нагадування надіслано");
      else if (d.status === "failed") toast.error(d.message || "Помилка надсилання нагадування");
      else toast(d.message || "Нагадування поставлено в чергу", { icon: "📨" });
      try { const a = await CrmAPI.customerEcoActivity(id); setActivity({ events: a.events || [], comments: a.comments || (activity?.comments || []) }); setTab("activity"); } catch {}
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося надіслати нагадування");
    } finally { setDebtBusy(false); }
  };

  const exportCard = async () => {
    setCardBusy(true);
    try {
      const r = await api.get(`/customers/${id}/card.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = `customer-card-${id}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      toast.success("Картку клієнта експортовано в PDF");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося сформувати PDF");
    } finally { setCardBusy(false); }
  };

  const downloadFile = async (file) => {
    const fid = file.file_id || file.id;
    if (!fid) return;
    try {
      const blob = await FilesAPI.download(fid);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = file.filename || file.title || "file";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (e) {
      toast.error("Не вдалося завантажити файл");
    }
  };

  const dto = customer ? toCustomerDTO(customer) : null;

  const loadCore = useCallback(async () => {
    setLoading(true); setErr(false);
    try {
      const [c, ov] = await Promise.all([
        CrmAPI.customerGet(id),
        CrmAPI.customerOverview(id).catch(() => null),
      ]);
      setCustomer(c.customer || c.data || null);
      setOverview(ov?.summary || null);
      if (ov?.customer) setCustomer((prev) => prev || ov.customer);
    } catch { setErr(true); } finally { setLoading(false); }
  }, [id]);

  useEffect(() => { loadCore(); }, [loadCore]);

  const loadInvoices = useCallback(async () => {
    try {
      const r = await CrmAPI.customerInvoices(id);
      // attach a stable customer DTO so the manage drawer shows "company — email"
      const items = (r.items || []).map((iv) => ({ ...iv, customer: dto || undefined }));
      setInvoices(items);
    } catch { setInvoices([]); }
  }, [id, dto]);

  const loadTab = useCallback(async (t) => {
    try {
      if (t === "requests" && requests === null) { const r = await CrmAPI.customerEcoRequests(id); setRequests(r.items || []); }
      if (t === "invoices" && invoices === null) { await loadInvoices(); }
      if (t === "documents" && documents === null) { const r = await CrmAPI.customerDocuments(id); setDocuments(r.items || []); }
      if (t === "contracts" && contracts === null) { const r = await CrmAPI.customerEcoContracts(id); setContracts(r.items || []); }
      if (t === "acts" && acts === null) {
        const r = await CrmAPI.customerEcoActs(id); setActs(r);
        try { const cc = await CrmAPI.customerEcoContracts(id); setEcoContracts(cc.items || []); } catch {}
      }
      if (t === "activity" && activity === null) {
        const [a, cm] = await Promise.all([CrmAPI.customerEcoActivity(id), CrmAPI.customerComments(id).catch(() => ({ items: [] }))]);
        setActivity({ events: a.events || [], comments: (a.comments && a.comments.length ? a.comments : (cm.items || cm.comments || [])) });
      }
    } catch { /* leave empty */ }
  }, [id, requests, invoices, documents, contracts, acts, activity, loadInvoices]);

  useEffect(() => { loadTab(tab); }, [tab, loadTab]);

  const refreshInvoices = () => { loadInvoices(); loadCore(); };

  const genPdf = async (kind, entity) => {
    setPdfBusy(entity.id);
    try {
      const api = kind === "invoice" ? FilesAPI.generateInvoice : kind === "act" ? FilesAPI.generateAct : FilesAPI.generateContract;
      const r = await api(entity.id);
      toast.success("PDF згенеровано");
      if (r.file?.id) openStoredFile(r.file.id);
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося згенерувати PDF"); } finally { setPdfBusy(null); }
  };

  const addComment = async () => {
    if (!comment.trim()) return;
    try {
      await CrmAPI.customerAddComment(id, { body: comment.trim() });
      setComment("");
      setActivity(null); loadTab("activity");
      toast.success("Коментар додано");
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося додати коментар"); }
  };

  if (loading) return <div data-testid="portal-customer360"><div className="mb-6 h-8 w-64 animate-pulse rounded bg-[hsl(var(--secondary))]" /><TableSkeleton rows={6} /></div>;
  if (err || !customer) return <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#991B1B]" data-testid="customer360-error">Клієнта не знайдено або немає доступу. <Link to="/app/crm/invoices" className="font-medium underline">До рахунків</Link></div>;

  const ov = overview || {};
  const cur = ov.currency || "UAH";

  return (
    <div data-testid="portal-customer360">
      <Link to="/app/crm/invoices" className="mb-4 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-[hsl(var(--primary))]" data-testid="customer360-back"><ArrowLeft className="h-4 w-4" /> Назад</Link>

      {/* Header */}
      <div className="mb-6 rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><User className="h-5 w-5" /></span>
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-slate-900" data-testid="customer360-name">{dto?.full_name || dto?.company_name || "Клієнт"}</h1>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                  {customer.email && <a href={`mailto:${customer.email}`} className="inline-flex items-center gap-1 text-emerald-700 hover:underline" data-testid="customer360-email"><Mail className="h-3.5 w-3.5" />{customer.email}</a>}
                  {customer.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{customer.phone}</span>}
                  {customer.company_name && (customer.company_id
                    ? <Link to={`/app/companies/${customer.company_id}`} className="inline-flex items-center gap-1 text-slate-700 hover:text-emerald-700 hover:underline" data-testid="customer360-company"><Building2 className="h-3.5 w-3.5" />{customer.company_name}</Link>
                    : <span className="inline-flex items-center gap-1"><Building2 className="h-3.5 w-3.5" />{customer.company_name}</span>)}
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1"><Hash className="h-3 w-3" />{customer.id}</span>
              <span>Роль: {customer.role || "customer"}</span>
              <span>Статус: <b className="text-slate-700">{customer.status || "active"}</b></span>
              <span>Створено: {fmtDate(customer.created_at)}</span>
              {customer.managerId && <span>Менеджер: {customer.managerEmail || customer.managerId}</span>}
            </div>
          </div>

          {/* Quick actions */}
          <div className="flex flex-wrap items-center gap-2">
            {customer.email && <a href={`mailto:${customer.email}`}><Button variant="outline" size="sm" className="gap-1.5" data-testid="qa-email"><Mail className="h-3.5 w-3.5" /> Email</Button></a>}
            <Button size="sm" className="gap-1.5" onClick={() => setInvDialog(true)} data-testid="qa-invoice"><Receipt className="h-3.5 w-3.5" /> Виставити рахунок</Button>
            {customer.company_id && <Link to={`/app/companies/${customer.company_id}`}><Button variant="outline" size="sm" className="gap-1.5" data-testid="qa-request"><ClipboardList className="h-3.5 w-3.5" /> Заявка / Об'єкт</Button></Link>}
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => { setTab("activity"); }} data-testid="qa-comment"><MessageSquare className="h-3.5 w-3.5" /> Коментар</Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={exportCard} disabled={cardBusy} data-testid="qa-export-pdf"><FileDown className={`h-3.5 w-3.5 ${cardBusy ? "animate-pulse" : ""}`} /> {cardBusy ? "Формуємо…" : "Експорт PDF"}</Button>
            <Button variant="outline" size="sm" className="gap-1.5 border-red-200 text-red-600 hover:bg-red-50" onClick={sendDebtReminder} disabled={debtBusy} data-testid="qa-debt-reminder"><Bell className={`h-3.5 w-3.5 ${debtBusy ? "animate-pulse" : ""}`} /> {debtBusy ? "Надсилаємо…" : "Нагадати про борг"}</Button>
          </div>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4 flex flex-wrap">
          <TabsTrigger value="overview" data-testid="c360-tab-overview">Огляд</TabsTrigger>
          <TabsTrigger value="requests" data-testid="c360-tab-requests">Заявки</TabsTrigger>
          <TabsTrigger value="invoices" data-testid="c360-tab-invoices">Рахунки</TabsTrigger>
          <TabsTrigger value="documents" data-testid="c360-tab-documents">Документи</TabsTrigger>
          <TabsTrigger value="contracts" data-testid="c360-tab-contracts">Договори</TabsTrigger>
          <TabsTrigger value="acts" data-testid="c360-tab-acts">Акти / Звіти</TabsTrigger>
          <TabsTrigger value="activity" data-testid="c360-tab-activity">Активність</TabsTrigger>
        </TabsList>

        {/* ── Overview ── */}
        <TabsContent value="overview">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={ClipboardList} label="Заявок" value={ov.requests_total ?? 0} testid="c360-kpi-requests" />
            <StatCard icon={FileSignature} label="Активні договори" value={ov.active_contracts ?? 0} testid="c360-kpi-contracts" />
            <StatCard icon={Receipt} label="Виставлено" value={money(ov.invoiced_amount, cur)} testid="c360-kpi-invoiced" />
            <StatCard icon={CheckCircle2} label="Оплачено" value={money(ov.paid_amount, cur)} testid="c360-kpi-paid" />
            <StatCard icon={Landmark} label="Борг" value={money(ov.debt_amount, cur)} testid="c360-kpi-debt" />
            <StatCard icon={AlertTriangle} label="Прострочено" value={money(ov.overdue_amount, cur)} testid="c360-kpi-overdue" />
            <StatCard icon={Clock} label="Відкриті задачі" value={ov.open_tasks ?? 0} testid="c360-kpi-tasks" />
            <StatCard icon={Sparkles} label="Остання активність" value={ov.last_activity ? fmtDate(ov.last_activity) : "—"} testid="c360-kpi-last" />
          </div>
        </TabsContent>

        {/* ── Requests ── */}
        <TabsContent value="requests">
          <SectionTable
            data={requests}
            empty={{ icon: ClipboardList, title: "Заявок немає", hint: "У цього клієнта ще немає заявок на вивезення." }}
            head={["№", "Статус", "Об'єкт", "Відходи", "Сума", "Дата"]}
            row={(r) => [
              <span className="font-mono text-xs">{r.number || r.id?.slice(-8)}</span>,
              <StatusChip s={r.status} />,
              r.object_name || r.object_id || "—",
              (r.waste_codes || []).join(", ") || r.waste_name || "—",
              r.amount ? money(r.amount, r.currency || cur) : "—",
              fmtDate(r.created_at),
            ]}
          />
        </TabsContent>

        {/* ── Invoices ── */}
        <TabsContent value="invoices">
          <div className="mb-3 flex justify-end"><Button size="sm" className="gap-1.5" onClick={() => setInvDialog(true)} data-testid="c360-inv-create"><Plus className="h-3.5 w-3.5" /> Новий рахунок</Button></div>
          <SectionTable
            data={invoices}
            empty={{ icon: Receipt, title: "Рахунків немає", hint: "Виставте перший рахунок цьому клієнту." }}
            head={["№", "Статус", "Сума", "Створено", "Дії"]}
            row={(iv) => [
              <span className="font-mono text-xs">{iv.number || iv.id?.slice(-8)}</span>,
              <StatusPill s={iv.status} />,
              <span className="font-mono font-semibold">{money(iv.amount || iv.total, iv.currency || cur)}</span>,
              fmtDate(iv.created_at),
              <div className="flex items-center justify-end gap-1">
                <Button size="sm" className="gap-1.5" onClick={() => setManage({ ...iv, customer: dto })} data-testid="c360-inv-manage">{iv.status === "awaiting_confirmation" ? <><ShieldCheck className="h-3.5 w-3.5" />Перевірити</> : <><FileSignature className="h-3.5 w-3.5" />Керувати</>}</Button>
                {iv.file_id && <Button variant="ghost" size="icon" title="Відкрити PDF" onClick={() => openStoredFile(iv.file_id)}><ExternalLink className="h-4 w-4" /></Button>}
                <Button variant="ghost" size="icon" title="Згенерувати PDF" onClick={() => genPdf("invoice", iv)} disabled={pdfBusy === iv.id}>{pdfBusy === iv.id ? <FileDown className="h-4 w-4 animate-pulse" /> : <Sparkles className="h-4 w-4" />}</Button>
              </div>,
            ]}
            lastRight
          />
        </TabsContent>

        {/* ── Documents (general File Layer view) ── */}
        <TabsContent value="documents">
          <SectionTable
            data={documents}
            empty={{ icon: FileText, title: "Документів немає", hint: "Договори, рахунки, акти, звіти та інші файли з'являться тут." }}
            head={["Назва", "Тип", "Джерело", "Період", "Статус", "Дата", ""]}
            row={(d) => [
              d.name || d.title || d.file_name || "Документ",
              <StatusChip s={d.type || d.kind || "file"} />,
              <SourceBadge uploaded={d.uploaded || d.source === "uploaded"} />,
              d.period_label || "—",
              <StatusChip s={d.status || d.sign_status || "—"} />,
              fmtDate(d.doc_date || d.created_at),
              <div className="flex justify-end gap-1">
                {(d.url || d.file_url || d.download_url)
                  ? <a className="text-emerald-700 underline text-sm" href={(d.url || d.file_url || d.download_url)} target="_blank" rel="noreferrer">Відкрити</a>
                  : (d.file_id ? <Button variant="ghost" size="sm" className="gap-1" onClick={() => openStoredFile(d.file_id)}><ExternalLink className="h-3.5 w-3.5" />Відкрити</Button> : "—")}
                {d.file_id && <Button variant="ghost" size="icon" title="Завантажити" onClick={() => downloadFile(d)}><Download className="h-4 w-4" /></Button>}
              </div>,
            ]}
            lastRight
          />
        </TabsContent>

        {/* ── Contracts ── */}
        <TabsContent value="contracts">
          <SectionTable
            data={contracts}
            empty={{ icon: FileSignature, title: "Договорів немає", hint: "Договори з'являться тут після створення." }}
            head={["№", "Статус", "Сума", "Оплачено", "Залишок", "Дата", ""]}
            row={(c) => [
              <span className="font-mono text-xs">{c.number || c.contract_number || c.id?.slice(-8)}</span>,
              <StatusChip s={c.status} />,
              money(c._value, c.currency || cur),
              money(c._paid, c.currency || cur),
              money(c._remaining, c.currency || cur),
              fmtDate(c.created_at),
              <Link to={`/app/operations/contracts/${c.id}`} className="text-emerald-700 underline">Виконання</Link>,
            ]}
            lastRight
          />
        </TabsContent>

        {/* ── Acts / Reports (profile view over the same File Layer) ── */}
        <TabsContent value="acts">
          <div className="space-y-6">
            {/* Acts */}
            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800"><Recycle className="h-4 w-4" /> Акти утилізації</h3>
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setShowActForm((v) => !v)} data-testid="c360-upload-act">
                  <Upload className="h-3.5 w-3.5" /> Завантажити акт
                </Button>
              </div>
              {showActForm && (
                <UploadDocPanel
                  kind="act"
                  busy={uploadingKind === "act"}
                  contracts={ecoContracts}
                  onUpload={uploadFile}
                  onCancel={() => setShowActForm(false)}
                />
              )}
              <FileTable
                data={acts?.acts}
                empty={{ icon: Recycle, title: "Актів немає", hint: "Завантажте акт з комп'ютера або згенеруйте після виконання робіт." }}
                kind="act"
                contracts={ecoContracts}
                onOpen={(a) => openStoredFile(a.file_id)}
                onDownload={downloadFile}
                onDelete={askDeleteFile}
                onGenPdf={(a) => genPdf("act", a)}
                pdfBusy={pdfBusy}
              />
            </div>
            {/* Ecologist reports */}
            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800"><FileText className="h-4 w-4" /> Звіти еколога</h3>
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setShowReportForm((v) => !v)} data-testid="c360-upload-report">
                  <Upload className="h-3.5 w-3.5" /> Завантажити звіт
                </Button>
              </div>
              {showReportForm && (
                <UploadDocPanel
                  kind="ecologist_report"
                  busy={uploadingKind === "ecologist_report"}
                  contracts={ecoContracts}
                  onUpload={uploadFile}
                  onCancel={() => setShowReportForm(false)}
                />
              )}
              <FileTable
                data={acts?.reports}
                empty={{ icon: FileText, title: "Звітів немає", hint: "Завантажте звіт еколога з комп'ютера (PDF, DOCX, зображення)." }}
                kind="ecologist_report"
                contracts={ecoContracts}
                onOpen={(r) => openStoredFile(r.file_id)}
                onDownload={downloadFile}
                onDelete={askDeleteFile}
                onGenPdf={null}
                pdfBusy={pdfBusy}
              />
            </div>
          </div>
        </TabsContent>

        {/* ── Activity ── */}
        <TabsContent value="activity">
          <div className="mb-4 rounded-xl border border-slate-200 p-4">
            <div className="mb-2 text-sm font-semibold text-slate-800">Додати коментар</div>
            <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Внутрішня нотатка по клієнту…" className="mb-2" data-testid="c360-comment-input" />
            <div className="flex justify-end"><Button size="sm" className="gap-1.5" onClick={addComment} data-testid="c360-comment-add"><Send className="h-3.5 w-3.5" /> Додати</Button></div>
          </div>
          {activity === null ? <TableSkeleton rows={4} /> : (() => {
            const bucketOf = (it) => {
              const k = it.kind || it._kind || "event";
              if (k === "invoice" || k === "payment" || k === "comment") return k;
              const s = `${it.type || ""} ${it.title || ""}`;
              if (/contract|догов[іо]р/i.test(s)) return "contract";
              return "event";
            };
            const merged = [...(activity.comments || []).map((c) => ({ ...c, kind: "comment" })), ...(activity.events || [])]
              .map((it) => ({ ...it, _bucket: bucketOf(it) }))
              .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
            const counts = merged.reduce((m, it) => { m[it._bucket] = (m[it._bucket] || 0) + 1; m.all = (m.all || 0) + 1; return m; }, {});
            const chips = [
              { key: "all", label: "Всі" },
              { key: "invoice", label: "Рахунки" },
              { key: "payment", label: "Оплати" },
              { key: "contract", label: "Договори" },
              { key: "comment", label: "Коментарі" },
            ];
            const shown = actFilter === "all" ? merged : merged.filter((it) => it._bucket === actFilter);
            return (
            <div className="space-y-2">
              <div className="mb-1 flex flex-wrap gap-1.5" data-testid="c360-activity-filters">
                {chips.map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    onClick={() => setActFilter(c.key)}
                    data-testid={`c360-actfilter-${c.key}`}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition ${actFilter === c.key ? "border-emerald-500 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"}`}
                  >
                    {c.label}{counts[c.key] ? ` · ${counts[c.key]}` : ""}
                  </button>
                ))}
              </div>
              {shown
                .slice(0, 200)
                .map((it, i) => {
                  const kind = it.kind || it._kind || "event";
                  const style = {
                    comment: { cls: "bg-blue-50 text-blue-600", Icon: MessageSquare },
                    invoice: { cls: "bg-amber-50 text-amber-600", Icon: Receipt },
                    payment: { cls: "bg-emerald-50 text-emerald-600", Icon: Landmark },
                    event: { cls: "bg-slate-100 text-slate-500", Icon: Clock },
                  }[kind] || { cls: "bg-slate-100 text-slate-500", Icon: Clock };
                  const Icon = style.Icon;
                  return (
                  <div key={it.id || i} className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white p-3" data-testid="c360-activity-item">
                    <span className={`mt-0.5 flex h-7 w-7 items-center justify-center rounded-full ${style.cls}`}><Icon className="h-3.5 w-3.5" /></span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-slate-800">{it.body || it.text || it.title || it.action || it.type || "Подія"}</div>
                      <div className="text-xs text-slate-400">{it.author_name || it.author_email || it.author || it.by || ""}{(it.author_name || it.author_email || it.author || it.by) ? " · " : ""}{fmtDateTime(it.created_at)}</div>
                    </div>
                  </div>
                  );
                })}
              {!merged.length && <EmptyState icon={MessageSquare} title="Активності немає" hint="Коментарі, зміни статусів та події з'являться тут." />}
              {merged.length > 0 && shown.length === 0 && <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400" data-testid="c360-activity-empty-filter">Немає подій цього типу</div>}
            </div>
            );
          })()}
        </TabsContent>
      </Tabs>

      <InvoiceDialog open={invDialog} onOpenChange={setInvDialog} lockedCustomer={dto} onSaved={() => { setInvoices(null); loadTab("invoices"); loadCore(); }} />
      <ManageDrawer invoice={manage} onClose={() => setManage(null)} onChanged={refreshInvoices} />
      <DeleteFileDialog
        state={delDialog}
        busy={delBusy}
        onReason={(v) => setDelDialog((d) => (d ? { ...d, reason: v } : d))}
        onCancel={() => setDelDialog(null)}
        onConfirm={confirmDeleteFile}
      />
    </div>
  );
}

// Small generic table renderer with loading + empty states.
function SectionTable({ data, head, row, empty, lastRight }) {
  if (data === null || data === undefined) return <TableSkeleton rows={5} />;
  if (!data.length) return <EmptyState icon={empty.icon} title={empty.title} hint={empty.hint} />;
  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
      <Table>
        <TableHeader><TableRow>{head.map((h, i) => <TableHead key={i} className={lastRight && i === head.length - 1 ? "text-right" : ""}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {data.map((item, ri) => {
            const cells = row(item);
            return <TableRow key={item.id || ri}>{cells.map((c, ci) => <TableCell key={ci} className={lastRight && ci === cells.length - 1 ? "text-right" : ""}>{c}</TableCell>)}</TableRow>;
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// Source pill: "Системний" (generated) vs "Завантажений" (manual upload).
function SourceBadge({ uploaded }) {
  return uploaded
    ? <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700" data-testid="src-uploaded"><HardDriveUpload className="h-3 w-3" />Завантажений</span>
    : <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600" data-testid="src-system"><Cpu className="h-3 w-3" />Системний</span>;
}

const todayISO = () => new Date().toISOString().slice(0, 10);

// Compact metadata form shown before uploading an act / ecologist report.
// Required: title + doc_date. Optional: period, contract, object, notes.
// Report adds report_scope (+quarter/year). Act adds act_number / method / weight.
function UploadDocPanel({ kind, busy, contracts, onUpload, onCancel }) {
  const isReport = kind === "ecologist_report";
  const [f, setF] = React.useState({
    title: "",
    doc_date: todayISO(),
    period_from: "",
    period_to: "",
    contract_id: "",
    object_id: "",
    notes: "",
    // report
    report_scope: "quarter",
    quarter: String(Math.floor(new Date().getMonth() / 3) + 1),
    year: String(new Date().getFullYear()),
    // act
    act_number: "",
    utilization_method: "",
    total_weight_kg: "",
  });
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  const buildMeta = () => {
    const meta = {
      doc_type: kind,
      title: f.title.trim(),
      doc_date: f.doc_date,
    };
    if (f.period_from) meta.period_from = f.period_from;
    if (f.period_to) meta.period_to = f.period_to;
    if (f.contract_id) meta.contract_id = f.contract_id;
    if (f.object_id.trim()) meta.object_id = f.object_id.trim();
    if (f.notes.trim()) meta.notes = f.notes.trim();
    if (isReport) {
      meta.report_scope = f.report_scope;
      if (f.report_scope === "quarter") {
        meta.quarter = Number(f.quarter);
        meta.year = Number(f.year);
        meta.period_label = `Q${f.quarter} ${f.year}`;
      }
    } else {
      if (f.act_number.trim()) meta.act_number = f.act_number.trim();
      if (f.utilization_method.trim()) meta.utilization_method = f.utilization_method.trim();
      if (f.total_weight_kg) meta.total_weight_kg = Number(f.total_weight_kg);
    }
    return meta;
  };

  const validate = () => {
    if (!f.title.trim()) { toast.error("Вкажіть назву документа"); return false; }
    if (!f.doc_date) { toast.error("Вкажіть дату документа"); return false; }
    if (f.period_from && f.period_to && f.period_from > f.period_to) {
      toast.error("Період: дата початку пізніше за дату завершення"); return false;
    }
    if (isReport && f.report_scope === "quarter" && (!f.quarter || !f.year)) {
      toast.error("Вкажіть квартал і рік"); return false;
    }
    return true;
  };

  const handleFile = (file) => {
    if (!validate()) return;
    onUpload(kind, file, buildMeta());
  };

  const inputCls = "h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm";
  const testidPrefix = isReport ? "report" : "act";

  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid={`c360-${testidPrefix}-meta-form`}>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div className="sm:col-span-2 lg:col-span-1">
          <label className="mb-1 block text-xs font-medium text-slate-600">Назва <span className="text-red-500">*</span></label>
          <Input value={f.title} onChange={set("title")} placeholder="напр. Акт №12 / Річний звіт" data-testid={`c360-${testidPrefix}-title`} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Дата документа <span className="text-red-500">*</span></label>
          <input type="date" value={f.doc_date} onChange={set("doc_date")} className={inputCls} data-testid={`c360-${testidPrefix}-docdate`} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Договір</label>
          <select value={f.contract_id} onChange={set("contract_id")} className={inputCls} data-testid={`c360-${testidPrefix}-contract`}>
            <option value="">— без прив'язки —</option>
            {(contracts || []).map((c) => (
              <option key={c.id} value={c.id}>{c.number || c.contract_number || c.id?.slice(-8)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Період з</label>
          <input type="date" value={f.period_from} onChange={set("period_from")} className={inputCls} data-testid={`c360-${testidPrefix}-pfrom`} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Період по</label>
          <input type="date" value={f.period_to} onChange={set("period_to")} className={inputCls} data-testid={`c360-${testidPrefix}-pto`} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Об'єкт (ID)</label>
          <Input value={f.object_id} onChange={set("object_id")} placeholder="необов'язково" data-testid={`c360-${testidPrefix}-object`} />
        </div>

        {isReport ? (
          <>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Обсяг звіту</label>
              <select value={f.report_scope} onChange={set("report_scope")} className={inputCls} data-testid="c360-report-scope">
                <option value="quarter">Квартал</option>
                <option value="custom_period">Довільний період</option>
                <option value="full_contract">Весь договір</option>
              </select>
            </div>
            {f.report_scope === "quarter" && (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Квартал</label>
                  <select value={f.quarter} onChange={set("quarter")} className={inputCls} data-testid="c360-report-quarter">
                    {["1", "2", "3", "4"].map((q) => <option key={q} value={q}>Q{q}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Рік</label>
                  <Input value={f.year} onChange={set("year")} placeholder="2026" data-testid="c360-report-year" />
                </div>
              </>
            )}
          </>
        ) : (
          <>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">№ акта</label>
              <Input value={f.act_number} onChange={set("act_number")} placeholder="необов'язково" data-testid="c360-act-number" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Метод утилізації</label>
              <Input value={f.utilization_method} onChange={set("utilization_method")} placeholder="необов'язково" data-testid="c360-act-method" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Вага (кг)</label>
              <Input type="number" value={f.total_weight_kg} onChange={set("total_weight_kg")} placeholder="необов'язково" data-testid="c360-act-weight" />
            </div>
          </>
        )}
        <div className="sm:col-span-2 lg:col-span-3">
          <label className="mb-1 block text-xs font-medium text-slate-600">Нотатки</label>
          <Textarea value={f.notes} onChange={set("notes")} placeholder="Короткий коментар (необов'язково)" className="min-h-[60px]" data-testid={`c360-${testidPrefix}-notes`} />
        </div>
      </div>
      <div className="mt-3">
        <DropZone onFile={handleFile} busy={busy} testid={`c360-dropzone-${testidPrefix}`} hint="Перетягніть файл сюди або натисніть, щоб обрати (макс. 25 МБ)" />
        <div className="mt-2 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onCancel} data-testid={`c360-${testidPrefix}-cancel`}>Скасувати</Button>
        </div>
      </div>
    </div>
  );
}

// Rich acts/reports table: name · type · period · date · contract · status ·
// source · uploaded_by · uploaded_at · actions (open / download / delete / pdf).
function FileTable({ data, empty, kind, contracts, onOpen, onDownload, onDelete, onGenPdf, pdfBusy }) {
  if (data === null || data === undefined) return <TableSkeleton rows={5} />;
  if (!data.length) return <EmptyState icon={empty.icon} title={empty.title} hint={empty.hint} />;
  const cmap = {};
  (contracts || []).forEach((c) => { cmap[c.id] = c.number || c.contract_number || (c.id ? c.id.slice(-8) : ""); });
  const isReport = kind === "ecologist_report";
  const typeLabel = (item) => {
    if (item.uploaded || item.source === "uploaded") {
      if (isReport) return item.report_type || "Звіт";
      return "Акт";
    }
    return isReport ? "Звіт" : "Акт";
  };
  const periodOf = (item) => {
    if (item.period_label) return item.period_label;
    if (item.period_from || item.period_to) return `${item.period_from ? fmtDate(item.period_from) : "…"} — ${item.period_to ? fmtDate(item.period_to) : "…"}`;
    return "—";
  };
  const head = ["Назва", "Тип", "Період", "Дата док.", "Договір", "Статус", "Джерело", "Ким завантажено", "Завантажено", ""];
  return (
    <div className="overflow-x-auto rounded-2xl border border-[hsl(var(--border))] bg-white">
      <Table>
        <TableHeader><TableRow>{head.map((h, i) => <TableHead key={i} className={i === head.length - 1 ? "text-right" : ""}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {data.map((item, ri) => {
            const uploaded = item.uploaded || item.source === "uploaded";
            const canDelete = uploaded && item.can_delete;
            return (
              <TableRow key={item.id || item.file_id || ri} data-testid={`c360-${isReport ? "report" : "act"}-row`}>
                <TableCell>
                  {uploaded
                    ? <span className="inline-flex items-center gap-1 text-xs"><FileText className="h-3.5 w-3.5 text-emerald-600" />{item.title || item.filename}</span>
                    : <span className="font-mono text-xs">{item.act_number || item.number || (item.id ? item.id.slice(-8) : "—")}</span>}
                </TableCell>
                <TableCell><StatusChip s={typeLabel(item)} /></TableCell>
                <TableCell className="text-xs text-slate-600">{periodOf(item)}</TableCell>
                <TableCell className="text-xs text-slate-600">{fmtDate(item.doc_date || item.act_date || (uploaded ? null : item.created_at)) || "—"}</TableCell>
                <TableCell className="text-xs text-slate-600">{item.contract_id ? (cmap[item.contract_id] || item.contract_id.slice(-8)) : "—"}</TableCell>
                <TableCell><StatusChip s={item.status || (uploaded ? "active" : "—")} /></TableCell>
                <TableCell><SourceBadge uploaded={uploaded} /></TableCell>
                <TableCell className="text-xs text-slate-500">{uploaded ? (item.uploaded_by || "—") : "—"}</TableCell>
                <TableCell className="text-xs text-slate-500">{uploaded ? fmtDate(item.created_at) : "—"}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {uploaded ? (
                      <>
                        <Button variant="ghost" size="sm" className="gap-1" onClick={() => onOpen(item)} data-testid={`c360-open-${isReport ? "report" : "act"}`}><ExternalLink className="h-3.5 w-3.5" />Відкрити</Button>
                        <Button variant="ghost" size="icon" title="Завантажити" onClick={() => onDownload(item)} data-testid={`c360-download-${isReport ? "report" : "act"}`}><Download className="h-4 w-4" /></Button>
                        {canDelete && (
                          <Button variant="ghost" size="icon" className="text-red-500 hover:bg-red-50" title="Видалити" onClick={() => onDelete(kind, item)} data-testid={`c360-delete-${isReport ? "report" : "act"}`}><Trash2 className="h-4 w-4" /></Button>
                        )}
                      </>
                    ) : (
                      onGenPdf
                        ? <Button variant="ghost" size="sm" className="gap-1" onClick={() => onGenPdf(item)} disabled={pdfBusy === item.id} data-testid="c360-genpdf-act"><FileDown className="h-3.5 w-3.5" />PDF</Button>
                        : <span className="text-xs text-slate-400">Системний</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// Delete confirmation dialog with an optional reason field.
function DeleteFileDialog({ state, busy, onReason, onCancel, onConfirm }) {
  if (!state) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid="c360-delete-dialog" onClick={onCancel}>
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-red-50 text-red-600"><Trash2 className="h-4 w-4" /></span>
          <h3 className="text-base font-semibold text-slate-900">Видалити файл?</h3>
        </div>
        <p className="mb-3 text-sm text-slate-600">
          Ви впевнені, що хочете видалити <b className="text-slate-800">«{state.title}»</b>? Файл зникне з таблиці та клієнтського перегляду. Дію буде зафіксовано в журналі.
        </p>
        <label className="mb-1 block text-xs font-medium text-slate-600">Причина (необов'язково)</label>
        <Textarea value={state.reason} onChange={(e) => onReason(e.target.value)} placeholder="напр. помилкове завантаження" className="mb-4 min-h-[60px]" data-testid="c360-delete-reason" />
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={busy} data-testid="c360-delete-cancel">Скасувати</Button>
          <Button size="sm" className="bg-red-600 text-white hover:bg-red-700" onClick={onConfirm} disabled={busy} data-testid="c360-delete-confirm">
            {busy ? "Видаляємо…" : "Видалити"}
          </Button>
        </div>
      </div>
    </div>
  );
}
