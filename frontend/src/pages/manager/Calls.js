import React, { useEffect, useState, useCallback } from "react";
import { Plus, PhoneIncoming, PhoneOutgoing, PhoneMissed, Phone } from "lucide-react";
import { ManagerAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import {
  CALL_STATUS_LABELS, CALL_STATUS_TONE, CALL_DIR_LABELS, fmtDateTime, durationStr,
} from "@/lib/managerMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const TABS = [["all", "Усі"], ["inbound", "Вхідні"], ["outbound", "Вихідні"], ["missed", "Пропущені"]];
const EMPTY = { contactName: "", phone: "", direction: "outbound", status: "answered", duration_sec: "", note: "" };

export default function ManagerCalls() {
  useSeo("Мої дзвінки", "Журнал дзвінків менеджера.");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    ManagerAPI.calls({ filter: tab })
      .then((r) => setItems(r.items || []))
      .catch(() => toast.error("Не вдалося завантажити дзвінки"))
      .finally(() => setLoading(false));
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const stats = items.reduce((a, c) => {
    a.total++;
    if (c.status === "answered") a.answered++;
    if (c.status === "missed") a.missed++;
    return a;
  }, { total: 0, answered: 0, missed: 0 });

  const save = async () => {
    if (!form.phone.trim() && !form.contactName.trim()) return toast.error("Вкажіть контакт або номер");
    setSaving(true);
    try {
      await ManagerAPI.logCall({ ...form, duration_sec: Number(form.duration_sec) || 0 });
      toast.success("Дзвінок зафіксовано");
      setDialog(false); setForm(EMPTY); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося зберегти"); }
    finally { setSaving(false); }
  };

  return (
    <div data-testid="manager-calls">
      <PageHeader
        title="Мої дзвінки"
        subtitle="Журнал комунікацій з клієнтами"
        actions={<Button onClick={() => setDialog(true)} data-testid="log-call-button"><Plus className="mr-2 h-4 w-4" /> Зафіксувати дзвінок</Button>}
      />

      <div className="mb-6 grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-4">
        <StatCard icon={Phone} label="Усього (показано)" value={stats.total} testid="calls-kpi-total" />
        <StatCard icon={PhoneIncoming} label="Відповіли" value={stats.answered} testid="calls-kpi-answered" />
        <StatCard icon={PhoneMissed} label="Пропущені" value={stats.missed} testid="calls-kpi-missed" />
      </div>

      <div className="mb-5 flex flex-wrap gap-1.5">
        {TABS.map(([v, label]) => (
          <button key={v} onClick={() => setTab(v)} data-testid={`call-tab-${v}`}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${tab === v ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <TableSkeleton rows={6} /> : items.length === 0 ? (
        <EmptyState icon={Phone} title="Дзвінків не знайдено" hint="Зафіксуйте дзвінок вручну." action={<Button onClick={() => setDialog(true)}><Plus className="mr-2 h-4 w-4" /> Зафіксувати дзвінок</Button>} testid="calls-empty" />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">Напрям</th>
                  <th className="px-4 py-3 font-semibold">Контакт</th>
                  <th className="px-4 py-3 font-semibold">Час</th>
                  <th className="px-4 py-3 font-semibold">Тривалість</th>
                  <th className="px-4 py-3 font-semibold">Статус</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-b border-slate-50 last:border-0 hover:bg-[#F2F8F3]/50" data-testid={`call-row-${c.id}`}>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-2 text-slate-600">
                        {c.direction === "inbound" ? <PhoneIncoming className="h-4 w-4 text-[#0E5E3A]" /> : <PhoneOutgoing className="h-4 w-4 text-slate-400" />}
                        {CALL_DIR_LABELS[c.direction] || c.direction}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{c.contactName || "—"}</div>
                      <div className="text-xs text-slate-400">{c.phone}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{fmtDateTime(c.started_at)}</td>
                    <td className="px-4 py-3 text-slate-600">{durationStr(c.duration_sec)}</td>
                    <td className="px-4 py-3"><StatusPill tone={CALL_STATUS_TONE[c.status]}>{CALL_STATUS_LABELS[c.status] || c.status}</StatusPill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={dialog} onOpenChange={setDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Зафіксувати дзвінок</DialogTitle>
            <DialogDescription>Додайте запис у журнал комунікацій</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Контакт"><Input value={form.contactName} onChange={(e) => setForm({ ...form, contactName: e.target.value })} data-testid="call-form-name" /></Field>
            <Field label="Телефон"><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="call-form-phone" /></Field>
            <Field label="Напрям">
              <Select value={form.direction} onValueChange={(v) => setForm({ ...form, direction: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="outbound">Вихідний</SelectItem><SelectItem value="inbound">Вхідний</SelectItem></SelectContent>
              </Select>
            </Field>
            <Field label="Статус">
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="answered">Відповіли</SelectItem>
                  <SelectItem value="missed">Пропущений</SelectItem>
                  <SelectItem value="no_answer">Без відповіді</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="Тривалість, с"><Input type="number" value={form.duration_sec} onChange={(e) => setForm({ ...form, duration_sec: e.target.value })} /></Field>
            <div className="sm:col-span-2"><Field label="Нотатка"><Textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(false)}>Скасувати</Button>
            <Button onClick={save} disabled={saving} data-testid="call-form-save">{saving ? "Збереження…" : "Зберегти"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Field = ({ label, children }) => (
  <label className="block"><span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>{children}</label>
);
