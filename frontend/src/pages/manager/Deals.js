import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, Pencil, Search, Trophy, Wallet, BarChart3 } from "lucide-react";
import { ManagerAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import {
  DEAL_STAGE_ORDER, DEAL_STAGE_LABELS, DEAL_STAGE_TONE, fmtMoney, fmtDate,
} from "@/lib/managerMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const TABS = [["all", "Усі"], ...DEAL_STAGE_ORDER.map((s) => [s, DEAL_STAGE_LABELS[s]])];
const EMPTY = { title: "", company: "", customerName: "", amount: "", currency: "UAH", stage: "new", wasteType: "" };

export default function ManagerDeals() {
  useSeo("Мої угоди", "Управління угодами менеджера.");
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    ManagerAPI.deals({ stage: tab, q: q || undefined })
      .then((r) => setItems(r.items || []))
      .catch(() => toast.error("Не вдалося завантажити угоди"))
      .finally(() => setLoading(false));
  }, [tab, q]);

  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  const totals = items.reduce((acc, d) => {
    const amt = Number(d.amount) || 0;
    if (d.stage === "won") acc.won += amt;
    else if (d.stage !== "lost") acc.pipeline += amt;
    return acc;
  }, { won: 0, pipeline: 0 });

  const openCreate = () => { setForm(EMPTY); setDialog({ mode: "create" }); };
  const openEdit = (d) => { setForm({ ...EMPTY, ...d, amount: d.amount || "" }); setDialog({ mode: "edit", data: d }); };

  const save = async () => {
    if (!form.title.trim()) return toast.error("Вкажіть назву угоди");
    setSaving(true);
    try {
      if (dialog.mode === "create") { await ManagerAPI.createDeal(form); toast.success("Угоду створено"); }
      else { await ManagerAPI.updateDeal(dialog.data.id, form); toast.success("Угоду оновлено"); }
      setDialog(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setSaving(false); }
  };

  const changeStage = async (d, stage) => {
    setItems((p) => p.map((x) => (x.id === d.id ? { ...x, stage } : x)));
    try { await ManagerAPI.updateDeal(d.id, { stage }); toast.success("Етап оновлено"); if (tab !== "all") load(); }
    catch { toast.error("Не вдалося"); load(); }
  };

  const doDelete = async () => {
    try { await ManagerAPI.deleteDeal(confirmDel.id); toast.success("Угоду видалено"); setItems((p) => p.filter((x) => x.id !== confirmDel.id)); }
    catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  return (
    <div data-testid="manager-deals">
      <PageHeader
        title="Мої угоди"
        subtitle="Комерційна воронка та підписані контракти"
        actions={<Button onClick={openCreate} data-testid="new-deal-button"><Plus className="mr-2 h-4 w-4" /> Нова угода</Button>}
      />

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard icon={Wallet} label="У воронці" value={fmtMoney(totals.pipeline)} testid="deals-kpi-pipeline" />
        <StatCard icon={Trophy} label="Виграно (показано)" value={fmtMoney(totals.won)} testid="deals-kpi-won" />
        <StatCard icon={Trophy} label="Угод (показано)" value={items.length} testid="deals-kpi-count" />
      </div>

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {TABS.map(([v, label]) => (
            <button key={v} onClick={() => setTab(v)} data-testid={`deal-tab-${v}`}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${tab === v ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук угод…" className="pl-9" data-testid="deal-search" />
        </div>
      </div>

      {loading ? <TableSkeleton rows={6} /> : items.length === 0 ? (
        <EmptyState icon={Trophy} title="Угод не знайдено" hint="Створіть угоду або конвертуйте лід." action={<Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" /> Нова угода</Button>} testid="deals-empty" />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">Угода</th>
                  <th className="px-4 py-3 font-semibold">Клієнт</th>
                  <th className="px-4 py-3 font-semibold text-right">Сума</th>
                  <th className="px-4 py-3 font-semibold">Етап</th>
                  <th className="px-4 py-3 font-semibold">Створено</th>
                  <th className="px-4 py-3 font-semibold text-right">Дії</th>
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} className="border-b border-slate-50 last:border-0 hover:bg-[#F2F8F3]/50" data-testid={`deal-row-${d.id}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{d.title}</div>
                      {d.wasteType && <div className="max-w-[220px] truncate text-xs text-slate-400">{d.wasteType}</div>}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{d.company || d.customerName || "—"}</td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-800">{fmtMoney(d.amount, d.currency === "UAH" ? "₴" : d.currency)}</td>
                    <td className="px-4 py-3">
                      <Select value={d.stage} onValueChange={(v) => changeStage(d, v)}>
                        <SelectTrigger className="h-8 w-[140px]" data-testid={`deal-stage-${d.id}`}><SelectValue /></SelectTrigger>
                        <SelectContent>{DEAL_STAGE_ORDER.map((s) => <SelectItem key={s} value={s}>{DEAL_STAGE_LABELS[s]}</SelectItem>)}</SelectContent>
                      </Select>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(d.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => navigate(`/app/cabinet/deals/${d.id}`)} data-testid={`deal-360-${d.id}`} title="Угода 360"><BarChart3 className="h-4 w-4 text-[#0E5E3A]" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(d)} data-testid={`deal-edit-${d.id}`}><Pencil className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => setConfirmDel(d)} data-testid={`deal-del-${d.id}`}><Trash2 className="h-4 w-4 text-[#B91C1C]" /></Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{dialog?.mode === "edit" ? "Редагувати угоду" : "Нова угода"}</DialogTitle>
            <DialogDescription>Комерційна угода з клієнтом</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2"><Field label="Назва угоди *"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="deal-form-title" /></Field></div>
            <Field label="Компанія"><Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></Field>
            <Field label="Контакт"><Input value={form.customerName} onChange={(e) => setForm({ ...form, customerName: e.target.value })} /></Field>
            <Field label="Сума"><Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="deal-form-amount" /></Field>
            <Field label="Валюта">
              <Select value={form.currency} onValueChange={(v) => setForm({ ...form, currency: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="UAH">UAH (₴)</SelectItem><SelectItem value="EUR">EUR (€)</SelectItem><SelectItem value="USD">USD ($)</SelectItem></SelectContent>
              </Select>
            </Field>
            <Field label="Етап">
              <Select value={form.stage} onValueChange={(v) => setForm({ ...form, stage: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{DEAL_STAGE_ORDER.map((s) => <SelectItem key={s} value={s}>{DEAL_STAGE_LABELS[s]}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field label="Тип відходів"><Input value={form.wasteType} onChange={(e) => setForm({ ...form, wasteType: e.target.value })} /></Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Скасувати</Button>
            <Button onClick={save} disabled={saving} data-testid="deal-form-save">{saving ? "Збереження…" : "Зберегти"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Видалити угоду?</AlertDialogTitle>
            <AlertDialogDescription>«{confirmDel?.title}» буде видалено безповоротно.</AlertDialogDescription>
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
  <label className="block"><span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>{children}</label>
);
