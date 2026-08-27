import React, { useEffect, useState, useCallback } from "react";
import { UserPlus, Plus, Search, PhoneCall, ArrowRightCircle, Filter } from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate } from "@/lib/portalMeta";
import { PageHeader, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/sonner";

const STATUS_TONE = {
  new: "bg-[#EFF6FF] text-[#1D4ED8]",
  contacted: "bg-[#FEF3C7] text-[#92400E]",
  qualified: "bg-[#EDE9FE] text-[#5B21B6]",
  won: "bg-[#ECFDF5] text-[#065F46]",
  lost: "bg-[#FEE2E2] text-[#991B1B]",
};

function CreateLeadDialog({ open, onOpenChange, managers, isAdmin, onCreated }) {
  const blank = { name: "", contact_name: "", phone: "", email: "", edrpou: "", source: "phone", notes: "", assigned_manager_id: "self" };
  const [f, setF] = useState(blank);
  const [submitting, setSubmitting] = useState(false);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  React.useEffect(() => { if (open) setF(blank); }, [open]); // eslint-disable-line
  const submit = async () => {
    if (!f.name.trim() && !f.contact_name.trim() && !f.phone.trim()) return toast.error("Вкажіть назву, контакт або телефон");
    setSubmitting(true);
    try {
      const body = { ...f };
      if (body.assigned_manager_id === "self") delete body.assigned_manager_id;
      await PortalAPI.createLead(body);
      toast.success("Лід створено");
      onOpenChange(false);
      onCreated && onCreated();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося створити лід"); }
    finally { setSubmitting(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="lead-dialog">
        <DialogHeader>
          <DialogTitle>Новий холодний лід</DialogTitle>
          <DialogDescription>Потенційний клієнт без кабінету (дзвінок, звернення «з вулиці»).</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Назва компанії</Label><Input value={f.name} onChange={set("name")} placeholder="ТОВ …" data-testid="lead-name-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Контактна особа</Label><Input value={f.contact_name} onChange={set("contact_name")} data-testid="lead-contact-input" /></div>
            <div className="grid gap-1.5"><Label>Телефон</Label><Input value={f.phone} onChange={set("phone")} placeholder="+380…" data-testid="lead-phone-input" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input value={f.email} onChange={set("email")} data-testid="lead-email-input" /></div>
            <div className="grid gap-1.5"><Label>ЄДРПОУ</Label><Input value={f.edrpou} onChange={set("edrpou")} data-testid="lead-edrpou-input" /></div>
          </div>
          {isAdmin && (
            <div className="grid gap-1.5">
              <Label>Відповідальний менеджер</Label>
              <Select value={f.assigned_manager_id} onValueChange={(v) => setF((p) => ({ ...p, assigned_manager_id: v }))}>
                <SelectTrigger data-testid="lead-manager-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="self">— Я (поточний користувач) —</SelectItem>
                  {managers.map((m) => <SelectItem key={m.id} value={m.id}>{m.name} · {m.role}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-1.5"><Label>Нотатки</Label><Textarea value={f.notes} onChange={set("notes")} rows={2} placeholder="Звідки прийшов, що цікавить…" data-testid="lead-notes-input" /></div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={submitting} data-testid="lead-submit">{submitting ? "Збереження…" : "Створити лід"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function WasteLeads() {
  useSeo("Ліди", "Холодні ліди — потенційні клієнти.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [mine, setMine] = useState(!isAdmin);
  const [dialog, setDialog] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await PortalAPI.leads({ ...(q ? { q } : {}), ...(mine ? { mine: true } : {}) });
      setRows(r.items || []);
      setStatuses(r.status_labels || {});
    } catch { setRows([]); } finally { setLoading(false); }
  }, [q, mine]);

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  useEffect(() => { PortalAPI.managers().then((r) => setManagers(r.items || [])).catch(() => {}); }, []);

  const setStatus = async (lead, status) => {
    try { await PortalAPI.updateLead(lead.id, { lead_status: status }); toast.success("Статус оновлено"); load(); }
    catch { toast.error("Не вдалося оновити статус"); }
  };
  const convert = async (lead) => {
    try { await PortalAPI.convertLead(lead.id); toast.success("Лід конвертовано у клієнта"); load(); }
    catch { toast.error("Не вдалося конвертувати"); }
  };

  return (
    <div data-testid="portal-leads">
      <PageHeader
        title="Ліди"
        subtitle="Холодні ліди — потенційні клієнти без кабінету"
        actions={<Button onClick={() => setDialog(true)} className="gap-2" data-testid="lead-create-button"><Plus className="h-4 w-4" /> Новий лід</Button>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative max-w-md flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук за назвою, контактом, телефоном…" className="pl-9" data-testid="leads-search" />
        </div>
        <label className="flex items-center gap-2 rounded-xl border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm text-slate-600">
          <Filter className="h-4 w-4 text-slate-400" /> Тільки мої
          <Switch checked={mine} onCheckedChange={setMine} data-testid="leads-mine-toggle" />
        </label>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={6} /></div>
        ) : rows.length === 0 ? (
          <EmptyState icon={UserPlus} title="Лідів немає" hint="Створіть холодний лід після дзвінка чи звернення." action={<Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Новий лід</Button>} testid="leads-empty" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Компанія / контакт</TableHead>
                <TableHead>Телефон</TableHead>
                <TableHead>Менеджер</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Створено</TableHead>
                <TableHead className="text-right">Дії</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id} data-testid="lead-row">
                  <TableCell>
                    <div className="font-medium text-slate-900">{c.name}</div>
                    {c.contact_name && <div className="text-xs text-slate-400">{c.contact_name}</div>}
                  </TableCell>
                  <TableCell className="text-slate-500">
                    {c.phone ? <a href={`tel:${c.phone}`} className="inline-flex items-center gap-1 hover:text-[#0E5E3A]"><PhoneCall className="h-3.5 w-3.5" />{c.phone}</a> : "—"}
                  </TableCell>
                  <TableCell className="text-slate-500">{c.manager ? c.manager.name : "—"}</TableCell>
                  <TableCell>
                    <Select value={c.lead_status || "new"} onValueChange={(v) => setStatus(c, v)}>
                      <SelectTrigger className="h-8 w-[150px]" data-testid="lead-status-select">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[c.lead_status || "new"]}`}>
                          {statuses[c.lead_status || "new"] || "Новий"}
                        </span>
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(statuses).map(([k, label]) => <SelectItem key={k} value={k}>{label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="text-slate-500">{fmtDate(c.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost" className="gap-1.5 text-[#0E5E3A]" onClick={() => convert(c)} data-testid="lead-convert-button">
                      <ArrowRightCircle className="h-4 w-4" /> У клієнти
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <CreateLeadDialog open={dialog} onOpenChange={setDialog} managers={managers} isAdmin={isAdmin} onCreated={load} />
    </div>
  );
}
