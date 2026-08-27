// ECO Message Center — directed messaging
// Admin → менеджери + клієнти ;  Менеджер → клієнти
import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Send, Inbox, Mail, RefreshCw, Users, Building2, CheckCheck,
  Megaphone, AlertTriangle, ChevronRight, Loader2, Search,
} from "lucide-react";
import { PortalAPI } from "@/lib/api";
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

const PRIORITY_META = {
  high: { label: "Високий", cls: "bg-[#FEE2E2] text-[#991B1B]" },
  normal: { label: "Звичайний", cls: "bg-[#E0F2FE] text-[#075985]" },
  low: { label: "Низький", cls: "bg-slate-100 text-slate-600" },
};

function PriorityPill({ priority }) {
  const m = PRIORITY_META[priority] || PRIORITY_META.normal;
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${m.cls}`}>{m.label}</span>;
}

export default function MessageCenter() {
  useSeo("Повідомлення · CRM", "Центр повідомлень: адмін пише менеджерам і клієнтам, менеджер — клієнтам.");
  const { user } = useAuth();
  const isAdmin = ["admin", "owner", "master_admin"].includes((user?.role || "").toLowerCase());

  const [tab, setTab] = useState("inbox");
  const [inbox, setInbox] = useState([]);
  const [unread, setUnread] = useState(0);
  const [sent, setSent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [composeOpen, setComposeOpen] = useState(false);

  const loadInbox = useCallback(async () => {
    try {
      const r = await PortalAPI.notifications({ limit: 100 });
      setInbox(r.items || []);
      setUnread(r.unread || 0);
    } catch { setInbox([]); }
  }, []);

  const loadSent = useCallback(async () => {
    try {
      const r = await PortalAPI.sentMessages({ limit: 100 });
      setSent(r.items || []);
    } catch { setSent([]); }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadInbox(), loadSent()]);
    setLoading(false);
  }, [loadInbox, loadSent]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const markRead = async (n) => {
    if (n.read) return;
    try {
      await PortalAPI.markNotificationRead(n.id);
      setInbox((p) => p.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      setUnread((u) => Math.max(0, u - 1));
    } catch { /* ignore */ }
  };
  const markAll = async () => {
    try { await PortalAPI.markAllNotificationsRead(); setInbox((p) => p.map((x) => ({ ...x, read: true }))); setUnread(0); }
    catch { /* ignore */ }
  };

  return (
    <div data-testid="portal-message-center">
      <PageHeader
        title="Центр повідомлень"
        subtitle={isAdmin ? "Надсилайте повідомлення менеджерам та клієнтам" : "Надсилайте повідомлення клієнтам"}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={loadAll} className="gap-2" data-testid="msg-refresh">
              <RefreshCw className="h-4 w-4" /> Оновити
            </Button>
            <Button onClick={() => setComposeOpen(true)} className="gap-2 bg-[#0E5E3A] hover:bg-[#0c4f31]" data-testid="msg-compose-open">
              <Send className="h-4 w-4" /> Нове повідомлення
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard icon={Inbox} label="Непрочитані" value={unread} testid="msg-kpi-unread" />
        <StatCard icon={Mail} label="Вхідні" value={inbox.length} testid="msg-kpi-inbox" />
        <StatCard icon={Send} label="Надіслані" value={sent.length} testid="msg-kpi-sent" />
      </div>

      <div className="mb-4 flex items-center justify-between">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="inbox" data-testid="msg-tab-inbox">Вхідні ({inbox.length})</TabsTrigger>
            <TabsTrigger value="sent" data-testid="msg-tab-sent">Надіслані ({sent.length})</TabsTrigger>
          </TabsList>
        </Tabs>
        {tab === "inbox" && unread > 0 && (
          <Button variant="ghost" onClick={markAll} className="gap-2 text-[#0E5E3A]" data-testid="msg-mark-all">
            <CheckCheck className="h-4 w-4" /> Прочитати всі
          </Button>
        )}
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? (
          <div className="p-4"><TableSkeleton rows={6} /></div>
        ) : tab === "inbox" ? (
          inbox.length === 0 ? (
            <EmptyState icon={Inbox} title="Немає вхідних" hint="Тут зʼявляться повідомлення від адміністрації." testid="msg-inbox-empty" />
          ) : (
            <ul className="divide-y divide-[hsl(var(--border))]">
              {inbox.map((n) => (
                <li
                  key={n.id}
                  onClick={() => markRead(n)}
                  className={`flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-slate-50 ${n.read ? "" : "bg-[#F4FBEF]"}`}
                  data-testid="msg-inbox-row"
                >
                  <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#0E5E3A]/10">
                    {n.kind === "message" ? <Megaphone className="h-4 w-4 text-[#0E5E3A]" /> : <AlertTriangle className="h-4 w-4 text-[#92400E]" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{n.title}</span>
                      {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-[#5BC47A]" />}
                      {n.priority && n.priority !== "normal" && <PriorityPill priority={n.priority} />}
                    </div>
                    {n.body && <div className="mt-0.5 text-sm text-slate-600">{n.body}</div>}
                    <div className="mt-1 text-xs text-slate-400">
                      {n.from_name ? `Від: ${n.from_name}` : "Система"} · {fmtDateTime(n.created_at)}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )
        ) : sent.length === 0 ? (
          <EmptyState icon={Send} title="Немає надісланих" hint="Натисніть «Нове повідомлення», щоб написати команді чи клієнтам." testid="msg-sent-empty" />
        ) : (
          <ul className="divide-y divide-[hsl(var(--border))]">
            {sent.map((m) => (
              <li key={m.id} className="flex items-start gap-3 px-4 py-3" data-testid="msg-sent-row">
                <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#5BC47A]/15">
                  {m.audience === "managers" ? <Users className="h-4 w-4 text-[#0E5E3A]" /> : <Building2 className="h-4 w-4 text-[#0E5E3A]" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">{m.title}</span>
                    {m.priority && m.priority !== "normal" && <PriorityPill priority={m.priority} />}
                  </div>
                  {m.body && <div className="mt-0.5 text-sm text-slate-600">{m.body}</div>}
                  <div className="mt-1 text-xs text-slate-400">
                    {m.audience === "managers" ? "Менеджерам" : "Клієнтам"} · {m.recipient_count} одерж. · {fmtDateTime(m.created_at)}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-slate-300" />
              </li>
            ))}
          </ul>
        )}
      </div>

      <ComposeDialog
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        isAdmin={isAdmin}
        onSent={() => { setComposeOpen(false); loadAll(); setTab("sent"); }}
      />
    </div>
  );
}

function ComposeDialog({ open, onClose, isAdmin, onSent }) {
  const [audience, setAudience] = useState("clients");
  const [scope, setScope] = useState("all");
  const [recipients, setRecipients] = useState({ managers: [], clients: [] });
  const [selected, setSelected] = useState([]);
  const [search, setSearch] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [loadingRec, setLoadingRec] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError(""); setSelected([]); setScope("all"); setSearch("");
    setLoadingRec(true);
    PortalAPI.messageRecipients()
      .then((r) => {
        setRecipients({ managers: r.managers || [], clients: r.clients || [] });
        setAudience(r.can_message_managers ? "managers" : "clients");
      })
      .catch(() => setError("Не вдалося завантажити одержувачів"))
      .finally(() => setLoadingRec(false));
  }, [open]);

  useEffect(() => { setSelected([]); }, [audience]);

  const list = audience === "managers" ? recipients.managers : recipients.clients;
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((x) => (x.name || "").toLowerCase().includes(q) || (x.email || "").toLowerCase().includes(q));
  }, [list, search]);

  const toggle = (id) => setSelected((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const submit = async () => {
    setError("");
    if (!title.trim() || !body.trim()) { setError("Вкажіть тему та текст"); return; }
    if (scope === "selected" && selected.length === 0) { setError("Оберіть одержувачів"); return; }
    setSending(true);
    try {
      const r = await PortalAPI.sendMessage({
        audience, scope,
        recipient_ids: scope === "selected" ? selected : [],
        title: title.trim(), body: body.trim(), priority,
      });
      if (r.success) { setTitle(""); setBody(""); setPriority("normal"); onSent(); }
      else setError("Не вдалося надіслати");
    } catch (e) {
      setError(e?.response?.data?.detail || "Помилка надсилання");
    } finally { setSending(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="msg-compose-dialog">
        <DialogHeader><DialogTitle>Нове повідомлення</DialogTitle></DialogHeader>

        <div className="space-y-4">
          {/* Audience */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Кому</label>
            <div className="flex gap-2">
              {isAdmin && (
                <button type="button" onClick={() => setAudience("managers")}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors ${audience === "managers" ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                  data-testid="msg-aud-managers">
                  <Users className="h-4 w-4" /> Менеджерам
                </button>
              )}
              <button type="button" onClick={() => setAudience("clients")}
                className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors ${audience === "clients" ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                data-testid="msg-aud-clients">
                <Building2 className="h-4 w-4" /> Клієнтам
              </button>
            </div>
          </div>

          {/* Scope */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Охоплення</label>
            <div className="flex gap-2">
              <button type="button" onClick={() => setScope("all")}
                className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${scope === "all" ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                data-testid="msg-scope-all">
                Усім ({list.length})
              </button>
              <button type="button" onClick={() => setScope("selected")}
                className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${scope === "selected" ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                data-testid="msg-scope-selected">
                Обрати ({selected.length})
              </button>
            </div>
          </div>

          {scope === "selected" && (
            <div className="rounded-xl border border-slate-200">
              <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
                <Search className="h-4 w-4 text-slate-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Пошук…"
                  className="w-full bg-transparent text-sm outline-none" data-testid="msg-rec-search" />
              </div>
              <div className="max-h-44 overflow-y-auto">
                {loadingRec ? (
                  <div className="flex items-center justify-center py-6 text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /></div>
                ) : filtered.length === 0 ? (
                  <div className="py-6 text-center text-sm text-slate-400">Нічого не знайдено</div>
                ) : filtered.map((x) => (
                  <label key={x.id} className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-slate-50" data-testid="msg-rec-item">
                    <input type="checkbox" checked={selected.includes(x.id)} onChange={() => toggle(x.id)}
                      className="h-4 w-4 accent-[#0E5E3A]" />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-slate-800">{x.name}</div>
                      {x.email && <div className="truncate text-xs text-slate-400">{x.email}</div>}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Title + body + priority */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Тема</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Тема повідомлення" data-testid="msg-title" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Текст</label>
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} placeholder="Текст повідомлення…" data-testid="msg-body" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Пріоритет</label>
            <div className="flex gap-2">
              {["low", "normal", "high"].map((p) => (
                <button key={p} type="button" onClick={() => setPriority(p)}
                  className={`flex-1 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${priority === p ? "border-[#0E5E3A] bg-[#0E5E3A]/5 text-[#0E5E3A]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                  data-testid={`msg-priority-${p}`}>
                  {PRIORITY_META[p].label}
                </button>
              ))}
            </div>
          </div>

          {error && <div className="rounded-lg bg-[#FEE2E2] px-3 py-2 text-sm text-[#991B1B]" data-testid="msg-error">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={sending}>Скасувати</Button>
          <Button onClick={submit} disabled={sending} className="gap-2 bg-[#0E5E3A] hover:bg-[#0c4f31]" data-testid="msg-send">
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Надіслати
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
