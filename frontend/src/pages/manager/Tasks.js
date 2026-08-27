import React, { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, CheckCircle2, Circle, Clock, CalendarClock } from "lucide-react";
import { ManagerAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import { TASK_STATUS_LABELS, TASK_STATUS_TONE, dueMeta } from "@/lib/managerMeta";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const TABS = [["all", "Усі"], ["today", "Сьогодні"], ["overdue", "Прострочені"], ["open", "Відкриті"], ["completed", "Виконані"]];

function defaultDue() {
  const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(12, 0, 0, 0);
  // local datetime-local value
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ManagerTasks() {
  useSeo("Мої завдання", "Завдання та нагадування менеджера.");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "normal", due: defaultDue() });
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    ManagerAPI.tasks({ filter: tab })
      .then((r) => setItems(r.items || []))
      .catch(() => toast.error("Не вдалося завантажити завдання"))
      .finally(() => setLoading(false));
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!form.title.trim()) return toast.error("Вкажіть назву завдання");
    setSaving(true);
    try {
      await ManagerAPI.createTask({
        title: form.title,
        description: form.description,
        priority: form.priority,
        due_at: form.due ? new Date(form.due).toISOString() : undefined,
      });
      toast.success("Завдання створено");
      setDialog(false);
      setForm({ title: "", description: "", priority: "normal", due: defaultDue() });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setSaving(false); }
  };

  const toggle = async (t) => {
    const next = t.status === "completed" ? "pending" : "completed";
    setItems((p) => p.map((x) => (x.id === t.id ? { ...x, status: next } : x)));
    try { await ManagerAPI.updateTask(t.id, { status: next }); if (tab !== "all") load(); }
    catch { toast.error("Не вдалося оновити"); load(); }
  };

  const doDelete = async () => {
    try { await ManagerAPI.deleteTask(confirmDel.id); toast.success("Видалено"); setItems((p) => p.filter((x) => x.id !== confirmDel.id)); }
    catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  return (
    <div data-testid="manager-tasks">
      <PageHeader
        title="Мої завдання"
        subtitle="Нагадування, дзвінки та дедлайни"
        actions={<Button onClick={() => setDialog(true)} data-testid="new-task-button"><Plus className="mr-2 h-4 w-4" /> Нове завдання</Button>}
      />

      <div className="mb-5 flex flex-wrap gap-1.5">
        {TABS.map(([v, label]) => (
          <button key={v} onClick={() => setTab(v)} data-testid={`task-tab-${v}`}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${tab === v ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <TableSkeleton rows={6} /> : items.length === 0 ? (
        <EmptyState icon={CalendarClock} title="Завдань немає" hint="Створіть завдання, щоб нічого не забути." action={<Button onClick={() => setDialog(true)}><Plus className="mr-2 h-4 w-4" /> Нове завдання</Button>} testid="tasks-empty" />
      ) : (
        <div className="space-y-2.5">
          {items.map((t) => {
            const dm = dueMeta(t.due_at);
            const done = t.status === "completed";
            return (
              <div key={t.id} data-testid={`task-row-${t.id}`}
                className={`flex items-center gap-3 rounded-xl border bg-white p-3.5 shadow-[0_1px_3px_rgba(11,26,20,0.05)] transition-colors ${done ? "border-slate-100 opacity-70" : dm.overdue ? "border-[#FECACA]" : "border-[#0B1A14]/[0.06]"}`}>
                <button onClick={() => toggle(t)} data-testid={`task-toggle-${t.id}`} className="shrink-0">
                  {done ? <CheckCircle2 className="h-5 w-5 text-[#0E5E3A]" /> : <Circle className="h-5 w-5 text-slate-300 hover:text-[#0E5E3A]" />}
                </button>
                <div className="min-w-0 flex-1">
                  <div className={`truncate text-sm font-medium ${done ? "text-slate-400 line-through" : "text-slate-800"}`}>{t.title}</div>
                  {t.description && <div className="truncate text-xs text-slate-400">{t.description}</div>}
                </div>
                {t.priority === "high" && !done && <StatusPill tone="danger">Високий</StatusPill>}
                <div className={`flex shrink-0 items-center gap-1.5 text-xs ${dm.overdue && !done ? "text-[#B91C1C]" : "text-slate-400"}`}>
                  <Clock className="h-3.5 w-3.5" /> {dm.label}
                </div>
                <StatusPill tone={TASK_STATUS_TONE[t.status]}>{TASK_STATUS_LABELS[t.status]}</StatusPill>
                <Button variant="ghost" size="icon" onClick={() => setConfirmDel(t)} data-testid={`task-del-${t.id}`}><Trash2 className="h-4 w-4 text-[#B91C1C]" /></Button>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={dialog} onOpenChange={setDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Нове завдання</DialogTitle>
            <DialogDescription>Заплануйте дію або нагадування</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Field label="Назва *"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="task-form-title" placeholder="напр., Передзвонити клієнту" /></Field>
            <Field label="Опис"><Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Термін">
                <Input type="datetime-local" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} data-testid="task-form-due" />
              </Field>
              <Field label="Пріоритет">
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="normal">Звичайний</SelectItem><SelectItem value="high">Високий</SelectItem></SelectContent>
                </Select>
              </Field>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(false)}>Скасувати</Button>
            <Button onClick={save} disabled={saving} data-testid="task-form-save">{saving ? "Збереження…" : "Створити"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Видалити завдання?</AlertDialogTitle>
            <AlertDialogDescription>«{confirmDel?.title}» буде видалено.</AlertDialogDescription>
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
