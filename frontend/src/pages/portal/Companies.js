import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Plus, Search, ChevronRight, UserCog } from "lucide-react";
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
import { toast } from "@/components/ui/sonner";

function CreateCompanyDialog({ open, onOpenChange, onCreated }) {
  const [f, setF] = useState({ name: "", edrpou: "", email: "", phone: "", address: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  React.useEffect(() => { if (open) setF({ name: "", edrpou: "", email: "", phone: "", address: "", notes: "" }); }, [open]);
  const submit = async () => {
    if (!f.name.trim()) return toast.error("Вкажіть назву компанії");
    setSubmitting(true);
    try {
      const r = await PortalAPI.createCompany(f);
      toast.success("Компанію створено");
      onOpenChange(false);
      onCreated && onCreated(r.company);
    } catch { toast.error("Не вдалося створити компанію"); }
    finally { setSubmitting(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="company-dialog">
        <DialogHeader>
          <DialogTitle>Нова компанія</DialogTitle>
          <DialogDescription>Додайте B2B-клієнта до реєстру.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Назва *</Label><Input value={f.name} onChange={set("name")} data-testid="company-name-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>ЄДРПОУ</Label><Input value={f.edrpou} onChange={set("edrpou")} data-testid="company-edrpou-input" /></div>
            <div className="grid gap-1.5"><Label>Телефон</Label><Input value={f.phone} onChange={set("phone")} placeholder="+380…" data-testid="company-phone-input" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Email</Label><Input value={f.email} onChange={set("email")} data-testid="company-email-input" /></div>
          <div className="grid gap-1.5"><Label>Адреса</Label><Input value={f.address} onChange={set("address")} data-testid="company-address-input" /></div>
          <div className="grid gap-1.5"><Label>Нотатки</Label><Textarea value={f.notes} onChange={set("notes")} rows={2} data-testid="company-notes-input" /></div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={submitting} data-testid="company-submit">{submitting ? "Збереження…" : "Створити"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReassignDialog({ company, managers, onOpenChange, onDone }) {
  const [val, setVal] = useState(company?.assigned_manager_id || "none");
  const [saving, setSaving] = useState(false);
  React.useEffect(() => { setVal(company?.assigned_manager_id || "none"); }, [company]);
  const submit = async () => {
    setSaving(true);
    try {
      await PortalAPI.assignCompanyManager(company.id, val === "none" ? "" : val);
      toast.success("Менеджера оновлено");
      onOpenChange(false);
      onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося призначити"); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open={!!company} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="reassign-dialog">
        <DialogHeader>
          <DialogTitle>Відповідальний менеджер</DialogTitle>
          <DialogDescription>Компанія: <b>{company?.name}</b>. Зміна оновить відкриті заявки та кабінет клієнта.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label>Менеджер</Label>
          <Select value={val} onValueChange={setVal}>
            <SelectTrigger data-testid="reassign-select"><SelectValue placeholder="Оберіть менеджера" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">— Без менеджера —</SelectItem>
              {managers.map((m) => (
                <SelectItem key={m.id} value={m.id}>{m.name} · {m.role}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={saving} data-testid="reassign-submit">{saving ? "Збереження…" : "Призначити"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Companies() {
  useSeo("Компанії", "Реєстр B2B-клієнтів.");
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(false);
  const [reassign, setReassign] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await PortalAPI.companies({ kind: "client", ...(q ? { q } : {}) }); setRows(r.items || []); }
    catch { setRows([]); } finally { setLoading(false); }
  }, [q]);

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  useEffect(() => { PortalAPI.managers().then((r) => setManagers(r.items || [])).catch(() => {}); }, []);

  return (
    <div data-testid="portal-companies">
      <PageHeader
        title="Компанії"
        subtitle="Реєстр B2B-клієнтів та об’єктів"
        actions={<Button onClick={() => setDialog(true)} className="gap-2" data-testid="company-create-button"><Plus className="h-4 w-4" /> Нова компанія</Button>}
      />

      <div className="mb-4 relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук за назвою, ЄДРПОУ, телефоном…" className="pl-9" data-testid="companies-search" />
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={6} /></div>
        ) : rows.length === 0 ? (
          <EmptyState icon={Building2} title="Компаній немає" hint="Створіть першого клієнта, щоб почати роботу." action={<Button onClick={() => setDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Нова компанія</Button>} testid="companies-empty" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Назва</TableHead>
                <TableHead>ЄДРПОУ</TableHead>
                <TableHead>Контакти</TableHead>
                <TableHead>Менеджер</TableHead>
                <TableHead>Створено</TableHead>
                <TableHead className="w-10"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id} className="cursor-pointer" data-testid="company-row">
                  <TableCell className="font-medium text-slate-900" onClick={() => navigate(`/app/companies/${c.id}`)}>{c.name}</TableCell>
                  <TableCell className="text-slate-500" onClick={() => navigate(`/app/companies/${c.id}`)}>{c.edrpou || "—"}</TableCell>
                  <TableCell className="text-slate-500" onClick={() => navigate(`/app/companies/${c.id}`)}>{c.phone || c.email || "—"}</TableCell>
                  <TableCell data-testid="company-manager-cell">
                    {c.manager ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF5] px-2.5 py-1 text-xs font-medium text-[#065F46]">
                        {c.manager.name}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">не призначено</span>
                    )}
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setReassign(c); }}
                        className="ml-2 inline-flex items-center text-slate-400 hover:text-[#0E5E3A]"
                        title="Змінити менеджера"
                        data-testid="company-reassign-button"
                      >
                        <UserCog className="h-4 w-4" />
                      </button>
                    )}
                  </TableCell>
                  <TableCell className="text-slate-500" onClick={() => navigate(`/app/companies/${c.id}`)}>{fmtDate(c.created_at)}</TableCell>
                  <TableCell onClick={() => navigate(`/app/companies/${c.id}`)}><ChevronRight className="h-4 w-4 text-slate-300" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <CreateCompanyDialog open={dialog} onOpenChange={setDialog} onCreated={(c) => (c ? navigate(`/app/companies/${c.id}`) : load())} />
      {reassign && (
        <ReassignDialog
          company={reassign}
          managers={managers}
          onOpenChange={(o) => { if (!o) setReassign(null); }}
          onDone={load}
        />
      )}
    </div>
  );
}
