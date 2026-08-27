import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Plus, ClipboardList, FileText, Truck, BadgeCheck, Building2, RefreshCw } from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { STAGE_ORDER, STAGE_LABELS, fmtDate, fmtDateTime, itemsSummary } from "@/lib/portalMeta";
import { PageHeader, StatusBadge } from "@/components/portal/PortalUI";
import { CreateRequestDialog } from "@/components/portal/CreateRequestDialog";
import { HazardBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

// Кольорові акценти етапів воронки (для візуальної ясності)
const STAGE_DOT = ["#10B981", "#3B82F6", "#F59E0B", "#8B5CF6", "#06B6D4", "#22C55E", "#64748B"];

function RequestCard({ r, onOpen, companyName }) {
  const contact = r.contact || {};
  return (
    <button onClick={() => onOpen(r)} data-testid="request-card"
      className="w-full rounded-xl border border-[hsl(var(--border))] bg-white p-3 text-left transition-shadow duration-200 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-slate-800">{companyName || contact.company_name || r.company_name || "Без компанії"}</span>
        {r.items?.some((i) => i.hazardous) && <HazardBadge hazardous />}
      </div>
      <div className="mt-1.5 font-mono text-xs text-slate-600">{itemsSummary(r.items)}</div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
        <span>{contact.name || contact.phone || r.source || "—"}</span>
        <span>{fmtDate(r.created_at)}</span>
      </div>
    </button>
  );
}

function RequestDetailDialog({ open, onOpenChange, request, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(request?.stage || "new");
  useEffect(() => { setStage(request?.stage || "new"); }, [request]);
  if (!request) return null;
  const contact = request.contact || {};

  const move = async (newStage) => {
    setStage(newStage); setBusy(true);
    try { await PortalAPI.setRequestStage(request.id, newStage); toast.success(`Етап → ${STAGE_LABELS[newStage]}`); onChanged && onChanged(); }
    catch { toast.error("Не вдалося змінити етап"); } finally { setBusy(false); }
  };

  const generate = async (kind) => {
    setBusy(true);
    const labels = { contract: "Договір", pickup: "Замовлення на вивіз", act: "Акт" };
    try {
      await PortalAPI.genFromRequest(request.id, kind);
      toast.success(`${labels[kind]} створено`);
      onChanged && onChanged();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Не вдалося згенерувати документ";
      toast.error(typeof msg === "string" ? msg : "Помилка генерації");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="request-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-[hsl(var(--primary))]" /> Заявка
            <StatusBadge status={request.stage} />
          </DialogTitle>
          <DialogDescription>{contact.company_name || request.company_name || "Без компанії"} · {fmtDateTime(request.created_at)}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Позиції</div>
            <div className="space-y-1.5">
              {(request.items || []).map((it, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 px-3 py-2 text-sm">
                  <span className="flex items-center gap-2"><span className="font-mono font-semibold text-[hsl(var(--primary))]">{it.waste_code}</span><HazardBadge hazardous={it.hazardous} /></span>
                  <span className="text-slate-500">{it.qty ? `${it.qty} ${it.unit || "кг"}` : "—"}</span>
                </div>
              ))}
            </div>
          </div>

          {(contact.name || contact.phone || contact.email) && (
            <div className="rounded-lg border border-[hsl(var(--border))] p-3 text-sm text-slate-600">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Контакт</div>
              <div className="mt-1">{[contact.name, contact.phone, contact.email].filter(Boolean).join(" · ")}</div>
            </div>
          )}

          {request.comment && <div className="rounded-lg bg-[hsl(var(--secondary))]/40 p-3 text-sm text-slate-600">{request.comment}</div>}

          <div className="grid gap-1.5">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Етап воронки</div>
            <Select value={stage} onValueChange={move} disabled={busy}>
              <SelectTrigger data-testid="request-stage-select"><SelectValue /></SelectTrigger>
              <SelectContent>{STAGE_ORDER.map((s) => <SelectItem key={s} value={s}>{STAGE_LABELS[s]}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Згенерувати документ</div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" className="gap-1.5" disabled={busy} onClick={() => generate("contract")} data-testid="gen-contract"><FileText className="h-4 w-4" /> Договір</Button>
              <Button variant="secondary" size="sm" className="gap-1.5" disabled={busy} onClick={() => generate("pickup")} data-testid="gen-pickup"><Truck className="h-4 w-4" /> Вивіз</Button>
              <Button variant="secondary" size="sm" className="gap-1.5" disabled={busy} onClick={() => generate("act")} data-testid="gen-act"><BadgeCheck className="h-4 w-4" /> Акт</Button>
            </div>
            {request.company_id && (
              <Link to={`/app/companies/${request.company_id}`} className="mt-3 inline-flex items-center gap-1.5 text-sm text-[hsl(var(--primary))] hover:underline" data-testid="request-to-company">
                <Building2 className="h-4 w-4" /> Відкрити картку компанії
              </Link>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function Requests() {
  useSeo("Воронка заявок", "Управління заявками на утилізацію за етапами.");
  const [rows, setRows] = useState([]);
  const [companyMap, setCompanyMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState({ open: false, request: null });

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await PortalAPI.requests({ limit: 500 }); setRows(r.items || []); }
    catch { setRows([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    PortalAPI.companies({ limit: 500 })
      .then((r) => setCompanyMap(Object.fromEntries((r.items || []).map((c) => [c.id, c.name]))))
      .catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const grouped = STAGE_ORDER.reduce((acc, s) => { acc[s] = []; return acc; }, {});
  rows.forEach((r) => { (grouped[r.stage] || grouped.new).push(r); });

  const openDetail = (r) => setDetail({ open: true, request: r });

  return (
    <div data-testid="portal-requests">
      <PageHeader
        title="Воронка заявок"
        subtitle="Заявки на утилізацію по етапах життєвого циклу"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="icon" onClick={load} title="Оновити" data-testid="requests-refresh"><RefreshCw className="h-4 w-4" /></Button>
            <Button className="gap-2" onClick={() => setCreateOpen(true)} data-testid="requests-create-button"><Plus className="h-4 w-4" /> Нова заявка</Button>
          </div>
        }
      />

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-64 w-full rounded-2xl" />)}
        </div>
      ) : (
        <ScrollArea className="w-full whitespace-nowrap">
          <div className="flex gap-4 pb-4">
            {STAGE_ORDER.map((s, idx) => {
              const dot = STAGE_DOT[idx % STAGE_DOT.length];
              const count = grouped[s].length;
              return (
                <div key={s} className="flex w-[290px] shrink-0 flex-col rounded-2xl border border-[hsl(var(--border))] bg-white/70 p-3 shadow-sm" data-testid={`column-${s}`}>
                  <div className="mb-3 flex items-center justify-between border-b border-[hsl(var(--border))] pb-2.5">
                    <span className="flex items-center gap-2 text-sm font-bold text-slate-800">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: dot }} />
                      {STAGE_LABELS[s]}
                    </span>
                    <span className={`min-w-[1.5rem] rounded-full px-2 py-0.5 text-center text-xs font-bold ${count ? "bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]" : "bg-[hsl(var(--secondary))] text-slate-400"}`}>{count}</span>
                  </div>
                  <div className="flex-1 space-y-2.5">
                    {count === 0 ? (
                      <div className="rounded-xl border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/30 px-3 py-8 text-center text-xs text-slate-400">Порожньо</div>
                    ) : grouped[s].map((r) => <RequestCard key={r.id} r={r} onOpen={openDetail} companyName={companyMap[r.company_id]} />)}
                  </div>
                </div>
              );
            })}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      )}

      <CreateRequestDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={load} />
      <RequestDetailDialog
        open={detail.open}
        onOpenChange={(v) => setDetail((d) => ({ ...d, open: v }))}
        request={detail.request}
        onChanged={() => { load(); setDetail((d) => ({ ...d, open: false })); }}
      />
    </div>
  );
}
