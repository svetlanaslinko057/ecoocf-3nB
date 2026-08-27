import React, { useEffect, useState, useCallback } from "react";
import {
  Users, UserPlus, ShieldCheck, ShieldOff, Trophy, Pencil, Trash2, KeyRound,
  Search, TrendingUp, ClipboardList, Crown,
} from "lucide-react";
import { StaffAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import { fmtMoney } from "@/lib/managerMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const ROLE_LABELS = { admin: "Адміністратор", manager: "Менеджер" };
const EMPTY = { name: "", email: "", password: "", phone: "", role: "manager" };

export default function StaffCenter() {
  useSeo("Центр персоналу", "Керування менеджерами, 2FA-статус, продуктивність.");
  const { user } = useAuth();
  const [ov, setOv] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [resetting, setResetting] = useState(null);
  const [newPwd, setNewPwd] = useState("");
  const [confirmDel, setConfirmDel] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([StaffAPI.overview(), StaffAPI.members({ q: q || undefined })])
      .then(([o, m]) => { setOv(o); setMembers(m.items || []); })
      .catch(() => toast.error("Не вдалося завантажити персонал"))
      .finally(() => setLoading(false));
  }, [q]);

  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  const create = async () => {
    if (!form.name.trim() || !form.email.trim()) return toast.error("Вкажіть ім'я та email");
    if (form.password.length < 6) return toast.error("Пароль ≥ 6 символів");
    setBusy(true);
    try { await StaffAPI.createMember(form); toast.success("Співробітника створено"); setCreateOpen(false); setForm(EMPTY); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося створити"); }
    finally { setBusy(false); }
  };

  const saveEdit = async () => {
    setBusy(true);
    try { await StaffAPI.updateMember(editing.id, { name: editing.name, phone: editing.phone, role: editing.role }); toast.success("Оновлено"); setEditing(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося"); }
    finally { setBusy(false); }
  };

  const toggleActive = async (m) => {
    setMembers((p) => p.map((x) => (x.id === m.id ? { ...x, active: !x.active } : x)));
    try { await StaffAPI.toggleActive(m.id); } catch { toast.error("Не вдалося"); load(); }
  };

  const doReset = async () => {
    if (newPwd.length < 6) return toast.error("Пароль ≥ 6 символів");
    setBusy(true);
    try { await StaffAPI.resetPassword(resetting.id, newPwd); toast.success("Пароль скинуто"); setResetting(null); setNewPwd(""); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося"); }
    finally { setBusy(false); }
  };

  const doDelete = async () => {
    try { await StaffAPI.deleteMember(confirmDel.id); toast.success("Видалено"); setMembers((p) => p.filter((x) => x.id !== confirmDel.id)); }
    catch (e) { toast.error(e?.response?.data?.detail || "Не вдалося видалити"); }
    finally { setConfirmDel(null); }
  };

  const s = ov?.staff || {};
  const t = ov?.totals || {};

  return (
    <div data-testid="staff-center">
      <PageHeader
        title="Центр персоналу"
        subtitle="Контроль роботи менеджерів, 2FA-статус та продуктивність"
        actions={<Button onClick={() => { setForm(EMPTY); setCreateOpen(true); }} data-testid="new-staff-button"><UserPlus className="mr-2 h-4 w-4" /> Новий співробітник</Button>}
      />

      {loading && !ov ? <TableSkeleton rows={6} /> : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={Users} label="Менеджерів" value={s.managers ?? 0} hint={`активних: ${s.active ?? 0}`} testid="staff-kpi-managers" />
            <StatCard icon={ShieldCheck} label="З 2FA" value={s.twofa_enabled ?? 0} hint={`із ${s.total ?? 0} акаунтів`} testid="staff-kpi-2fa" />
            <StatCard icon={Trophy} label="Виграно (сума)" value={fmtMoney(t.won_value)} hint={`угод: ${t.won ?? 0}`} testid="staff-kpi-won" />
            <StatCard icon={ClipboardList} label="Прострочені задачі" value={t.overdue_tasks ?? 0} hint={`відкритих: ${t.open_tasks ?? 0}`} testid="staff-kpi-overdue" />
          </div>

          <div className="mb-4 flex items-center justify-end">
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук співробітника…" className="pl-9" data-testid="staff-search" />
            </div>
          </div>

          {members.length === 0 ? (
            <EmptyState icon={Users} title="Співробітників не знайдено" hint="Створіть першого менеджера." action={<Button onClick={() => setCreateOpen(true)}><UserPlus className="mr-2 h-4 w-4" /> Новий співробітник</Button>} testid="staff-empty" />
          ) : (
            <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="px-4 py-3 font-semibold">Співробітник</th>
                      <th className="px-4 py-3 font-semibold">Роль</th>
                      <th className="px-4 py-3 font-semibold">2FA</th>
                      <th className="px-4 py-3 font-semibold text-center">Ліди</th>
                      <th className="px-4 py-3 font-semibold text-center">Конв.</th>
                      <th className="px-4 py-3 font-semibold text-right">Виграно</th>
                      <th className="px-4 py-3 font-semibold text-center">Активний</th>
                      <th className="px-4 py-3 font-semibold text-right">Дії</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.id} className="border-b border-slate-50 last:border-0 hover:bg-[#F2F8F3]/50" data-testid={`staff-row-${m.id}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0E5E3A] text-sm font-semibold text-[#5BC47A]">{(m.name || m.email || "?").charAt(0).toUpperCase()}</span>
                            <div>
                              <div className="font-medium text-slate-900">{m.name}</div>
                              <div className="text-xs text-slate-400">{m.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {m.role === "admin"
                            ? <StatusPill tone="info"><Crown className="mr-1 inline h-3 w-3" />{ROLE_LABELS.admin}</StatusPill>
                            : <StatusPill tone="muted">{ROLE_LABELS.manager}</StatusPill>}
                        </td>
                        <td className="px-4 py-3">
                          {m.twofa_enabled
                            ? <StatusPill tone="pos" testid={`staff-2fa-on-${m.id}`}><ShieldCheck className="mr-1 inline h-3 w-3" />Увімкнено</StatusPill>
                            : <StatusPill tone="warn" testid={`staff-2fa-off-${m.id}`}><ShieldOff className="mr-1 inline h-3 w-3" />Вимкнено</StatusPill>}
                        </td>
                        <td className="px-4 py-3 text-center text-slate-700">{m.kpis?.leads_total ?? "—"}</td>
                        <td className="px-4 py-3 text-center text-slate-700">{m.role === "manager" ? `${m.kpis?.conversion ?? 0}%` : "—"}</td>
                        <td className="px-4 py-3 text-right font-medium text-slate-800">{m.role === "manager" ? fmtMoney(m.kpis?.won_value) : "—"}</td>
                        <td className="px-4 py-3 text-center">
                          <Switch checked={!!m.active} onCheckedChange={() => toggleActive(m)} disabled={m.id === user?.id} data-testid={`staff-active-${m.id}`} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="icon" title="Редагувати" onClick={() => setEditing({ ...m })} data-testid={`staff-edit-${m.id}`}><Pencil className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" title="Скинути пароль" onClick={() => { setResetting(m); setNewPwd(""); }} data-testid={`staff-reset-${m.id}`}><KeyRound className="h-4 w-4 text-[#B45309]" /></Button>
                            <Button variant="ghost" size="icon" title="Видалити" onClick={() => setConfirmDel(m)} disabled={m.id === user?.id} data-testid={`staff-del-${m.id}`}><Trash2 className="h-4 w-4 text-[#B91C1C]" /></Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Новий співробітник</DialogTitle>
            <DialogDescription>Створіть акаунт менеджера або адміністратора</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Ім'я *"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="staff-form-name" /></Field>
            <Field label="Email *"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="staff-form-email" /></Field>
            <Field label="Пароль *"><Input type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="мін. 6 символів" data-testid="staff-form-password" /></Field>
            <Field label="Телефон"><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
            <Field label="Роль">
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="staff-form-role"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="manager">Менеджер</SelectItem><SelectItem value="admin">Адміністратор</SelectItem></SelectContent>
              </Select>
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Скасувати</Button>
            <Button onClick={create} disabled={busy} data-testid="staff-form-save">{busy ? "Збереження…" : "Створити"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Редагувати співробітника</DialogTitle><DialogDescription>{editing?.email}</DialogDescription></DialogHeader>
          {editing && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Ім'я"><Input value={editing.name || ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })} data-testid="staff-edit-name" /></Field>
              <Field label="Телефон"><Input value={editing.phone || ""} onChange={(e) => setEditing({ ...editing, phone: e.target.value })} /></Field>
              <Field label="Роль">
                <Select value={editing.role} onValueChange={(v) => setEditing({ ...editing, role: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="manager">Менеджер</SelectItem><SelectItem value="admin">Адміністратор</SelectItem></SelectContent>
                </Select>
              </Field>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Скасувати</Button>
            <Button onClick={saveEdit} disabled={busy} data-testid="staff-edit-save">Зберегти</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset password */}
      <Dialog open={!!resetting} onOpenChange={(o) => !o && setResetting(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Скинути пароль</DialogTitle><DialogDescription>Новий пароль для «{resetting?.name}»</DialogDescription></DialogHeader>
          <Field label="Новий пароль"><Input type="text" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} placeholder="мін. 6 символів" data-testid="staff-reset-input" /></Field>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetting(null)}>Скасувати</Button>
            <Button onClick={doReset} disabled={busy} data-testid="staff-reset-save">Скинути</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Видалити співробітника?</AlertDialogTitle>
            <AlertDialogDescription>«{confirmDel?.name}» ({confirmDel?.email}) буде видалено разом із налаштуваннями 2FA.</AlertDialogDescription>
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
