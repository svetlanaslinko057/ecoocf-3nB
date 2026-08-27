// Wave 5A: Documents Center
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { FileStack, Plus, ExternalLink, AlertTriangle, CheckCircle2, Clock, Search } from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";

const TYPE_OPTS = [
  { value: "contract", label: "Договір" },
  { value: "act", label: "Акт" },
  { value: "invoice", label: "Рахунок" },
  { value: "license", label: "Ліцензія" },
  { value: "passport", label: "Паспорт відходу" },
  { value: "photo", label: "Фото" },
  { value: "other", label: "Інше" },
];
const TYPE_LABEL = Object.fromEntries(TYPE_OPTS.map((t) => [t.value, t.label]));

function DocDialog({ open, onOpenChange, onSaved }) {
  const [f, setF] = useState({ name: "", type: "contract", url: "", customerId: "", dealId: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF({ name: "", type: "contract", url: "", customerId: "", dealId: "" }); }, [open]);
  const submit = async () => {
    if (!f.name.trim()) return toast.error("Назва документа обов'язкова");
    if (!f.url.trim()) return toast.error("Вкажіть URL або ID файлу");
    setBusy(true);
    try {
      await CrmAPI.documentCreate({
        name: f.name.trim(), type: f.type, url: f.url.trim(),
        customerId: f.customerId.trim() || null, dealId: f.dealId.trim() || null,
      });
      toast.success("Документ додано");
      onOpenChange(false); onSaved && onSaved();
    } catch { toast.error("Не вдалося додати"); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="doc-dialog">
        <DialogHeader><DialogTitle>Додати документ</DialogTitle><DialogDescription>URL або ID файлу в сховищі.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Назва *</Label><Input value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} data-testid="doc-name" /></div>
          <div className="grid gap-1.5"><Label>Тип</Label>
            <Select value={f.type} onValueChange={(v) => setF((p) => ({ ...p, type: v }))}>
              <SelectTrigger data-testid="doc-type"><SelectValue /></SelectTrigger>
              <SelectContent>{TYPE_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>URL / file_id *</Label><Input value={f.url} onChange={(e) => setF((p) => ({ ...p, url: e.target.value }))} placeholder="https://… або file-id" data-testid="doc-url" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>customerId</Label><Input value={f.customerId} onChange={(e) => setF((p) => ({ ...p, customerId: e.target.value }))} /></div>
            <div className="grid gap-1.5"><Label>dealId</Label><Input value={f.dealId} onChange={(e) => setF((p) => ({ ...p, dealId: e.target.value }))} /></div>
          </div>
        </div>
        <DialogFooter><Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button><Button onClick={submit} disabled={busy} data-testid="doc-submit">{busy ? "Збереження…" : "Додати"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function CrmDocuments() {
  useSeo("Документи · CRM", "Єдиний центр договорів, актів, ліцензій та вкладень.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [docs, setDocs] = useState([]);
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, p] = await Promise.all([CrmAPI.documents(), CrmAPI.documentsPending()]);
      setDocs(a.data || []);
      setPending(p.data || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let r = tab === "pending" ? pending : docs;
    if (q.trim()) {
      const ql = q.toLowerCase();
      r = r.filter((x) => (x.name || "").toLowerCase().includes(ql) || (x.type || "").toLowerCase().includes(ql) || (x.id || "").toLowerCase().includes(ql));
    }
    return r;
  }, [docs, pending, tab, q]);

  const verified = docs.filter((d) => d.status === "verified" || d.status === "approved").length;
  return (
    <div data-testid="portal-crm-documents">
      <PageHeader title="Документи" subtitle="Договори, акти, ліцензії, паспорти, фото" actions={isAdmin && <Button onClick={() => setDialog(true)} className="gap-2" data-testid="doc-create-button"><Plus className="h-4 w-4" /> Додати</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileStack} label="Усього" value={docs.length} testid="doc-kpi-total" />
        <StatCard icon={CheckCircle2} label="Верифіковані" value={verified} testid="doc-kpi-verified" />
        <StatCard icon={Clock} label="На перевірці" value={pending.length} testid="doc-kpi-pending" />
        <StatCard icon={AlertTriangle} label="Типів" value={new Set(docs.map((d) => d.type)).size} testid="doc-kpi-types" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="all" data-testid="doc-tab-all">Усі ({docs.length})</TabsTrigger>
            <TabsTrigger value="pending" data-testid="doc-tab-pending">На перевірці ({pending.length})</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук…" className="pl-9" data-testid="doc-search" />
        </div>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
          : filtered.length === 0 ? <EmptyState icon={FileStack} title="Документів немає" hint="Додайте договір або акт утилізації." action={isAdmin && <Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Додати</Button>} testid="doc-empty" />
          : (
            <Table>
              <TableHeader><TableRow><TableHead>Назва</TableHead><TableHead>Тип</TableHead><TableHead>Клієнт</TableHead><TableHead>Створено</TableHead><TableHead>Статус</TableHead><TableHead className="w-12"></TableHead></TableRow></TableHeader>
              <TableBody>{filtered.map((d) => {
                const pendingFlag = (d.status || "pending") === "pending";
                return (
                  <TableRow key={d.id} data-testid="doc-row">
                    <TableCell><div className="font-medium text-slate-900">{d.name || "—"}</div><div className="font-mono text-[10px] text-slate-400">{d.id}</div></TableCell>
                    <TableCell className="text-sm text-slate-500">{TYPE_LABEL[d.type] || d.type || "—"}</TableCell>
                    <TableCell className="text-sm text-slate-500">{d.customerId || "—"}</TableCell>
                    <TableCell className="text-sm text-slate-500">{fmtDate(d.created_at)}</TableCell>
                    <TableCell>{pendingFlag
                      ? <span className="inline-flex items-center rounded-md border border-[#FDE68A] bg-[#FFFBEB] px-2 py-0.5 text-xs text-[#92400E]">на перевірці</span>
                      : <span className="inline-flex items-center rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-2 py-0.5 text-xs text-[#065F46]">вериф. {d.status || ""}</span>}
                    </TableCell>
                    <TableCell>{d.url && /^https?:/i.test(d.url) && <Button variant="ghost" size="icon" onClick={() => window.open(d.url, "_blank")} data-testid="doc-open"><ExternalLink className="h-4 w-4" /></Button>}</TableCell>
                  </TableRow>
                );
              })}</TableBody>
            </Table>
          )}
      </div>

      <DocDialog open={dialog} onOpenChange={setDialog} onSaved={load} />
    </div>
  );
}
