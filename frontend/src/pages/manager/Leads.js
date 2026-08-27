import React, { useEffect, useState, useCallback } from "react";
import { Plus, Search, Trash2, Pencil, ArrowRightLeft, Phone, ClipboardList, Building2, Mail, PhoneCall } from "lucide-react";
import { ManagerAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import {
  LEAD_STATUS_ORDER, LEAD_STATUS_LABELS, LEAD_STATUS_TONE,
  fmtMoney, fmtDate, fmtDateTime, CALL_STATUS_LABELS, CALL_STATUS_TONE, TASK_STATUS_LABELS, TASK_STATUS_TONE, dueMeta,
} from "@/lib/managerMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const TABS = [["all", "Усі"], ...LEAD_STATUS_ORDER.map((s) => [s, LEAD_STATUS_LABELS[s]])];
const EMPTY = { name: "", company: "", email: "", phone: "", wasteType: "", region: "", budgetEur: "", source: "manual", status: "new", notes: "" };

export default function ManagerLeads() {
  useSeo("Мої ліди", "Управління лідами менеджера.");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(null);   // {mode:'create'|'edit', data}
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const [detail, setDetail] = useState(null);   // lead detail object

  const load = useCallback(() => {
    setLoading(true);
    ManagerAPI.leads({ status: tab, q: q || undefined })
      .then((r) => setItems(r.items || []))
      .catch(() => toast.error("Не вдалося завантажити ліди"))
      .finally(() => setLoading(false));
  }, [tab, q]);

  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  const openCreate = () => { setForm(EMPTY); setDialog({ mode: "create" }); };
  const openEdit = (l) => {
    setForm({ ...EMPTY, ...l, budgetEur: l.budgetEur || "" });
    setDialog({ mode: "edit", data: l });
  };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Вкажіть ім'я контакту");
    setSaving(true);
    try {
      if (dialog.mode === "create") { await ManagerAPI.createLead(form); toast.success("Лід створено"); }
      else { await ManagerAPI.updateLead(dialog.data.id, form); toast.success("Лід оновлено"); }
      setDialog(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setSaving(false); }
  };

  const changeStatus = async (l, status) => {
    setItems((p) => p.map((x) => (x.id === l.id ? { ...x, status } : x)));
    try { await ManagerAPI.updateLead(l.id, { status }); toast.success("Статус оновлено"); if (tab !== "all") load(); }
    catch { toast.error("Не вдалося"); load(); }
  };

  const convert = async (l) => {
    try { const r = await ManagerAPI.convertLead(l.id); toast.success(`Створено угоду: ${r.deal.title}`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося конвертувати"); }
  };

  const doDelete = async () => {
    try { await ManagerAPI.deleteLead(confirmDel.id); toast.success("Лід видалено"); setItems((p) => p.filter((x) => x.id !== confirmDel.id)); }
    catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  const openDetail = async (l) => {
    setDetail({ loading: true, lead: l });
    try { const r = await ManagerAPI.lead(l.id); setDetail({ loading: false, ...r }); }
    catch { toast.error("Не вдалося відкрити лід"); setDetail(null); }
  };

  return (
    <div data-testid="manager-leads">
      <PageHeader
        title="Мої ліди"
        subtitle="Воронка потенційних клієнтів"
        actions={<Button onClick={openCreate} data-testid="new-lead-button"><Plus className="mr-2 h-4 w-4" /> Новий лід</Button>}
      />

      {/* Filters */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {TABS.map(([v, label]) => (
            <button
              key={v}
              onClick={() => setTab(v)}
              data-testid={`lead-tab-${v}`}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${tab === v ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"}`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук: ім'я, компанія, email…" className="pl-9" data-testid="lead-search" />
        </div>
      </div>

      {loading ? <TableSkeleton rows={6} /> : items.length === 0 ? (
        <EmptyState icon={Building2} title="Лідів не знайдено" hint="Створіть новий лід або змініть фільтри." action={<Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" /> Новий лід</Button>} testid="leads-empty" />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">Клієнт</th>
                  <th className="px-4 py-3 font-semibold">Контакт</th>
                  <th className="px-4 py-3 font-semibold">Тип відходів</th>
                  <th className="px-4 py-3 font-semibold text-right">Бюджет</th>
                  <th className="px-4 py-3 font-semibold">Статус</th>
                  <th className="px-4 py-3 font-semibold text-right">Дії</th>
                </tr>
              </thead>
              <tbody>
                {items.map((l) => (
                  <tr key={l.id} className="border-b border-slate-50 last:border-0 hover:bg-[#F2F8F3]/50" data-testid={`lead-row-${l.id}`}>
                    <td className="px-4 py-3">
                      <button onClick={() => openDetail(l)} className="text-left" data-testid={`lead-open-${l.id}`}>
                        <div className="font-medium text-slate-900 hover:text-[#0E5E3A]">{l.company || l.name}</div>
                        <div className="text-xs text-slate-400">{l.name} · {fmtDate(l.created_at)}</div>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div className="text-xs">{l.phone || "—"}</div>
                      <div className="text-xs text-slate-400">{l.email || "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div className="max-w-[180px] truncate">{l.wasteType || "—"}</div>
                      {l.region && <div className="text-xs text-slate-400">{l.region}</div>}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-slate-800">{l.budgetEur ? fmtMoney(l.budgetEur) : "—"}</td>
                    <td className="px-4 py-3">
                      <Select value={l.status} onValueChange={(v) => changeStatus(l, v)}>
                        <SelectTrigger className="h-8 w-[150px]" data-testid={`lead-status-${l.id}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {LEAD_STATUS_ORDER.map((s) => <SelectItem key={s} value={s}>{LEAD_STATUS_LABELS[s]}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {l.status !== "won" && l.status !== "lost" && (
                          <Button variant="ghost" size="icon" title="Конвертувати в угоду" onClick={() => convert(l)} data-testid={`lead-convert-${l.id}`}><ArrowRightLeft className="h-4 w-4 text-[#0E5E3A]" /></Button>
                        )}
                        <Button variant="ghost" size="icon" title="Редагувати" onClick={() => openEdit(l)} data-testid={`lead-edit-${l.id}`}><Pencil className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" title="Видалити" onClick={() => setConfirmDel(l)} data-testid={`lead-del-${l.id}`}><Trash2 className="h-4 w-4 text-[#B91C1C]" /></Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{dialog?.mode === "edit" ? "Редагувати лід" : "Новий лід"}</DialogTitle>
            <DialogDescription>Дані потенційного клієнта</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Контактна особа *"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="lead-form-name" /></Field>
            <Field label="Компанія"><Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} data-testid="lead-form-company" /></Field>
            <Field label="Email"><Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Телефон"><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
            <Field label="Тип відходів"><Input value={form.wasteType} onChange={(e) => setForm({ ...form, wasteType: e.target.value })} placeholder="напр., відпрацьовані масла" /></Field>
            <Field label="Регіон"><Input value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} /></Field>
            <Field label="Бюджет, ₴"><Input type="number" value={form.budgetEur} onChange={(e) => setForm({ ...form, budgetEur: e.target.value })} /></Field>
            <Field label="Статус">
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{LEAD_STATUS_ORDER.map((s) => <SelectItem key={s} value={s}>{LEAD_STATUS_LABELS[s]}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <div className="sm:col-span-2"><Field label="Нотатки"><Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Скасувати</Button>
            <Button onClick={save} disabled={saving} data-testid="lead-form-save">{saving ? "Збереження…" : "Зберегти"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-[#0E5E3A]" />
                  {detail.lead?.company || detail.lead?.name}
                </DialogTitle>
                <DialogDescription>{detail.lead?.name} · {detail.lead?.wasteType || "тип не вказано"}</DialogDescription>
              </DialogHeader>
              {detail.loading ? <TableSkeleton rows={3} /> : (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-4">
                    <div><div className="text-xs text-slate-400">Статус</div><StatusPill tone={LEAD_STATUS_TONE[detail.lead?.status]}>{LEAD_STATUS_LABELS[detail.lead?.status]}</StatusPill></div>
                    <div><div className="text-xs text-slate-400">Бюджет</div><div className="font-medium">{detail.lead?.budgetEur ? fmtMoney(detail.lead.budgetEur) : "—"}</div></div>
                    <div className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5 text-slate-400" /><span className="truncate">{detail.lead?.email || "—"}</span></div>
                    <div className="flex items-center gap-1.5"><PhoneCall className="h-3.5 w-3.5 text-slate-400" /><span>{detail.lead?.phone || "—"}</span></div>
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700"><ClipboardList className="h-4 w-4" /> Завдання ({detail.tasks?.length || 0})</h4>
                      {(detail.tasks || []).length === 0 ? <p className="text-xs text-slate-400">Немає пов'язаних завдань</p> : (
                        <ul className="space-y-2">
                          {detail.tasks.map((t) => {
                            const dm = dueMeta(t.due_at);
                            return (
                              <li key={t.id} className="rounded-lg border border-slate-100 p-2.5 text-sm">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="truncate">{t.title}</span>
                                  <StatusPill tone={TASK_STATUS_TONE[t.status]}>{TASK_STATUS_LABELS[t.status]}</StatusPill>
                                </div>
                                <div className={`mt-0.5 text-xs ${dm.overdue ? "text-[#B91C1C]" : "text-slate-400"}`}>{dm.label}</div>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700"><Phone className="h-4 w-4" /> Дзвінки ({detail.calls?.length || 0})</h4>
                      {(detail.calls || []).length === 0 ? <p className="text-xs text-slate-400">Немає історії дзвінків</p> : (
                        <ul className="space-y-2">
                          {detail.calls.map((c) => (
                            <li key={c.id} className="rounded-lg border border-slate-100 p-2.5 text-sm">
                              <div className="flex items-center justify-between gap-2">
                                <span>{fmtDateTime(c.started_at)}</span>
                                <StatusPill tone={CALL_STATUS_TONE[c.status]}>{CALL_STATUS_LABELS[c.status]}</StatusPill>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {detail.lead?.notes && <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600">{detail.lead.notes}</div>}
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Видалити лід?</AlertDialogTitle>
            <AlertDialogDescription>«{confirmDel?.company || confirmDel?.name}» буде видалено безповоротно.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Скасувати</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} className="bg-[#B91C1C] hover:bg-[#991B1B]">Видалити</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const Field = ({ label, children }) => (
  <label className="block">
    <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
    {children}
  </label>
);
