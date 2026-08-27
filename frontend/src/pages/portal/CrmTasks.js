// Wave 5A: Tasks workspace
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { ListTodo, Plus, Pencil, Trash2, Play, CheckCircle2, AlertTriangle, Clock, Search, Filter } from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDate, fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";

const PRIORITY_LABEL = { low: "Низький", medium: "Середній", high: "Високий", urgent: "Терміновий" };
const PRIORITY_OPTS = Object.entries(PRIORITY_LABEL).map(([value, label]) => ({ value, label }));
const STATUS_LABEL = { pending: "Очікує", in_progress: "У роботі", completed: "Виконано", cancelled: "Скасовано" };
const STATUS_OPTS = Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }));
const FILTERS = [
  { key: "", label: "Усі" },
  { key: "today", label: "Сьогодні" },
  { key: "tomorrow", label: "Завтра" },
  { key: "week", label: "Тиждень" },
  { key: "overdue", label: "Прострочені" },
  { key: "no_deadline", label: "Без дедлайну" },
];

function TaskDialog({ open, onOpenChange, initial, assignees, onSaved }) {
  const [f, setF] = useState({ title: "", description: "", assigneeId: "", priority: "medium", dueDate: "", type: "general", comment: "" });
  const [busy, setBusy] = useState(false);
  const isEdit = !!initial?.id;
  useEffect(() => {
    if (!open) return;
    if (initial) {
      setF({
        title: initial.title || "", description: initial.description || "",
        assigneeId: initial.assigneeId || "", priority: initial.priority || "medium",
        dueDate: (initial.dueDate || "").slice(0, 16), type: initial.type || "general", comment: initial.comment || "",
      });
    } else { setF({ title: "", description: "", assigneeId: "", priority: "medium", dueDate: "", type: "general", comment: "" }); }
  }, [open, initial]);
  const submit = async () => {
    if (!f.title.trim()) return toast.error("Назва обов'язкова");
    if (!isEdit && !f.assigneeId) return toast.error("Оберіть виконавця");
    setBusy(true);
    try {
      const payload = {
        title: f.title.trim(),
        description: f.description.trim() || null,
        assigneeId: f.assigneeId,
        priority: f.priority, type: f.type,
        dueDate: f.dueDate ? new Date(f.dueDate).toISOString() : null,
        comment: f.comment.trim() || null,
      };
      if (isEdit) await CrmAPI.taskUpdate(initial.id, payload);
      else await CrmAPI.taskCreate(payload);
      toast.success(isEdit ? "Завдання оновлено" : "Завдання створено");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl" data-testid="crmtask-dialog">
        <DialogHeader><DialogTitle>{isEdit ? "Редагувати завдання" : "Нове завдання"}</DialogTitle><DialogDescription>Прив’язка до виконавця (manager / team_lead) обов’язкова.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Назва *</Label><Input value={f.title} onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} data-testid="crmtask-title" /></div>
          <div className="grid gap-1.5"><Label>Опис</Label><Textarea rows={2} value={f.description} onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Виконавець *</Label>
              <Select value={f.assigneeId} onValueChange={(v) => setF((p) => ({ ...p, assigneeId: v }))} disabled={isEdit}>
                <SelectTrigger data-testid="crmtask-assignee"><SelectValue placeholder="Оберіть…" /></SelectTrigger>
                <SelectContent>{(assignees || []).map((a) => <SelectItem key={a.id} value={a.id}>{a.displayName || a.name || a.email} ({a.role})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Пріоритет</Label>
              <Select value={f.priority} onValueChange={(v) => setF((p) => ({ ...p, priority: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITY_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Дедлайн</Label><Input type="datetime-local" value={f.dueDate} onChange={(e) => setF((p) => ({ ...p, dueDate: e.target.value }))} data-testid="crmtask-due" /></div>
            <div className="grid gap-1.5"><Label>Тип</Label><Input value={f.type} onChange={(e) => setF((p) => ({ ...p, type: e.target.value }))} placeholder="general / call / followup" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Коментар</Label><Textarea rows={2} value={f.comment} onChange={(e) => setF((p) => ({ ...p, comment: e.target.value }))} /></div>
        </div>
        <DialogFooter><Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button><Button onClick={submit} disabled={busy} data-testid="crmtask-submit">{busy ? "Збереження…" : isEdit ? "Зберегти" : "Створити"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PriorityBadge({ value }) {
  const m = { urgent: "border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]", high: "border-[#FED7AA] bg-[#FFF7ED] text-[#9A3412]", medium: "border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]", low: "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]" };
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${m[value] || m.medium}`}>{PRIORITY_LABEL[value] || value}</span>;
}

export default function CrmTasks() {
  useSeo("Завдання · CRM", "Робочий простір завдань команди.");
  const { user } = useAuth();
  const canEdit = ["admin", "team_lead"].includes(user?.role);
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [assignees, setAssignees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState({ open: false, initial: null });
  const [confirmDel, setConfirmDel] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter ? { filter, limit: 200 } : { limit: 200 };
      const [t, s, a] = await Promise.all([
        CrmAPI.tasks(params),
        CrmAPI.taskStats().catch(() => ({ stats: {} })),
        CrmAPI.eligibleAssignees().catch(() => ({ items: [] })),
      ]);
      setTasks(t.data || t.items || []);
      setStats(s.stats || {});
      setAssignees(a.items || []);
    } catch { /* empty */ } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!q.trim()) return tasks;
    const ql = q.toLowerCase();
    return tasks.filter((t) => (t.title || "").toLowerCase().includes(ql) || (t.assigneeName || "").toLowerCase().includes(ql) || (t.description || "").toLowerCase().includes(ql));
  }, [tasks, q]);

  const setStatus = async (t, status) => {
    try {
      if (status === "in_progress") await CrmAPI.taskStart(t.id);
      else if (status === "completed") await CrmAPI.taskComplete(t.id, {});
      else await CrmAPI.taskUpdate(t.id, { status });
      toast.success("Статус оновлено");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося"); }
  };

  const handleDelete = async (t) => {
    try { await CrmAPI.taskDelete(t.id); toast.success("Видалено"); setTasks((p) => p.filter((x) => x.id !== t.id)); }
    catch { toast.error("Не вдалося видалити"); } finally { setConfirmDel(null); }
  };

  return (
    <div data-testid="portal-crm-tasks">
      <PageHeader title="Завдання" subtitle="Робоча черга команди · фільтри today / tomorrow / week / overdue" actions={canEdit && <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2" data-testid="crmtask-create-button"><Plus className="h-4 w-4" /> Нове завдання</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={ListTodo} label="Усього" value={stats.total ?? 0} testid="crmtask-kpi-total" />
        <StatCard icon={Clock} label="Очікують" value={stats.pending ?? 0} testid="crmtask-kpi-pending" />
        <StatCard icon={CheckCircle2} label="Виконані" value={stats.completed ?? 0} testid="crmtask-kpi-done" />
        <StatCard icon={AlertTriangle} label="Прострочені" value={stats.overdue ?? 0} testid="crmtask-kpi-overdue" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={filter} onValueChange={setFilter}>
          <TabsList>{FILTERS.map((f) => <TabsTrigger key={f.key} value={f.key} data-testid={`crmtask-filter-${f.key || "all"}`}>{f.label}</TabsTrigger>)}</TabsList>
        </Tabs>
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук…" className="pl-9" data-testid="crmtask-search" />
        </div>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
          : filtered.length === 0 ? <EmptyState icon={ListTodo} title="Завдань немає" hint="Очистіть фільтр або створіть перше завдання." action={canEdit && <Button onClick={() => setDialog({ open: true, initial: null })} className="gap-2"><Plus className="h-4 w-4" /> Створити</Button>} testid="crmtask-empty" />
          : (
            <Table>
              <TableHeader><TableRow><TableHead>Завдання</TableHead><TableHead>Виконавець</TableHead><TableHead>Дедлайн</TableHead><TableHead>Пріоритет</TableHead><TableHead>Статус</TableHead>{canEdit && <TableHead className="w-24"></TableHead>}</TableRow></TableHeader>
              <TableBody>{filtered.map((t) => {
                const overdue = t.dueDate && new Date(t.dueDate) < new Date() && t.status !== "completed";
                return (
                  <TableRow key={t.id} data-testid="crmtask-row">
                    <TableCell><div className="font-medium text-slate-900">{t.title}</div>{t.description && <div className="mt-0.5 text-xs text-slate-500 max-w-md truncate">{t.description}</div>}</TableCell>
                    <TableCell className="text-sm text-slate-600">{t.assigneeName || t.assigneeId || "—"}</TableCell>
                    <TableCell className={`text-sm ${overdue ? "text-[#991B1B] font-medium" : "text-slate-600"}`}>{t.dueDate ? fmtDateTime(t.dueDate) : "—"}</TableCell>
                    <TableCell><PriorityBadge value={t.priority} /></TableCell>
                    <TableCell>
                      <Select value={t.status || "pending"} onValueChange={(v) => setStatus(t, v)}>
                        <SelectTrigger className="h-8 w-[150px]" data-testid="crmtask-status"><SelectValue /></SelectTrigger>
                        <SelectContent>{STATUS_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                      </Select>
                    </TableCell>
                    {canEdit && <TableCell>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => setDialog({ open: true, initial: t })} data-testid="crmtask-edit"><Pencil className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => setConfirmDel(t)} data-testid="crmtask-delete"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button>
                      </div>
                    </TableCell>}
                  </TableRow>
                );
              })}</TableBody>
            </Table>
          )}
      </div>

      <TaskDialog open={dialog.open} onOpenChange={(v) => setDialog((p) => ({ ...p, open: v }))} initial={dialog.initial} assignees={assignees} onSaved={load} />
      <Dialog open={!!confirmDel} onOpenChange={(v) => !v && setConfirmDel(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Видалити завдання?</DialogTitle><DialogDescription>Дія незворотна. «{confirmDel?.title}» буде видалено.</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="secondary" onClick={() => setConfirmDel(null)}>Скасувати</Button><Button onClick={() => handleDelete(confirmDel)} data-testid="crmtask-confirm-delete" className="bg-[#991B1B] hover:bg-[#7F1D1D]">Видалити</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
