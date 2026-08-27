// ECO Action Center (Wave 17) — операційний рушій дій
// Інбокс / Мої / Команда(admin) / Аналітика + життєвий цикл дій
import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Zap, RefreshCw, Plus, AlertTriangle, Clock, CheckCircle2, Play,
  Pause, ArrowUpCircle, Loader2, Activity, Filter, TrendingUp, Users,
} from "lucide-react";
import { ActionsAPI } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSeo } from "@/lib/seo";
import { fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const PRIO = {
  critical: { label: "Критичний", cls: "bg-[#FEE2E2] text-[#991B1B]" },
  high: { label: "Високий", cls: "bg-[#FFEDD5] text-[#9A3412]" },
  medium: { label: "Середній", cls: "bg-[#E0F2FE] text-[#075985]" },
  low: { label: "Низький", cls: "bg-slate-100 text-slate-600" },
};
const SOURCE_LABEL = {
  operations: "Операції", contract: "Контракти", financial: "Фінанси",
  collection_workflow: "Стягнення", manual: "Вручну", sla: "SLA", deal: "Угоди",
};
const STATUS_LABEL = {
  open: "Відкрита", in_progress: "В роботі", snoozed: "Відкладена",
  resolved: "Виконана", cancelled: "Скасована",
};

function money(v) {
  const n = Number(v || 0);
  if (!n) return "—";
  return `${n.toLocaleString("uk-UA")} ₴`;
}

function PrioPill({ p }) {
  const m = PRIO[p] || PRIO.low;
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${m.cls}`}>{m.label}</span>;
}

function ActionRow({ a, onAct, busy }) {
  return (
    <li className={`flex items-start gap-3 px-4 py-3 ${a.is_overdue ? "bg-[#FFF7F7]" : ""}`} data-testid="action-row">
      <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#0E5E3A]/10">
        <Zap className="h-4 w-4 text-[#0E5E3A]" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-slate-900">{a.title}</span>
          <PrioPill p={a.priority} />
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            {SOURCE_LABEL[a.source] || a.source}
          </span>
          {a.is_overdue && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#DC2626]"><AlertTriangle className="h-3 w-3" /> прострочено</span>}
        </div>
        {a.description && <div className="mt-0.5 text-sm text-slate-600">{a.description}</div>}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
          <span>Виконавець: {a.owner_name || a.owner_id || "—"}</span>
          {a.due_at && <span>Дедлайн: {fmtDateTime(a.due_at)}</span>}
          {a.impact ? <span className="font-medium text-[#0E5E3A]">{money(a.impact)}</span> : null}
          <span>· {STATUS_LABEL[a.status] || a.status}</span>
        </div>
      </div>
      <div className="flex shrink-0 flex-col gap-1.5">
        {a.status !== "in_progress" && a.status !== "resolved" && (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAct(a, "start")} className="h-7 gap-1 px-2 text-xs" data-testid="action-start"><Play className="h-3 w-3" /> Почати</Button>
        )}
        {a.status !== "resolved" && (
          <Button size="sm" disabled={busy} onClick={() => onAct(a, "resolve")} className="h-7 gap-1 bg-[#0E5E3A] px-2 text-xs hover:bg-[#0c4f31]" data-testid="action-resolve"><CheckCircle2 className="h-3 w-3" /> Виконати</Button>
        )}
        {a.status !== "resolved" && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAct(a, "escalate")} className="h-7 gap-1 px-2 text-xs text-[#9A3412]" data-testid="action-escalate"><ArrowUpCircle className="h-3 w-3" /> Ескалація</Button>
        )}
      </div>
    </li>
  );
}

export default function ActionCenter() {
  useSeo("Центр дій · CRM", "Операційний рушій дій ECO: ризики, прострочення, SLA.");
  const { user } = useAuth();
  const isAdmin = ["admin", "owner", "master_admin"].includes((user?.role || "").toLowerCase());

  const [tab, setTab] = useState("inbox");
  const [inbox, setInbox] = useState(null);
  const [my, setMy] = useState(null);
  const [team, setTeam] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [prioFilter, setPrioFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ib, mine] = await Promise.all([ActionsAPI.inbox(), ActionsAPI.my()]);
      setInbox(ib.data); setMy(mine.data);
      if (isAdmin) { try { const t = await ActionsAPI.team(); setTeam(t.data); } catch { /* ignore */ } }
    } finally { setLoading(false); }
  }, [isAdmin]);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try { await ActionsAPI.sync(); await load(); } finally { setSyncing(false); }
  };

  const onAct = async (a, action) => {
    setBusyId(a.id);
    try {
      const body = action === "escalate" ? { to_step: "admin", comment: "Ескальовано" }
        : action === "resolve" ? { comment: "Виконано" } : {};
      await ActionsAPI.lifecycle(a.id, action, body);
      await load();
    } finally { setBusyId(null); }
  };

  const items = inbox?.items || [];
  const filtered = useMemo(() => prioFilter === "all" ? items : items.filter((x) => x.priority === prioFilter), [items, prioFilter]);

  return (
    <div data-testid="portal-action-center">
      <PageHeader
        title="Центр дій"
        subtitle="Операційні дії: ризики, прострочення та SLA по заявках, контрактах і фінансах"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={sync} disabled={syncing} className="gap-2" data-testid="action-sync">
              {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Синхронізувати
            </Button>
            <Button onClick={() => setCreateOpen(true)} className="gap-2 bg-[#0E5E3A] hover:bg-[#0c4f31]" data-testid="action-create-open">
              <Plus className="h-4 w-4" /> Нова дія
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Activity} label="Всього відкритих" value={inbox?.total ?? 0} testid="action-kpi-total" />
        <StatCard icon={AlertTriangle} label="Прострочено" value={inbox?.overdue ?? 0} testid="action-kpi-overdue" />
        <StatCard icon={Zap} label="Критичні" value={inbox?.by_priority?.critical ?? 0} testid="action-kpi-critical" />
        <StatCard icon={TrendingUp} label="Вплив (₴)" value={money(inbox?.impact_total)} testid="action-kpi-impact" />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="inbox" data-testid="action-tab-inbox">Інбокс ({inbox?.total ?? 0})</TabsTrigger>
            <TabsTrigger value="my" data-testid="action-tab-my">Мої ({my?.total ?? 0})</TabsTrigger>
            {isAdmin && <TabsTrigger value="team" data-testid="action-tab-team">Команда</TabsTrigger>}
            <TabsTrigger value="analytics" data-testid="action-tab-analytics">Аналітика</TabsTrigger>
          </TabsList>
        </Tabs>
        {tab === "inbox" && (
          <div className="flex items-center gap-1.5">
            <Filter className="h-4 w-4 text-slate-400" />
            {["all", "critical", "high", "medium", "low"].map((p) => (
              <button key={p} onClick={() => setPrioFilter(p)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${prioFilter === p ? "bg-[#0E5E3A] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                data-testid={`action-filter-${p}`}>
                {p === "all" ? "Усі" : PRIO[p].label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={6} /></div>
        ) : tab === "inbox" ? (
          filtered.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="Немає відкритих дій" hint="Усі операційні ризики опрацьовано." testid="action-inbox-empty" />
          ) : (
            <ul className="divide-y divide-[hsl(var(--border))]">
              {filtered.map((a) => <ActionRow key={a.id} a={a} onAct={onAct} busy={busyId === a.id} />)}
            </ul>
          )
        ) : tab === "my" ? (
          <MyBuckets my={my} onAct={onAct} busyId={busyId} />
        ) : tab === "team" ? (
          <TeamTable team={team} />
        ) : (
          <AnalyticsPanel inbox={inbox} />
        )}
      </div>

      <CreateActionDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => { setCreateOpen(false); load(); }} />
    </div>
  );
}

const BUCKETS = [
  { key: "overdue", label: "Прострочені", icon: AlertTriangle, color: "#DC2626" },
  { key: "today", label: "Сьогодні", icon: Clock, color: "#9A3412" },
  { key: "this_week", label: "Цього тижня", icon: Clock, color: "#075985" },
  { key: "later", label: "Пізніше", icon: Clock, color: "#64748B" },
];

function MyBuckets({ my, onAct, busyId }) {
  if (!my || my.total === 0) return <EmptyState icon={CheckCircle2} title="Немає призначених дій" hint="Вам поки не призначено жодної дії." testid="action-my-empty" />;
  return (
    <div className="divide-y divide-[hsl(var(--border))]">
      {BUCKETS.map(({ key, label, icon: Icon, color }) => {
        const b = my.buckets?.[key];
        if (!b || b.total === 0) return null;
        return (
          <div key={key}>
            <div className="flex items-center gap-2 px-4 pt-3 text-xs font-bold uppercase tracking-wide" style={{ color }}>
              <Icon className="h-3.5 w-3.5" /> {label} ({b.total})
            </div>
            <ul className="divide-y divide-[hsl(var(--border))]">
              {b.items.map((a) => <ActionRow key={a.id} a={a} onAct={onAct} busy={busyId === a.id} />)}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function TeamTable({ team }) {
  const rows = team?.managers || team?.items || team?.rows || [];
  if (!rows.length) return <EmptyState icon={Users} title="Немає даних по команді" hint="Завантаження навантаження менеджерів." testid="action-team-empty" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[hsl(var(--border))] text-left text-xs uppercase tracking-wide text-slate-400">
            <th className="px-4 py-3">Менеджер</th><th className="px-3 py-3">Відкриті</th>
            <th className="px-3 py-3">В роботі</th><th className="px-3 py-3">Прострочені</th>
            <th className="px-3 py-3">Виконано сьогодні</th><th className="px-3 py-3">Ескальовані</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.owner_id || m.owner_name} className="border-b border-[hsl(var(--border))]" data-testid="action-team-row">
              <td className="px-4 py-3 font-medium text-slate-800">{m.owner_name || m.owner_id || "—"}</td>
              <td className="px-3 py-3">{m.open ?? 0}</td>
              <td className="px-3 py-3">{m.in_progress ?? 0}</td>
              <td className="px-3 py-3 text-[#DC2626]">{m.overdue ?? 0}</td>
              <td className="px-3 py-3 text-[#0E5E3A]">{m.resolved_today ?? 0}</td>
              <td className="px-3 py-3">{m.escalated ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnalyticsPanel({ inbox }) {
  const bp = inbox?.by_priority || {};
  const bs = inbox?.by_source || {};
  return (
    <div className="grid gap-6 p-4 md:grid-cols-2">
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">За пріоритетом</h3>
        <div className="space-y-2">
          {["critical", "high", "medium", "low"].map((p) => (
            <div key={p} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
              <PrioPill p={p} /><span className="font-semibold text-slate-800">{bp[p] || 0}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">За джерелом</h3>
        <div className="space-y-2">
          {Object.keys(bs).length === 0 ? <div className="text-sm text-slate-400">Немає даних</div> :
            Object.entries(bs).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <span className="text-sm text-slate-600">{SOURCE_LABEL[k] || k}</span><span className="font-semibold text-slate-800">{v}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

function CreateActionDialog({ open, onClose, onCreated }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [dueAt, setDueAt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (open) { setTitle(""); setDescription(""); setPriority("medium"); setDueAt(""); setError(""); } }, [open]);

  const submit = async () => {
    if (!title.trim()) { setError("Вкажіть назву"); return; }
    setSaving(true); setError("");
    try {
      await ActionsAPI.create({
        source: "manual", type: "manual", title: title.trim(),
        description: description.trim(), priority,
        due_at: dueAt ? new Date(dueAt).toISOString() : undefined,
      });
      onCreated();
    } catch (e) { setError(e?.response?.data?.detail || "Помилка створення"); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid="action-create-dialog">
        <DialogHeader><DialogTitle>Нова дія</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Назва</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Що потрібно зробити" data-testid="action-title" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Опис</label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Деталі…" data-testid="action-desc" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Пріоритет</label>
              <div className="flex flex-wrap gap-1.5">
                {["critical", "high", "medium", "low"].map((p) => (
                  <button key={p} type="button" onClick={() => setPriority(p)}
                    className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${priority === p ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600"}`}
                    data-testid={`action-prio-${p}`}>{PRIO[p].label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Дедлайн</label>
              <Input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} data-testid="action-due" />
            </div>
          </div>
          {error && <div className="rounded-lg bg-[#FEE2E2] px-3 py-2 text-sm text-[#991B1B]" data-testid="action-error">{error}</div>}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>Скасувати</Button>
          <Button onClick={submit} disabled={saving} className="gap-2 bg-[#0E5E3A] hover:bg-[#0c4f31]" data-testid="action-save">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Створити
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
