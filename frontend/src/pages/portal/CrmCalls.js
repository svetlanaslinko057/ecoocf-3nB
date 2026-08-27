// ECO CRM — Calls Console (Ringostat)
// Unified call-management surface for admin + manager: KPIs, filters,
// awaiting-outcome queue, scheduled call-backs, per-manager attribution,
// and the outcome workflow (result + callback date + comment).
import React, { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Phone, PhoneIncoming, PhoneMissed, PhoneOff, BarChart3, Filter, RefreshCw,
  Sparkles, Send, Clock, AlertTriangle, CalendarClock, CheckCircle2, ExternalLink,
} from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import {
  durFmt, dtFmt, callStatusMeta, outcomeLabel, outcomeStyle, DirectionIcon, needsOutcome,
} from "@/lib/callsMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import OutcomeDialog from "@/components/calls/OutcomeDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";

function StatusPill({ s }) {
  const m = callStatusMeta(s);
  return <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium" style={{ color: m.c, background: m.bg, borderColor: m.b }}>{m.l}</span>;
}
function OutcomePill({ value }) {
  if (!value) return <span className="text-xs text-amber-600">— потрібен —</span>;
  const st = outcomeStyle(value);
  return <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium" style={{ color: st.c, background: st.bg, borderColor: st.b }}>{outcomeLabel(value)}</span>;
}

function SimulateDialog({ open, onOpenChange, onCreated }) {
  const [f, setF] = useState({ event: "CALL_END", from: "", manager_extension: "101", duration: 75 });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setF({ event: "CALL_END", from: "+38067" + Math.floor(Math.random() * 9000000 + 1000000), manager_extension: "101", duration: 75 });
  }, [open]);
  const submit = async () => {
    setBusy(true);
    try {
      await CrmAPI.simulateCall({
        event: f.event,
        from: f.from,
        manager_extension: f.manager_extension,
        duration: f.event === "CALL_END" ? Number(f.duration) || 60 : 0,
      });
      toast.success("Тестовий дзвінок зафіксовано");
      onOpenChange(false); onCreated && onCreated();
    } catch { toast.error("Не вдалося зареєструвати дзвінок"); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="call-sim-dialog">
        <DialogHeader><DialogTitle>Симуляція Ringostat-дзвінка</DialogTitle><DialogDescription>Для демо та відлагодження воронки дзвінків.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Номер абонента</Label><Input value={f.from} onChange={(e) => setF((p) => ({ ...p, from: e.target.value }))} data-testid="call-sim-number" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Тип події</Label>
              <Select value={f.event} onValueChange={(v) => setF((p) => ({ ...p, event: v }))}>
                <SelectTrigger data-testid="call-sim-event"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="CALL_END">Відповів (потребує результату)</SelectItem>
                  <SelectItem value="CALL_MISSED">Пропущений</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Розширення</Label><Input value={f.manager_extension} onChange={(e) => setF((p) => ({ ...p, manager_extension: e.target.value }))} /></div>
          </div>
          {f.event === "CALL_END" && (
            <div className="grid gap-1.5"><Label>Тривалість (с)</Label><Input type="number" value={f.duration} onChange={(e) => setF((p) => ({ ...p, duration: e.target.value }))} /></div>
          )}
        </div>
        <DialogFooter><Button variant="secondary" onClick={() => onOpenChange(false)}>Скасувати</Button><Button onClick={submit} disabled={busy} data-testid="call-sim-submit" className="gap-2"><Send className="h-4 w-4" /> {busy ? "Надсилання…" : "Надіслати"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const TABS = [
  ["all", "Усі", Phone],
  ["awaiting", "Очікують результату", AlertTriangle],
  ["missed", "Пропущені", PhoneMissed],
  ["callbacks", "Передзвони", CalendarClock],
];

export default function CrmCalls() {
  useSeo("Дзвінки · CRM", "Консоль керування дзвінками — Ringostat.");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "all";

  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [simOpen, setSimOpen] = useState(false);
  const [outcomeCall, setOutcomeCall] = useState(null);
  const [staff, setStaff] = useState([]);
  const [filters, setFilters] = useState({ period: "week", direction: "", status: "", manager_id: "", q: "" });

  const setTab = (t) => { const p = new URLSearchParams(params); p.set("tab", t); setParams(p); };

  const loadSummary = useCallback(async () => {
    try {
      const p = filters.manager_id ? { manager_id: filters.manager_id } : {};
      setSummary(await CrmAPI.callsSummary(p));
    } catch { /* silent */ }
  }, [filters.manager_id]);

  const loadRows = useCallback(async () => {
    setLoading(true);
    try {
      const scope = filters.manager_id ? { manager_id: filters.manager_id } : {};
      let res;
      if (tab === "awaiting") res = await CrmAPI.callsAwaiting(scope);
      else if (tab === "callbacks") res = await CrmAPI.callsCallbacks(scope);
      else if (tab === "missed") res = await CrmAPI.callsFeed({ ...scope, period: filters.period, status: "MISSED", q: filters.q || undefined });
      else res = await CrmAPI.callsFeed({
        ...scope, period: filters.period,
        direction: filters.direction || undefined,
        status: filters.status || undefined,
        q: filters.q || undefined,
      });
      setRows(res.calls || []);
    } catch { setRows([]); } finally { setLoading(false); }
  }, [tab, filters]);

  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { loadRows(); }, [loadRows]);
  useEffect(() => {
    if (!isAdmin) return;
    CrmAPI.ringostatMappings().then((r) => setStaff(r.staff || [])).catch(() => {});
  }, [isAdmin]);

  const refresh = () => { loadSummary(); loadRows(); };
  const s = summary || {};

  return (
    <div data-testid="portal-crm-calls">
      <PageHeader
        title="Консоль дзвінків"
        subtitle="Ringostat · вхідні / вихідні / результати / передзвони"
        actions={isAdmin && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => window.open("/app/ringostat", "_self")} className="gap-2" data-testid="calls-open-admin"><ExternalLink className="h-4 w-4" /> Налаштування</Button>
            <Button onClick={() => setSimOpen(true)} className="gap-2" data-testid="call-sim-button" variant="secondary"><Sparkles className="h-4 w-4" /> Симулювати</Button>
          </div>
        )}
      />

      {/* KPIs */}
      <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard icon={Phone} label="Сьогодні" value={s.today_total ?? 0} hint={`вх ${s.today_inbound ?? 0} · вих ${s.today_outbound ?? 0}`} testid="crmcalls-kpi-total" />
        <StatCard icon={PhoneIncoming} label="Відповіли" value={s.today_answered ?? 0} testid="crmcalls-kpi-answered" />
        <StatCard icon={PhoneMissed} label="Пропущені" value={s.today_missed ?? 0} testid="crmcalls-kpi-missed" />
        <StatCard icon={AlertTriangle} label="Очікують результату" value={s.awaiting_outcome ?? 0} testid="crmcalls-kpi-awaiting" />
        <StatCard icon={CalendarClock} label="Передзвони" value={s.scheduled_callbacks ?? 0} hint={s.overdue_callbacks ? `${s.overdue_callbacks} прострочено` : undefined} testid="crmcalls-kpi-callbacks" />
      </div>

      {/* Awaiting alert */}
      {(s.awaiting_outcome ?? 0) > 0 && tab !== "awaiting" && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3" data-testid="crmcalls-awaiting-alert">
          <div className="flex items-center gap-2 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4" /> {s.awaiting_outcome} дзвінок(ів) очікують фіксації результату — ліди не закриються без цього.
          </div>
          <Button size="sm" variant="outline" className="border-amber-400 text-amber-800" onClick={() => setTab("awaiting")} data-testid="crmcalls-goto-awaiting">Заповнити</Button>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex flex-wrap">
            {TABS.map(([v, label, Icon]) => (
              <TabsTrigger key={v} value={v} data-testid={`crmcalls-tab-${v}`} className="gap-1.5"><Icon className="h-4 w-4" /> {label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {/* Filters */}
      <Card className="mb-4 p-3">
        <div className="flex flex-wrap items-end gap-3">
          {tab !== "awaiting" && tab !== "callbacks" && (
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1"><Filter className="h-3 w-3" /> Період</Label>
              <Select value={filters.period} onValueChange={(v) => setFilters((p) => ({ ...p, period: v }))}>
                <SelectTrigger className="w-36" data-testid="calls-filter-period"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">Сьогодні</SelectItem>
                  <SelectItem value="week">Тиждень</SelectItem>
                  <SelectItem value="month">Місяць</SelectItem>
                  <SelectItem value="all">Весь час</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          {tab === "all" && (
            <div className="space-y-1">
              <Label className="text-xs">Напрям</Label>
              <Select value={filters.direction || "all"} onValueChange={(v) => setFilters((p) => ({ ...p, direction: v === "all" ? "" : v }))}>
                <SelectTrigger className="w-32" data-testid="calls-filter-direction"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Усі</SelectItem>
                  <SelectItem value="inbound">Вхідні</SelectItem>
                  <SelectItem value="outbound">Вихідні</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          {isAdmin && (
            <div className="space-y-1">
              <Label className="text-xs">Менеджер</Label>
              <Select value={filters.manager_id || "all"} onValueChange={(v) => setFilters((p) => ({ ...p, manager_id: v === "all" ? "" : v }))}>
                <SelectTrigger className="w-48" data-testid="calls-filter-manager"><SelectValue placeholder="Усі менеджери" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Усі менеджери</SelectItem>
                  {staff.map((st) => (<SelectItem key={st.id} value={st.id}>{st.name || st.email} ({st.role})</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
          )}
          {tab !== "awaiting" && tab !== "callbacks" && (
            <div className="space-y-1">
              <Label className="text-xs">Пошук номера</Label>
              <Input className="w-44" placeholder="+380…" value={filters.q} onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && loadRows()} data-testid="calls-filter-q" />
            </div>
          )}
          <Button variant="outline" onClick={refresh} className="ml-auto gap-1.5" data-testid="calls-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>
        </div>
      </Card>

      {/* Table */}
      <Card className="overflow-hidden p-0">
        {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
          : rows.length === 0 ? (
            <EmptyState
              icon={tab === "missed" ? PhoneMissed : tab === "callbacks" ? CalendarClock : tab === "awaiting" ? CheckCircle2 : PhoneOff}
              title={tab === "awaiting" ? "Усі результати заповнені 🎉" : tab === "callbacks" ? "Запланованих передзвонів немає" : tab === "missed" ? "Пропущених немає" : "Дзвінків немає"}
              hint={isAdmin ? "Підключіть Ringostat webhook або скористайтесь симулятором для демо." : "Нові дзвінки з'являться тут автоматично."}
              action={isAdmin && tab === "all" && <Button onClick={() => setSimOpen(true)} variant="secondary" className="gap-2"><Sparkles className="h-4 w-4" /> Симулювати</Button>}
              testid="crmcalls-empty"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Час</TableHead>
                  <TableHead>Напрям</TableHead>
                  <TableHead>Номер</TableHead>
                  <TableHead>Лід</TableHead>
                  <TableHead>Менеджер</TableHead>
                  <TableHead>Трив.</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Результат</TableHead>
                  {tab === "callbacks" && <TableHead>Передзвін</TableHead>}
                  <TableHead className="text-right">Дія</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((c) => {
                  const na = needsOutcome(c);
                  return (
                    <TableRow key={c.call_id || c._id} data-testid="crmcalls-row" className={na ? "bg-amber-50/40" : ""}>
                      <TableCell className="whitespace-nowrap text-xs text-slate-500">{dtFmt(c.started_at || c.created_at)}</TableCell>
                      <TableCell><div className="flex items-center gap-1"><DirectionIcon d={c.direction} /></div></TableCell>
                      <TableCell className="font-mono text-sm text-slate-900">{c.from || c.caller_number || "—"}</TableCell>
                      <TableCell className="text-sm text-slate-600">{c.lead?.name || c.lead?.phone || c.lead_name || "—"}</TableCell>
                      <TableCell className="text-sm text-slate-600">{c.manager_name || (c.manager_id ? "—" : <span className="text-amber-600">не призначено</span>)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{durFmt(c.duration)}</TableCell>
                      <TableCell><StatusPill s={c.status} /></TableCell>
                      <TableCell><OutcomePill value={c.outcome} /></TableCell>
                      {tab === "callbacks" && (
                        <TableCell className="text-xs">
                          <span className={c.overdue ? "font-medium text-rose-600" : "text-slate-600"}>{dtFmt(c.callback_at)}</span>
                        </TableCell>
                      )}
                      <TableCell className="text-right">
                        <Button size="sm" variant={na ? "default" : "outline"} onClick={() => setOutcomeCall(c)} data-testid="crmcalls-outcome-btn" className="gap-1.5">
                          <Clock className="h-3.5 w-3.5" /> {c.outcome ? "Змінити" : "Результат"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
      </Card>

      <SimulateDialog open={simOpen} onOpenChange={setSimOpen} onCreated={refresh} />
      <OutcomeDialog open={!!outcomeCall} onOpenChange={(v) => !v && setOutcomeCall(null)} call={outcomeCall} onSaved={() => { setOutcomeCall(null); refresh(); }} />
    </div>
  );
}
