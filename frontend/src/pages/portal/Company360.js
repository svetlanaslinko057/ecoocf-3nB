import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  Building2, Plus, ClipboardList, FileText, Truck, BadgeCheck, Boxes, Activity,
  Mail, Phone, MapPin, Hash, ArrowLeft, History, MessageSquare, CheckSquare,
  Recycle, Send, Trash2, ChevronRight, ListTodo, User,
} from "lucide-react";
import { PortalAPI, CrmAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDate, fmtDateTime, itemsSummary } from "@/lib/portalMeta";
import { StatusBadge, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import CustomerLabel from "@/components/portal/CustomerLabel";
import { CreateRequestDialog } from "@/components/portal/CreateRequestDialog";
import { OperationDetailDrawer } from "@/components/portal/OperationDetailDrawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

const OBJECT_TYPES = [
  { value: "hospital", label: "Лікарня / клініка" },
  { value: "factory", label: "Завод / виробництво" },
  { value: "lab", label: "Лабораторія" },
  { value: "warehouse", label: "Склад" },
  { value: "gas_station", label: "АЗС" },
  { value: "agrofirm", label: "Агрофірма" },
  { value: "site", label: "Інший об’єкт" },
];

function AddObjectDialog({ open, onOpenChange, companyId, onCreated }) {
  const [f, setF] = useState({ name: "", object_type: "site", address: "", responsible_name: "", responsible_phone: "" });
  const [submitting, setSubmitting] = useState(false);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  useEffect(() => { if (open) setF({ name: "", object_type: "site", address: "", responsible_name: "", responsible_phone: "" }); }, [open]);
  const submit = async () => {
    if (!f.name.trim()) return toast.error("Вкажіть назву об’єкта");
    setSubmitting(true);
    try {
      await PortalAPI.createObject({ company_id: companyId, ...f });
      toast.success("Об’єкт додано");
      onOpenChange(false);
      onCreated && onCreated();
    } catch { toast.error("Не вдалося додати об’єкт"); }
    finally { setSubmitting(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="object-dialog">
        <DialogHeader>
          <DialogTitle>Новий об’єкт</DialogTitle>
          <DialogDescription>Філія / майданчик, де утворюються відходи.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Назва *</Label><Input value={f.name} onChange={set("name")} data-testid="object-name-input" /></div>
          <div className="grid gap-1.5"><Label>Тип об’єкта</Label>
            <Select value={f.object_type} onValueChange={(v) => setF((p) => ({ ...p, object_type: v }))}>
              <SelectTrigger data-testid="object-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>{OBJECT_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Адреса</Label><Input value={f.address} onChange={set("address")} data-testid="object-address-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Відповідальний</Label><Input value={f.responsible_name} onChange={set("responsible_name")} data-testid="object-resp-name-input" /></div>
            <div className="grid gap-1.5"><Label>Телефон</Label><Input value={f.responsible_phone} onChange={set("responsible_phone")} placeholder="+380…" data-testid="object-resp-phone-input" /></div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button>
          <Button onClick={submit} disabled={submitting} data-testid="object-submit">{submitting ? "Збереження…" : "Додати"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const StatPill = ({ icon: Icon, label, value }) => (
  <div className="flex items-center gap-2 rounded-xl border border-[hsl(var(--border))] bg-white px-3 py-2">
    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[hsl(var(--accent))] text-[hsl(var(--primary))]"><Icon className="h-4 w-4" /></span>
    <div><div className="text-base font-semibold leading-none text-slate-900">{value}</div><div className="mt-0.5 text-xs text-slate-500">{label}</div></div>
  </div>
);

function CompanyContacts({ companyId }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    let active = true;
    CrmAPI.companyCustomers(companyId)
      .then((r) => { if (active) setItems(r.items || []); })
      .catch(() => { if (active) setItems([]); });
    return () => { active = false; };
  }, [companyId]);
  return (
    <>
      <div className="my-4 h-px bg-[hsl(var(--border))]" />
      <div className="mb-2 text-sm font-semibold text-slate-900">Контактні особи</div>
      {items === null ? <div className="text-sm text-slate-400">Завантаження…</div>
        : items.length === 0 ? <div className="text-sm text-slate-500">Контактних осіб ще немає.</div>
        : <div className="space-y-1.5" data-testid="company-contacts">{items.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 px-3 py-2">
              <CustomerLabel customer={p} />
            </div>
          ))}</div>}
    </>
  );
}

export default function Company360() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const [objDialog, setObjDialog] = useState(false);
  const [reqDialog, setReqDialog] = useState(false);
  const [drawer, setDrawer] = useState({ open: false, kind: "contract", id: null });
  // Tasks + Comments live state
  const [tasks, setTasks] = useState([]);
  const [comments, setComments] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [taskDialog, setTaskDialog] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(false);
    try { const r = await PortalAPI.company(id); setData(r); }
    catch { setErr(true); } finally { setLoading(false); }
  }, [id]);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try { const r = await PortalAPI.tasks(id); setTasks(r.items || []); }
    catch { /* empty */ } finally { setTasksLoading(false); }
  }, [id]);

  const loadComments = useCallback(async () => {
    setCommentsLoading(true);
    try { const r = await PortalAPI.comments(id); setComments(r.items || []); }
    catch { /* empty */ } finally { setCommentsLoading(false); }
  }, [id]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadTasks(); loadComments(); }, [loadTasks, loadComments]);

  useSeo(data?.company?.name ? `${data.company.name} · Компанія` : "Компанія", "Картка компанії — об'єкти, заявки, контракти, акти.");

  if (loading) return <div data-testid="portal-company360"><div className="mb-6 h-8 w-48 animate-pulse rounded bg-[hsl(var(--secondary))]" /><TableSkeleton rows={6} /></div>;
  if (err || !data) return <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#991B1B]" data-testid="company360-error">Компанію не знайдено. <Link to="/app/companies" className="font-medium underline">До списку</Link></div>;

  const c = data.company;
  const s = data.stats || {};

  return (
    <div data-testid="portal-company360">
      <Link to="/app/companies" className="mb-4 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-[hsl(var(--primary))]" data-testid="company360-back"><ArrowLeft className="h-4 w-4" /> Компанії</Link>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900" data-testid="company360-name">{c.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
            {c.edrpou && <span className="inline-flex items-center gap-1"><Hash className="h-3.5 w-3.5" /> {c.edrpou}</span>}
            {c.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" /> {c.phone}</span>}
            {c.email && <span className="inline-flex items-center gap-1"><Mail className="h-3.5 w-3.5" /> {c.email}</span>}
            {c.address && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {c.address}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" className="gap-2" onClick={() => setObjDialog(true)} data-testid="company360-add-object"><Boxes className="h-4 w-4" /> Об’єкт</Button>
          <Button className="gap-2" onClick={() => setReqDialog(true)} data-testid="company360-create-request"><Plus className="h-4 w-4" /> Заявка</Button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatPill icon={Boxes} label="Об’єкти" value={s.objects ?? 0} />
        <StatPill icon={ClipboardList} label="Заявки" value={s.requests ?? 0} />
        <StatPill icon={FileText} label="Договори" value={s.contracts ?? 0} />
        <StatPill icon={Truck} label="Вивози" value={s.pickups ?? 0} />
        <StatPill icon={BadgeCheck} label="Акти" value={s.acts ?? 0} />
        <StatPill icon={Activity} label="Відкриті" value={s.open_requests ?? 0} />
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="flex w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="overview" data-testid="tab-overview" className="gap-1.5"><Activity className="h-4 w-4" /> Огляд</TabsTrigger>
          <TabsTrigger value="objects" data-testid="tab-objects">Об'єкти</TabsTrigger>
          <TabsTrigger value="requests" data-testid="tab-requests">Заявки</TabsTrigger>
          <TabsTrigger value="contracts" data-testid="tab-contracts">Договори</TabsTrigger>
          <TabsTrigger value="pickups" data-testid="tab-pickups">Вивози</TabsTrigger>
          <TabsTrigger value="acts" data-testid="tab-acts">Акти</TabsTrigger>
          <TabsTrigger value="tasks" data-testid="tab-tasks" className="gap-1.5"><CheckSquare className="h-4 w-4" /> Завдання</TabsTrigger>
          <TabsTrigger value="comments" data-testid="tab-comments" className="gap-1.5"><MessageSquare className="h-4 w-4" /> Коментарі</TabsTrigger>
          <TabsTrigger value="utilization" data-testid="tab-utilization" className="gap-1.5"><Recycle className="h-4 w-4" /> Утилізація</TabsTrigger>
          <TabsTrigger value="timeline" data-testid="tab-timeline">Таймлайн</TabsTrigger>
        </TabsList>

        {/* OVERVIEW */}
        <TabsContent value="overview" className="mt-4">
          <CompanyOverview data={data} tasks={tasks} comments={comments} timeline={data.timeline || []} onOpenObject={(o) => null} onOpenDrawer={(kind, id) => setDrawer({ open: true, kind, id })} />
        </TabsContent>

        {/* OBJECTS */}
        <TabsContent value="objects" className="mt-4">
          {(data.objects || []).length === 0 ? (
            <EmptyState icon={Boxes} title="Об'єктів немає" hint="Додайте філію або майданчик клієнта." action={<Button onClick={() => setObjDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Додати об'єкт</Button>} />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
              <Table>
                <TableHeader><TableRow><TableHead>Назва</TableHead><TableHead>Тип</TableHead><TableHead>Адреса</TableHead><TableHead>Відповідальний</TableHead><TableHead className="w-12"></TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.objects.map((o) => (
                    <TableRow key={o.id} data-testid="object-row" className="cursor-pointer hover:bg-[hsl(var(--secondary))]" onClick={() => nav(`/app/objects/${o.id}`)}>
                      <TableCell><span className="font-medium text-slate-900 hover:text-[hsl(var(--primary))]">{o.name}</span></TableCell>
                      <TableCell className="text-slate-500">{(OBJECT_TYPES.find((t) => t.value === o.object_type) || {}).label || o.object_type}</TableCell>
                      <TableCell className="text-slate-500">{o.address || "—"}</TableCell>
                      <TableCell className="text-slate-500">{o.responsible_name || "—"}</TableCell>
                      <TableCell><ChevronRight className="h-4 w-4 text-slate-400" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* REQUESTS */}
        <TabsContent value="requests" className="mt-4">
          {(data.requests || []).length === 0 ? (
            <EmptyState icon={ClipboardList} title="Заявок немає" hint="Створіть заявку на утилізацію відходів." action={<Button onClick={() => setReqDialog(true)} className="gap-2"><Plus className="h-4 w-4" /> Нова заявка</Button>} />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
              <Table>
                <TableHeader><TableRow><TableHead>Коди відходів</TableHead><TableHead>Етап</TableHead><TableHead>Джерело</TableHead><TableHead>Створено</TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.requests.map((r) => (
                    <TableRow key={r.id} data-testid="company-request-row">
                      <TableCell className="font-mono text-sm text-slate-700">{itemsSummary(r.items)}</TableCell>
                      <TableCell><StatusBadge status={r.stage} /></TableCell>
                      <TableCell className="text-slate-500">{r.source || "—"}</TableCell>
                      <TableCell className="text-slate-500">{fmtDate(r.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* CONTRACTS */}
        <TabsContent value="contracts" className="mt-4">
          {(data.contracts || []).length === 0 ? (
            <EmptyState icon={FileText} title="Договорів немає" hint="Договори генеруються із заявок у воронці." />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
              <Table>
                <TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Статус</TableHead><TableHead>Сума</TableHead><TableHead>Підписано</TableHead><TableHead>Створено</TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.contracts.map((x) => (
                    <TableRow key={x.id} data-testid="company-contract-row" onClick={() => setDrawer({ open: true, kind: "contract", id: x.id })} className="cursor-pointer hover:bg-[hsl(var(--secondary))]">
                      <TableCell className="font-mono text-sm font-medium text-slate-900">{x.number}</TableCell>
                      <TableCell><StatusBadge status={x.status} /></TableCell>
                      <TableCell className="text-slate-500">{x.amount ? `${x.amount} ${x.currency || "UAH"}` : "—"}</TableCell>
                      <TableCell className="text-slate-500 text-xs">{x.signed_at ? fmtDate(x.signed_at) : "—"}</TableCell>
                      <TableCell className="text-slate-500">{fmtDate(x.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* PICKUPS */}
        <TabsContent value="pickups" className="mt-4">
          {(data.pickups || []).length === 0 ? (
            <EmptyState icon={Truck} title="Вивозів немає" hint="Замовлення на вивіз генеруються із заявок." />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
              <Table>
                <TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Статус</TableHead><TableHead>Заплановано</TableHead><TableHead>Водій</TableHead><TableHead className="text-right">Вага</TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.pickups.map((x) => (
                    <TableRow key={x.id} data-testid="company-pickup-row" onClick={() => setDrawer({ open: true, kind: "pickup", id: x.id })} className="cursor-pointer hover:bg-[hsl(var(--secondary))]">
                      <TableCell className="font-mono text-sm font-medium text-slate-900">{x.number}</TableCell>
                      <TableCell><StatusBadge status={x.status} /></TableCell>
                      <TableCell className="text-slate-500">{fmtDateTime(x.scheduled_at)}</TableCell>
                      <TableCell className="text-slate-500 text-xs">{x.driver?.name || "—"}</TableCell>
                      <TableCell className="text-right text-slate-500 font-mono text-xs">{x.weight_kg ? `${x.weight_kg} кг` : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* ACTS */}
        <TabsContent value="acts" className="mt-4">
          {(data.acts || []).length === 0 ? (
            <EmptyState icon={BadgeCheck} title="Актів немає" hint="Акти утилізації формуються після вивозу." />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
              <Table>
                <TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Статус</TableHead><TableHead>Дата</TableHead><TableHead>Метод</TableHead><TableHead className="text-right">Вага</TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.acts.map((x) => (
                    <TableRow key={x.id} data-testid="company-act-row" onClick={() => setDrawer({ open: true, kind: "act", id: x.id })} className="cursor-pointer hover:bg-[hsl(var(--secondary))]">
                      <TableCell className="font-mono text-sm font-medium text-slate-900">{x.number}</TableCell>
                      <TableCell><StatusBadge status={x.status} /></TableCell>
                      <TableCell className="text-slate-500">{fmtDate(x.act_date || x.signed_at || x.created_at)}</TableCell>
                      <TableCell className="text-slate-500 text-xs">{x.utilization_method || "—"}</TableCell>
                      <TableCell className="text-right text-slate-500 font-mono">{x.total_weight_kg ? `${x.total_weight_kg} кг` : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* TASKS */}
        <TabsContent value="tasks" className="mt-4">
          <CompanyTasks companyId={id} tasks={tasks} loading={tasksLoading} onChanged={loadTasks} onOpenCreate={() => setTaskDialog(true)} />
        </TabsContent>

        {/* COMMENTS */}
        <TabsContent value="comments" className="mt-4">
          <CompanyComments companyId={id} comments={comments} loading={commentsLoading} onAdded={loadComments} />
        </TabsContent>

        {/* UTILIZATION */}
        <TabsContent value="utilization" className="mt-4">
          <UtilizationTab data={data} onOpenDrawer={(kind, id) => setDrawer({ open: true, kind, id })} />
        </TabsContent>

        {/* TIMELINE */}
        <TabsContent value="timeline" className="mt-4">
          {(data.timeline || []).length === 0 ? (
            <EmptyState icon={History} title="Подій немає" hint="Тут з'являтимуться всі операційні події компанії." />
          ) : (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-2">
              <ol className="relative ml-3 border-l border-[hsl(var(--border))]">
                {data.timeline.map((t, i) => (
                  <li key={i} className="ml-4 py-3" data-testid="timeline-item">
                    <span className="absolute -left-[6px] mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-[hsl(var(--primary))]" />
                    <div className="text-sm text-slate-800">{t.message}</div>
                    <div className="mt-0.5 text-xs text-slate-400">{fmtDateTime(t.at)} · {t.by || "система"}</div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </TabsContent>
      </Tabs>

      <AddObjectDialog open={objDialog} onOpenChange={setObjDialog} companyId={id} onCreated={load} />
      <CreateRequestDialog open={reqDialog} onOpenChange={setReqDialog} company={{ id, name: c.name }} onCreated={load} />
      <TaskDialog open={taskDialog} onOpenChange={setTaskDialog} companyId={id} objects={data.objects || []} onCreated={loadTasks} />
      <OperationDetailDrawer open={drawer.open} onOpenChange={(v) => setDrawer((p) => ({ ...p, open: v }))} kind={drawer.kind} id={drawer.id} onSaved={load} />
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CompanyOverview({ data, tasks, comments, timeline, onOpenDrawer }) {
  const c = data.company || {};
  const recentRequests = (data.requests || []).slice(0, 5);
  const openTasks = (tasks || []).filter((t) => t.status !== "done").slice(0, 5);
  const lastComment = (comments || [])[0];
  const lastActivity = (timeline || []).slice(0, 6);
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5 lg:col-span-2">
        <div className="mb-3 text-sm font-semibold text-slate-900">Контакти</div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <dt className="text-slate-500">ЄДРПОУ</dt><dd className="font-mono text-slate-800">{c.edrpou || "—"}</dd>
          <dt className="text-slate-500">Телефон</dt><dd className="text-slate-800">{c.phone || "—"}</dd>
          <dt className="text-slate-500">Email</dt><dd className="text-slate-800">{c.email || "—"}</dd>
          <dt className="text-slate-500">Адреса</dt><dd className="text-slate-800">{c.address || "—"}</dd>
          <dt className="text-slate-500">Сегмент</dt><dd className="text-slate-800">{c.segment || "—"}</dd>
          <dt className="text-slate-500">Створено</dt><dd className="text-slate-800">{fmtDate(c.created_at)}</dd>
        </dl>
        <CompanyContacts companyId={c.id} />
        <div className="my-4 h-px bg-[hsl(var(--border))]" />
        <div className="mb-2 text-sm font-semibold text-slate-900">Останні заявки</div>
        {recentRequests.length === 0
          ? <div className="text-sm text-slate-500">Заявок ще немає.</div>
          : <div className="space-y-1.5">{recentRequests.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/40 px-3 py-2 text-sm">
                <div className="flex items-center gap-2 min-w-0"><span className="font-mono text-xs text-slate-600 truncate">{itemsSummary(r.items)}</span></div>
                <div className="flex items-center gap-2"><StatusBadge status={r.stage} /><span className="text-xs text-slate-400">{fmtDate(r.created_at)}</span></div>
              </div>
            ))}</div>}
      </div>
      <div className="space-y-4">
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900"><ListTodo className="h-4 w-4 text-[hsl(var(--primary))]" /> Відкриті завдання</div>
          {openTasks.length === 0
            ? <div className="text-sm text-slate-500">Усе під контролем.</div>
            : <ul className="space-y-1.5 text-sm">{openTasks.map((t) => (
                <li key={t.id} className="flex items-start justify-between gap-2"><span className="text-slate-700">{t.title}</span><span className="shrink-0 text-xs text-slate-400">{t.due_at ? fmtDate(t.due_at) : "—"}</span></li>
              ))}</ul>}
        </div>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900"><MessageSquare className="h-4 w-4 text-[hsl(var(--primary))]" /> Останній коментар</div>
          {lastComment ? (
            <div className="space-y-1"><div className="text-sm text-slate-700">{lastComment.text}</div><div className="text-xs text-slate-400">{lastComment.author} · {fmtDateTime(lastComment.created_at)}</div></div>
          ) : <div className="text-sm text-slate-500">Коментарів немає.</div>}
        </div>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900"><Activity className="h-4 w-4 text-[hsl(var(--primary))]" /> Активність</div>
          {lastActivity.length === 0
            ? <div className="text-sm text-slate-500">Подій ще немає.</div>
            : <ol className="space-y-1.5 text-sm">{lastActivity.map((t, i) => (
                <li key={i} className="flex items-start gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[hsl(var(--primary))]" /><div><div className="text-slate-700">{t.message}</div><div className="text-xs text-slate-400">{fmtDateTime(t.at)}</div></div></li>
              ))}</ol>}
        </div>
      </div>
    </div>
  );
}

const TASK_STATUS_OPTS = [
  { value: "open", label: "Відкрита" },
  { value: "in_progress", label: "У роботі" },
  { value: "done", label: "Виконана" },
  { value: "cancelled", label: "Скасована" },
];

function TaskDialog({ open, onOpenChange, companyId, objects, onCreated }) {
  const [f, setF] = useState({ title: "", due_at: "", assigned_to: "", object_id: "", notes: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF({ title: "", due_at: "", assigned_to: "", object_id: "", notes: "" }); }, [open]);
  const submit = async () => {
    if (!f.title.trim()) return toast.error("Вкажіть заголовок задачі");
    setBusy(true);
    try {
      await PortalAPI.createTask(companyId, {
        title: f.title.trim(),
        due_at: f.due_at ? new Date(f.due_at).toISOString() : null,
        assigned_to: f.assigned_to.trim() || null,
        object_id: f.object_id || null,
        notes: f.notes.trim() || null,
      });
      toast.success("Задачу створено");
      onOpenChange(false); onCreated && onCreated();
    } catch { toast.error("Не вдалося створити задачу"); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="task-dialog">
        <DialogHeader><DialogTitle>Нова задача</DialogTitle><DialogDescription>Привʼязана до компанії; можна вказати конкретний обʼєкт.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Заголовок *</Label><Input value={f.title} onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} data-testid="task-title-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Дедлайн</Label><Input type="datetime-local" value={f.due_at} onChange={(e) => setF((p) => ({ ...p, due_at: e.target.value }))} /></div>
            <div className="grid gap-1.5"><Label>Виконавець</Label><Input value={f.assigned_to} onChange={(e) => setF((p) => ({ ...p, assigned_to: e.target.value }))} placeholder="email або імʼя" /></div>
          </div>
          {objects.length > 0 && (
            <div className="grid gap-1.5"><Label>Обʼєкт</Label>
              <Select value={f.object_id || "_none"} onValueChange={(v) => setF((p) => ({ ...p, object_id: v === "_none" ? "" : v }))}>
                <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent><SelectItem value="_none">— без привʼязки —</SelectItem>{objects.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-1.5"><Label>Деталі</Label><Textarea rows={2} value={f.notes} onChange={(e) => setF((p) => ({ ...p, notes: e.target.value }))} /></div>
        </div>
        <DialogFooter><Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button><Button onClick={submit} disabled={busy} data-testid="task-submit">{busy ? "Збереження…" : "Створити"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CompanyTasks({ companyId, tasks, loading, onChanged, onOpenCreate }) {
  const setStatus = async (t, status) => {
    try { await PortalAPI.updateTask(t.id, { status }); toast.success("Статус оновлено"); onChanged(); }
    catch { toast.error("Не вдалося"); }
  };
  const remove = async (t) => {
    if (!window.confirm(`Видалити задачу "${t.title}"?`)) return;
    try { await PortalAPI.deleteTask(t.id); toast.success("Видалено"); onChanged(); }
    catch { toast.error("Не вдалося"); }
  };
  if (loading) return <TableSkeleton rows={4} />;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm text-slate-500">Усього задач: <span className="font-medium text-slate-900">{tasks.length}</span></div>
        <Button onClick={onOpenCreate} className="gap-2" data-testid="task-create-button"><Plus className="h-4 w-4" /> Нова задача</Button>
      </div>
      {tasks.length === 0
        ? <EmptyState icon={CheckSquare} title="Задач немає" hint="Створіть першу задачу для менеджера." action={<Button onClick={onOpenCreate} className="gap-2"><Plus className="h-4 w-4" /> Створити</Button>} />
        : <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
            <Table>
              <TableHeader><TableRow><TableHead>Задача</TableHead><TableHead>Виконавець</TableHead><TableHead>Дедлайн</TableHead><TableHead>Статус</TableHead><TableHead className="w-12"></TableHead></TableRow></TableHeader>
              <TableBody>{tasks.map((t) => (
                <TableRow key={t.id} data-testid="task-row">
                  <TableCell><div className="font-medium text-slate-900">{t.title}</div>{t.notes && <div className="mt-0.5 text-xs text-slate-500 max-w-md truncate">{t.notes}</div>}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{t.assigned_to || "—"}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{t.due_at ? fmtDateTime(t.due_at) : "—"}</TableCell>
                  <TableCell>
                    <Select value={t.status || "open"} onValueChange={(v) => setStatus(t, v)}>
                      <SelectTrigger className="h-8 w-[140px]" data-testid="task-status-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{TASK_STATUS_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell><Button variant="ghost" size="icon" onClick={() => remove(t)} data-testid="task-delete-button"><Trash2 className="h-4 w-4 text-[#991B1B]" /></Button></TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          </div>}
    </div>
  );
}

function CompanyComments({ companyId, comments, loading, onAdded }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try { await PortalAPI.createComment(companyId, { text: text.trim() }); setText(""); onAdded(); }
    catch { toast.error("Не вдалося додати коментар"); } finally { setBusy(false); }
  };
  return (
    <div>
      <div className="mb-4 rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
        <Label className="mb-1.5 block text-xs uppercase tracking-wide text-slate-500">Новий коментар</Label>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Опишіть зустріч, дзвінок, домовленості…" rows={3} data-testid="comment-input" />
        <div className="mt-2 flex justify-end"><Button onClick={submit} disabled={busy || !text.trim()} className="gap-2" data-testid="comment-submit"><Send className="h-4 w-4" /> {busy ? "Збереження…" : "Опублікувати"}</Button></div>
      </div>
      {loading ? <TableSkeleton rows={3} /> : comments.length === 0 ? (
        <EmptyState icon={MessageSquare} title="Коментарів немає" hint="Зафіксуйте першу комунікацію з клієнтом." />
      ) : (
        <div className="space-y-3">{comments.map((cm) => (
          <div key={cm.id} className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4" data-testid="comment-row">
            <div className="mb-1 flex items-center justify-between text-xs text-slate-500"><span className="inline-flex items-center gap-1"><User className="h-3.5 w-3.5" />{cm.author}</span><span>{fmtDateTime(cm.created_at)}</span></div>
            <div className="whitespace-pre-wrap text-sm text-slate-800">{cm.text}</div>
          </div>
        ))}</div>
      )}
    </div>
  );
}

function UtilizationTab({ data, onOpenDrawer }) {
  const acts = useMemo(() => data.acts || [], [data.acts]);
  const pickups = data.pickups || [];
  // Aggregate: total weight + by waste code
  const stats = useMemo(() => {
    let totalWeight = 0, signedActs = 0;
    const byCode = {};
    acts.forEach((a) => {
      if (a.total_weight_kg) totalWeight += Number(a.total_weight_kg) || 0;
      if (a.status === "signed" || a.status === "archived") signedActs += 1;
      (a.items || []).forEach((it) => {
        if (!it.waste_code) return;
        byCode[it.waste_code] = byCode[it.waste_code] || { code: it.waste_code, name: it.name, qty: 0 };
        byCode[it.waste_code].qty += Number(it.qty || 0);
      });
    });
    return { totalWeight, signedActs, byCode: Object.values(byCode).sort((a, b) => b.qty - a.qty) };
  }, [acts]);
  const maxQty = stats.byCode[0]?.qty || 1;

  if (acts.length === 0 && pickups.length === 0) {
    return <EmptyState icon={Recycle} title="Утилізації ще не проводилися" hint="Тут зʼявиться обсяг утилізованих відходів за фактом актів." />;
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Усього актів</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{acts.length}</div>
        </div>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Підписаних</div>
          <div className="mt-1 text-2xl font-semibold text-[#065F46]">{stats.signedActs}</div>
        </div>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Вивозів</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{pickups.length}</div>
        </div>
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Утилізовано, кг</div>
          <div className="mt-1 text-2xl font-semibold text-[hsl(var(--primary))]">{stats.totalWeight.toFixed(1)}</div>
        </div>
      </div>

      {stats.byCode.length > 0 && (
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
          <div className="mb-3 text-sm font-semibold text-slate-900">Розподіл за кодами</div>
          <div className="space-y-2">{stats.byCode.map((b) => (
            <div key={b.code} className="flex items-center gap-3">
              <Link to={`/waste-code/${encodeURIComponent(b.code)}`} className="w-28 shrink-0 font-mono text-sm text-[hsl(var(--primary))] hover:underline">{b.code}</Link>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs text-slate-500">{b.name || "—"}</div>
                <div className="mt-0.5 h-2 rounded-full bg-[hsl(var(--secondary))]"><div className="h-2 rounded-full bg-[hsl(var(--primary))]" style={{ width: `${Math.max(6, (b.qty / maxQty) * 100)}%` }} /></div>
              </div>
              <div className="w-20 shrink-0 text-right font-mono text-sm text-slate-800">{b.qty.toFixed(1)} кг</div>
            </div>
          ))}</div>
        </div>
      )}

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        <div className="border-b border-[hsl(var(--border))] px-4 py-3 text-sm font-semibold text-slate-900">Останні акти</div>
        <Table>
          <TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Дата</TableHead><TableHead>Метод</TableHead><TableHead className="text-right">Вага</TableHead><TableHead>Статус</TableHead></TableRow></TableHeader>
          <TableBody>{acts.slice(0, 10).map((a) => (
            <TableRow key={a.id} className="cursor-pointer hover:bg-[hsl(var(--secondary))]" onClick={() => onOpenDrawer("act", a.id)}>
              <TableCell className="font-mono text-sm text-slate-900">{a.number}</TableCell>
              <TableCell className="text-slate-500">{fmtDate(a.act_date || a.signed_at || a.created_at)}</TableCell>
              <TableCell className="text-slate-500 text-xs">{a.utilization_method || "—"}</TableCell>
              <TableCell className="text-right text-slate-700 font-mono">{a.total_weight_kg ? `${a.total_weight_kg} кг` : "—"}</TableCell>
              <TableCell><StatusBadge status={a.status} /></TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
      </div>
    </div>
  );
}
