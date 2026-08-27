import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  Boxes, ArrowLeft, MapPin, User, Phone, Building2, ClipboardList, Truck,
  BadgeCheck, Calendar, Recycle, Pencil, Save, Plus, Hash,
} from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDate, fmtDateTime, itemsSummary } from "@/lib/portalMeta";
import { PageHeader, StatCard, StatusBadge, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";
import { OperationDetailDrawer } from "@/components/portal/OperationDetailDrawer";
import { CreateRequestDialog } from "@/components/portal/CreateRequestDialog";

const OBJECT_TYPES = {
  hospital: "Лікарня / клініка",
  factory: "Завод / виробництво",
  lab: "Лабораторія",
  warehouse: "Склад",
  gas_station: "АЗС",
  agrofirm: "Агрофірма",
  site: "Об'єкт",
};

const FREQ_OPTS = [
  { value: "weekly", label: "Щотижнево" },
  { value: "biweekly", label: "Раз на 2 тижні" },
  { value: "monthly", label: "Щомісячно" },
  { value: "quarterly", label: "Поквартально" },
  { value: "on_demand", label: "На вимогу" },
];

function EditObjectDialog({ open, onOpenChange, obj, onSaved }) {
  const [f, setF] = useState({});
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!open || !obj) return;
    setF({
      name: obj.name || "", object_type: obj.object_type || "site", address: obj.address || "",
      responsible_name: obj.responsible_name || "", responsible_phone: obj.responsible_phone || "",
      pickup_schedule: obj.pickup_schedule || { frequency: "on_demand", weekday: "", time: "", notes: "" },
    });
  }, [open, obj]);
  const save = async () => {
    setSaving(true);
    try {
      await PortalAPI.updateObject(obj.id, f);
      toast.success("Об'єкт оновлено");
      onSaved && onSaved(); onOpenChange(false);
    } catch { toast.error("Не вдалося зберегти"); }
    finally { setSaving(false); }
  };
  if (!f.pickup_schedule) return null;
  const sched = f.pickup_schedule || {};
  const setSched = (p) => setF((s) => ({ ...s, pickup_schedule: { ...sched, ...p } }));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="object-edit-dialog">
        <DialogHeader><DialogTitle>Редагувати об'єкт</DialogTitle><DialogDescription>Контактна особа, адреса та графік вивозу.</DialogDescription></DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5 sm:col-span-2"><Label>Назва</Label><Input value={f.name || ""} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} data-testid="object-edit-name" /></div>
          <div className="grid gap-1.5"><Label>Тип об'єкта</Label>
            <Select value={f.object_type || "site"} onValueChange={(v) => setF((p) => ({ ...p, object_type: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(OBJECT_TYPES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Адреса</Label><Input value={f.address || ""} onChange={(e) => setF((p) => ({ ...p, address: e.target.value }))} /></div>
          <div className="grid gap-1.5"><Label>Відповідальний</Label><Input value={f.responsible_name || ""} onChange={(e) => setF((p) => ({ ...p, responsible_name: e.target.value }))} /></div>
          <div className="grid gap-1.5"><Label>Телефон</Label><Input value={f.responsible_phone || ""} onChange={(e) => setF((p) => ({ ...p, responsible_phone: e.target.value }))} placeholder="+380…" /></div>

          <div className="sm:col-span-2 rounded-xl border border-dashed border-[hsl(var(--border))] p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Графік вивозу</div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="grid gap-1.5"><Label className="text-xs">Частота</Label>
                <Select value={sched.frequency || "on_demand"} onValueChange={(v) => setSched({ frequency: v })}>
                  <SelectTrigger data-testid="object-sched-freq"><SelectValue /></SelectTrigger>
                  <SelectContent>{FREQ_OPTS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5"><Label className="text-xs">День тижня</Label>
                <Select value={sched.weekday || ""} onValueChange={(v) => setSched({ weekday: v })}>
                  <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>{["mon","tue","wed","thu","fri","sat","sun"].map((w, i) => <SelectItem key={w} value={w}>{["Пн","Вт","Ср","Чт","Пт","Сб","Нд"][i]}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5"><Label className="text-xs">Час</Label><Input type="time" value={sched.time || ""} onChange={(e) => setSched({ time: e.target.value })} /></div>
            </div>
            <div className="mt-3 grid gap-1.5"><Label className="text-xs">Примітки</Label><Textarea rows={2} value={sched.notes || ""} onChange={(e) => setSched({ notes: e.target.value })} /></div>
          </div>
        </div>
        <DialogFooter><Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button><Button onClick={save} disabled={saving} data-testid="object-edit-save">{saving ? "Збереження…" : "Зберегти"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ObjectDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [reqOpen, setReqOpen] = useState(false);
  const [drawer, setDrawer] = useState({ open: false, kind: "contract", id: null });

  const load = useCallback(async () => {
    setLoading(true); setErr(false);
    try { const r = await PortalAPI.objectDetail(id); setData(r); }
    catch { setErr(true); } finally { setLoading(false); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  useSeo(data?.object?.name ? `${data.object.name} · Об'єкт` : "Об'єкт", "Картка об'єкта: графік, заявки, вивози, акти.");

  const openDrawer = (kind, id) => setDrawer({ open: true, kind, id });

  if (loading) return <div><div className="mb-6 h-8 w-48 animate-pulse rounded bg-[hsl(var(--secondary))]" /><TableSkeleton rows={6} /></div>;
  if (err || !data?.object) return <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#991B1B]" data-testid="object-error">Об'єкт не знайдено. <Link to="/app/companies" className="font-medium underline">До компаній</Link></div>;

  const o = data.object;
  const company = data.company;
  const s = data.stats || {};
  const sched = o.pickup_schedule || null;

  return (
    <div data-testid="portal-object-detail">
      <div className="mb-4 flex items-center gap-3 text-sm text-slate-500">
        <button onClick={() => nav(-1)} className="inline-flex items-center gap-2 hover:text-[hsl(var(--primary))]"><ArrowLeft className="h-4 w-4" /> Назад</button>
        {company && <><span>/</span><Link to={`/app/companies/${company.id}`} className="hover:text-[hsl(var(--primary))]">{company.name}</Link></>}
        <span>/</span><span className="text-slate-900">{o.name}</span>
      </div>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-2 py-0.5 text-xs text-slate-600"><Boxes className="h-3.5 w-3.5" /> {OBJECT_TYPES[o.object_type] || o.object_type}</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900" data-testid="object-detail-name">{o.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
            {o.address && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{o.address}</span>}
            {o.responsible_name && <span className="inline-flex items-center gap-1"><User className="h-3.5 w-3.5" />{o.responsible_name}</span>}
            {o.responsible_phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{o.responsible_phone}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" className="gap-2" onClick={() => setEditOpen(true)} data-testid="object-edit-button"><Pencil className="h-4 w-4" /> Редагувати</Button>
          <Button className="gap-2" onClick={() => setReqOpen(true)} data-testid="object-create-request"><Plus className="h-4 w-4" /> Заявка</Button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard icon={ClipboardList} label="Заявки" value={s.requests ?? 0} testid="object-kpi-requests" />
        <StatCard icon={Truck} label="Вивози" value={s.pickups ?? 0} testid="object-kpi-pickups" />
        <StatCard icon={BadgeCheck} label="Акти" value={s.acts ?? 0} testid="object-kpi-acts" />
        <StatCard icon={Recycle} label="Типи відходів" value={s.waste_types ?? 0} testid="object-kpi-types" />
        <StatCard icon={Calendar} label="Наступний вивіз" value={fmtDate(s.next_pickup)} hint={sched ? FREQ_OPTS.find((f) => f.value === sched.frequency)?.label : "—"} testid="object-kpi-next" />
      </div>

      {sched && (
        <div className="mb-6 rounded-2xl border border-[hsl(var(--border))] bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Calendar className="h-4 w-4 text-[hsl(var(--primary))]" /> Графік вивозу</div>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
            <span><b className="text-slate-900">Частота:</b> {FREQ_OPTS.find((f) => f.value === sched.frequency)?.label || sched.frequency}</span>
            {sched.weekday && <span><b className="text-slate-900">День:</b> {sched.weekday}</span>}
            {sched.time && <span><b className="text-slate-900">Час:</b> {sched.time}</span>}
            {sched.notes && <span><b className="text-slate-900">Нотатки:</b> {sched.notes}</span>}
          </div>
        </div>
      )}

      <Tabs defaultValue="requests">
        <TabsList>
          <TabsTrigger value="requests" data-testid="obj-tab-requests">Заявки ({s.requests ?? 0})</TabsTrigger>
          <TabsTrigger value="pickups" data-testid="obj-tab-pickups">Вивози ({s.pickups ?? 0})</TabsTrigger>
          <TabsTrigger value="acts" data-testid="obj-tab-acts">Акти ({s.acts ?? 0})</TabsTrigger>
          <TabsTrigger value="waste" data-testid="obj-tab-waste">Відходи ({s.waste_types ?? 0})</TabsTrigger>
          <TabsTrigger value="branches" data-testid="obj-tab-branches">Філії ({s.branches ?? 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="requests" className="mt-4">
          {(data.requests || []).length === 0
            ? <EmptyState icon={ClipboardList} title="Заявок немає" hint="Створіть першу заявку для цього об'єкта." action={<Button onClick={() => setReqOpen(true)} className="gap-2"><Plus className="h-4 w-4" /> Нова заявка</Button>} />
            : <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
                <Table><TableHeader><TableRow><TableHead>Коди</TableHead><TableHead>Етап</TableHead><TableHead>Джерело</TableHead><TableHead>Створено</TableHead></TableRow></TableHeader>
                  <TableBody>{(data.requests || []).map((r) => (
                    <TableRow key={r.id} data-testid="object-request-row">
                      <TableCell className="font-mono text-sm text-slate-700">{itemsSummary(r.items)}</TableCell>
                      <TableCell><StatusBadge status={r.stage} /></TableCell>
                      <TableCell className="text-slate-500">{r.source || "—"}</TableCell>
                      <TableCell className="text-slate-500">{fmtDate(r.created_at)}</TableCell>
                    </TableRow>
                  ))}</TableBody></Table>
              </div>}
        </TabsContent>

        <TabsContent value="pickups" className="mt-4">
          {(data.pickups || []).length === 0
            ? <EmptyState icon={Truck} title="Вивозів немає" hint="Замовлення вивозу формуються із заявок." />
            : <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
                <Table><TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Статус</TableHead><TableHead>Заплановано</TableHead><TableHead>Водій</TableHead><TableHead className="text-right">Вага</TableHead></TableRow></TableHeader>
                  <TableBody>{(data.pickups || []).map((p) => (
                    <TableRow key={p.id} onClick={() => openDrawer("pickup", p.id)} className="cursor-pointer hover:bg-[hsl(var(--secondary))]" data-testid="object-pickup-row">
                      <TableCell className="font-mono text-sm font-medium text-slate-900">{p.number}</TableCell>
                      <TableCell><StatusBadge status={p.status} /></TableCell>
                      <TableCell className="text-slate-500">{fmtDateTime(p.scheduled_at)}</TableCell>
                      <TableCell className="text-slate-500">{p.driver?.name || "—"}</TableCell>
                      <TableCell className="text-right text-slate-500 font-mono">{p.weight_kg ? `${p.weight_kg} кг` : "—"}</TableCell>
                    </TableRow>
                  ))}</TableBody></Table>
              </div>}
        </TabsContent>

        <TabsContent value="acts" className="mt-4">
          {(data.acts || []).length === 0
            ? <EmptyState icon={BadgeCheck} title="Актів немає" hint="Акти формуються після вивозу відходів." />
            : <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
                <Table><TableHeader><TableRow><TableHead>Номер</TableHead><TableHead>Статус</TableHead><TableHead>Дата</TableHead><TableHead>Метод</TableHead><TableHead className="text-right">Вага</TableHead></TableRow></TableHeader>
                  <TableBody>{(data.acts || []).map((a) => (
                    <TableRow key={a.id} onClick={() => openDrawer("act", a.id)} className="cursor-pointer hover:bg-[hsl(var(--secondary))]" data-testid="object-act-row">
                      <TableCell className="font-mono text-sm font-medium text-slate-900">{a.number}</TableCell>
                      <TableCell><StatusBadge status={a.status} /></TableCell>
                      <TableCell className="text-slate-500">{fmtDate(a.act_date || a.signed_at || a.created_at)}</TableCell>
                      <TableCell className="text-slate-500">{a.utilization_method || "—"}</TableCell>
                      <TableCell className="text-right text-slate-500 font-mono">{a.total_weight_kg ? `${a.total_weight_kg} кг` : "—"}</TableCell>
                    </TableRow>
                  ))}</TableBody></Table>
              </div>}
        </TabsContent>

        <TabsContent value="waste" className="mt-4">
          {(data.waste_types || []).length === 0
            ? <EmptyState icon={Recycle} title="Типів відходів не вказано" hint="З'являться після першої заявки." />
            : <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {(data.waste_types || []).map((code) => (
                  <Link key={code} to={`/waste-code/${encodeURIComponent(code)}`} className="flex items-center justify-between gap-2 rounded-xl border border-[hsl(var(--border))] bg-white px-4 py-3 hover:border-[hsl(var(--primary))]">
                    <span className="font-mono text-sm text-slate-900">{code}</span>
                    <Hash className="h-4 w-4 text-slate-400" />
                  </Link>
                ))}
              </div>}
        </TabsContent>

        <TabsContent value="branches" className="mt-4">
          {(data.branches || []).length === 0
            ? <EmptyState icon={Building2} title="Підрозділів немає" hint="Підоб'єкти (філії) підключаються через parent_id." />
            : <div className="grid gap-2 sm:grid-cols-2">
                {(data.branches || []).map((b) => (
                  <Link key={b.id} to={`/app/objects/${b.id}`} className="flex items-center gap-3 rounded-xl border border-[hsl(var(--border))] bg-white p-3 hover:border-[hsl(var(--primary))]">
                    <Boxes className="h-5 w-5 text-[hsl(var(--primary))]" />
                    <div><div className="font-medium text-slate-900">{b.name}</div><div className="text-xs text-slate-500">{OBJECT_TYPES[b.object_type] || b.object_type}{b.address ? ` · ${b.address}` : ""}</div></div>
                  </Link>
                ))}
              </div>}
        </TabsContent>
      </Tabs>

      <EditObjectDialog open={editOpen} onOpenChange={setEditOpen} obj={o} onSaved={load} />
      <CreateRequestDialog open={reqOpen} onOpenChange={setReqOpen} company={company ? { id: company.id, name: company.name, objectId: o.id } : null} onCreated={load} />
      <OperationDetailDrawer open={drawer.open} onOpenChange={(v) => setDrawer((p) => ({ ...p, open: v }))} kind={drawer.kind} id={drawer.id} onSaved={load} />
    </div>
  );
}
