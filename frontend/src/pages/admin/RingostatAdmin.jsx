// Ringostat Admin — повноцінний центр керування кол-трекінгом
// (ключі / Project ID / webhook / менеджери / дзвінки / статистика / автоматизація)
import React, { useEffect, useState, useCallback } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, PhoneCall, Plug, Webhook,
  Users, BarChart3, Settings2, RefreshCw, Save, RotateCcw, Send, Copy, Check,
  Wifi, WifiOff, Trash2, Plus, Sparkles, KeyRound, Hash, ShieldCheck, Clock,
} from "lucide-react";
import { RingostatAPI } from "@/lib/api";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";

function durFmt(s) {
  if (!s) return "—";
  const n = Number(s); if (isNaN(n)) return String(s);
  const m = Math.floor(n / 60), r = n % 60;
  return `${m}хв ${r}с`;
}
function dtFmt(v) {
  if (!v) return "—";
  try { return new Date(v).toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" }); }
  catch { return String(v); }
}
function DirIcon({ d }) {
  if (d === "inbound") return <PhoneIncoming className="h-4 w-4 text-emerald-600" />;
  if (d === "outbound") return <PhoneOutgoing className="h-4 w-4 text-sky-600" />;
  return <Phone className="h-4 w-4 text-slate-400" />;
}
function CallStatusPill({ s }) {
  const k = String(s || "").toLowerCase();
  const map = {
    answered: { l: "відповів", c: "#065F46", bg: "#ECFDF5", b: "#A7F3D0" },
    completed: { l: "завершено", c: "#065F46", bg: "#ECFDF5", b: "#A7F3D0" },
    missed: { l: "пропущений", c: "#991B1B", bg: "#FEF2F2", b: "#FECACA" },
    "no-answer": { l: "не відповів", c: "#92400E", bg: "#FFFBEB", b: "#FDE68A" },
    busy: { l: "зайнято", c: "#92400E", bg: "#FFFBEB", b: "#FDE68A" },
  };
  const m = map[k] || { l: s || "—", c: "#475569", bg: "#F1F5F9", b: "#E2E8F0" };
  return <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium" style={{ color: m.c, background: m.bg, borderColor: m.b }}>{m.l}</span>;
}

// ── Tab: Підключення ─────────────────────────────────────────────────
function ConnectionTab({ health, reloadHealth }) {
  const [form, setForm] = useState({ api_key: "", project_id: "", webhook_secret: "", enabled: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await RingostatAPI.settings();
      setForm({
        api_key: s.api_key || "", project_id: s.project_id || "",
        webhook_secret: s.webhook_secret || "", enabled: s.enabled !== false,
      });
    } catch { toast.error("Не вдалося завантажити налаштування"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const r = await RingostatAPI.updateSettings(form);
      if (r?.webhook_auto_provisioned) {
        toast.success("Ключі збережено · Webhook автоматично створено та захищено токеном");
      } else if (r?.webhook_secret) {
        toast.success("Налаштування збережено · Webhook активний (див. вкладку Webhook)");
      } else {
        toast.success("Налаштування збережено");
      }
      await load();        // pull back the freshly provisioned webhook_secret
      reloadHealth();
    } catch { toast.error("Не вдалося зберегти (потрібні права головного адміна)"); }
    finally { setSaving(false); }
  };
  const test = async () => {
    setTesting(true); setTestResult(null);
    try {
      const r = await RingostatAPI.testConnection({ api_key: form.api_key, project_id: form.project_id });
      setTestResult(r);
      r.success ? toast.success("З'єднання успішне") : toast.error("З'єднання не вдалося");
    } catch (e) {
      const msg = e?.response?.data?.detail || "Помилка перевірки";
      setTestResult({ success: false, message: msg });
      toast.error(msg);
    } finally { setTesting(false); }
  };
  const reset = async () => {
    if (!window.confirm("Скинути ВСІ налаштування Ringostat до значень за замовчуванням?")) return;
    try { await RingostatAPI.resetSettings(); toast.success("Скинуто до дефолтів"); load(); reloadHealth(); }
    catch { toast.error("Не вдалося скинути"); }
  };

  const conn = health?.connection || {};
  const connected = conn.status === "connected";

  return (
    <div className="space-y-6">
      {/* Health banner */}
      <Card className="p-5">
        <div className="flex items-center gap-4">
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${connected ? "bg-emerald-50" : "bg-rose-50"}`}>
            {connected ? <Wifi className="h-6 w-6 text-emerald-600" /> : <WifiOff className="h-6 w-6 text-rose-500" />}
          </div>
          <div className="flex-1">
            <div className="text-sm font-semibold text-foreground">
              {connected ? "Інтеграцію підключено" : "Інтеграцію не підключено"}
            </div>
            <div className="text-xs text-muted-foreground">
              API-ключ: {conn.api_key_set ? "✓ задано" : "✗ відсутній"} · Project ID: {conn.project_id_set ? "✓ задано" : "✗ відсутній"} · Стан: {conn.enabled ? "увімкнено" : "вимкнено"}
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-foreground">{health?.calls_today ?? 0}</div>
            <div className="text-xs text-muted-foreground">дзвінків сьогодні</div>
          </div>
        </div>
      </Card>

      {/* Credentials form */}
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-emerald-600" />
          <h3 className="text-sm font-semibold">Облікові дані Ringostat API</h3>
        </div>
        {loading ? <TableSkeleton rows={3} /> : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" /> API key (Auth-key)</Label>
              <Input data-testid="ringostat-api-key" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="Auth-key з кабінету Ringostat" />
            </div>
            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5"><Hash className="h-3.5 w-3.5" /> Project ID</Label>
              <Input data-testid="ringostat-project-id" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} placeholder="x-project-id" />
            </div>
            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" /> Webhook secret (token)</Label>
              <Input data-testid="ringostat-webhook-secret" value={form.webhook_secret} onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })} placeholder="токен для ?token=… у webhook URL" />
            </div>
            <div className="flex items-end">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-2.5 w-full">
                <Switch data-testid="ringostat-enabled" checked={form.enabled} onCheckedChange={(v) => setForm({ ...form, enabled: v })} />
                <div>
                  <div className="text-sm font-medium">Інтеграція активна</div>
                  <div className="text-xs text-muted-foreground">головний перемикач (kill switch)</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {testResult && (
          <div className={`mt-4 rounded-lg border px-4 py-3 text-sm ${testResult.success ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800"}`} data-testid="ringostat-test-result">
            {testResult.success ? "✓ " : "✗ "}{testResult.message}
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <Button onClick={save} disabled={saving} data-testid="ringostat-save-btn">
            <Save className="mr-1.5 h-4 w-4" /> {saving ? "Зберігаю…" : "Зберегти"}
          </Button>
          <Button variant="outline" onClick={test} disabled={testing} data-testid="ringostat-test-btn">
            <Plug className="mr-1.5 h-4 w-4" /> {testing ? "Перевіряю…" : "Перевірити з'єднання"}
          </Button>
          <Button variant="ghost" onClick={reset} className="text-rose-600 hover:text-rose-700" data-testid="ringostat-reset-btn">
            <RotateCcw className="mr-1.5 h-4 w-4" /> Скинути до дефолтів
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ── Tab: Webhook ─────────────────────────────────────────────────────
function WebhookTab() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setInfo(await RingostatAPI.webhookInfo()); }
    catch { toast.error("Не вдалося завантажити webhook-інфо"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const copy = async () => {
    try { await navigator.clipboard.writeText(info?.webhook_url || ""); setCopied(true); setTimeout(() => setCopied(false), 1500); toast.success("URL скопійовано"); }
    catch { toast.error("Копіювання не вдалося"); }
  };
  const sendTest = async () => {
    setSending(true);
    try { const r = await RingostatAPI.testWebhook(); toast.success(`Тестовий дзвінок створено: ${r.call_id}`); }
    catch { toast.error("Не вдалося надіслати тест"); }
    finally { setSending(false); }
  };

  if (loading) return <TableSkeleton rows={5} />;
  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="mb-3 flex items-center gap-2"><Webhook className="h-4 w-4 text-emerald-600" /><h3 className="text-sm font-semibold">URL для Webhooks 2.0</h3></div>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 overflow-x-auto rounded-lg border border-border bg-secondary/50 px-3 py-2.5 text-xs text-foreground" data-testid="ringostat-webhook-url">{info?.webhook_url}</code>
          <Button variant="outline" onClick={copy} data-testid="ringostat-copy-webhook">{copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}</Button>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
          <div className="rounded-md border border-border bg-card px-3 py-2"><span className="font-medium text-foreground">Метод:</span> {info?.method}</div>
          <div className="rounded-md border border-border bg-card px-3 py-2"><span className="font-medium text-foreground">Формат:</span> {info?.format}</div>
          <div className="rounded-md border border-border bg-card px-3 py-2"><span className="font-medium text-foreground">Token-auth:</span> {info?.auth?.token_enabled ? "увімкнено" : "вимкнено"}</div>
        </div>
        <Button className="mt-4" variant="outline" onClick={sendTest} disabled={sending} data-testid="ringostat-test-webhook-btn">
          <Send className="mr-1.5 h-4 w-4" /> {sending ? "Надсилаю…" : "Надіслати тестову подію"}
        </Button>
      </Card>

      <Card className="p-6">
        <h3 className="mb-3 text-sm font-semibold">Інструкція з підключення</h3>
        <ol className="space-y-2">
          {(info?.instructions || []).map((step, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted-foreground">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[11px] font-semibold text-emerald-700">{i + 1}</span>
              <span>{step.replace(/^\d+\)\s*/, "")}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

// ── Tab: Менеджери / Extensions ──────────────────────────────────────
function MappingsTab() {
  const [data, setData] = useState({ mappings: [], staff: [] });
  const [loading, setLoading] = useState(true);
  const [newExt, setNewExt] = useState("");
  const [newMgr, setNewMgr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await RingostatAPI.mappings()); }
    catch { toast.error("Не вдалося завантажити прив'язки"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!newExt.trim()) { toast.error("Вкажіть SIP-розширення"); return; }
    try {
      await RingostatAPI.saveMapping({ extension: newExt.trim(), manager_id: newMgr || null });
      toast.success("Прив'язку збережено"); setNewExt(""); setNewMgr(""); load();
    } catch { toast.error("Не вдалося зберегти прив'язку"); }
  };
  const remove = async (ext) => {
    if (!window.confirm(`Видалити прив'язку для розширення ${ext}?`)) return;
    try { await RingostatAPI.deleteMapping(ext); toast.success("Видалено"); load(); }
    catch { toast.error("Не вдалося видалити"); }
  };

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2"><Plus className="h-4 w-4 text-emerald-600" /><h3 className="text-sm font-semibold">Прив'язати розширення до менеджера</h3></div>
        <div className="grid gap-3 sm:grid-cols-[1fr_1.5fr_auto]">
          <Input data-testid="mapping-ext-input" placeholder="SIP-розширення (напр. 101)" value={newExt} onChange={(e) => setNewExt(e.target.value)} />
          <Select value={newMgr || "none"} onValueChange={(v) => setNewMgr(v === "none" ? "" : v)}>
            <SelectTrigger data-testid="mapping-mgr-select"><SelectValue placeholder="Менеджер" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">— без прив'язки —</SelectItem>
              {(data.staff || []).map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.name || s.email} ({s.role})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={add} data-testid="mapping-add-btn"><Plus className="mr-1.5 h-4 w-4" /> Додати</Button>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        {loading ? <div className="p-6"><TableSkeleton rows={4} /></div> : (data.mappings || []).length === 0 ? (
          <EmptyState icon={Users} title="Прив'язок ще немає" hint="Додайте відповідність SIP-розширення → менеджер, щоб дзвінки автоматично призначались." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Розширення</TableHead>
                <TableHead>Менеджер</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead className="text-right">Дія</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.mappings.map((m) => (
                <TableRow key={m.extension} data-testid={`mapping-row-${m.extension}`}>
                  <TableCell className="font-mono font-medium">{m.extension}</TableCell>
                  <TableCell>{m.manager_name || <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell className="text-muted-foreground">{m.manager_email || "—"}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${m.status === "assigned" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                      {m.status === "assigned" ? "призначено" : "не призначено"}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="text-rose-600 hover:text-rose-700" onClick={() => remove(m.extension)} data-testid={`mapping-del-${m.extension}`}><Trash2 className="h-4 w-4" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

// ── Tab: Дзвінки ─────────────────────────────────────────────────────
function CallsTab() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ period: "week", direction: "", status: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period: filters.period, limit: 100 };
      if (filters.direction) params.direction = filters.direction;
      if (filters.status) params.status = filters.status;
      const r = await RingostatAPI.calls(params);
      setCalls(r.calls || []);
    } catch { toast.error("Не вдалося завантажити дзвінки"); }
    finally { setLoading(false); }
  }, [filters]);
  useEffect(() => { load(); }, [load]);

  const simulate = async () => {
    try {
      await RingostatAPI.simulate({ caller_number: "+38067" + Math.floor(Math.random() * 9000000 + 1000000), status: "answered", duration: 60 + Math.floor(Math.random() * 120) });
      toast.success("Тестовий дзвінок зафіксовано"); load();
    } catch { toast.error("Не вдалося симулювати дзвінок"); }
  };

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Період</Label>
            <Select value={filters.period} onValueChange={(v) => setFilters({ ...filters, period: v })}>
              <SelectTrigger className="w-36" data-testid="calls-period"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="today">Сьогодні</SelectItem>
                <SelectItem value="week">Тиждень</SelectItem>
                <SelectItem value="month">Місяць</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Напрям</Label>
            <Select value={filters.direction || "all"} onValueChange={(v) => setFilters({ ...filters, direction: v === "all" ? "" : v })}>
              <SelectTrigger className="w-36" data-testid="calls-direction"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Усі</SelectItem>
                <SelectItem value="inbound">Вхідні</SelectItem>
                <SelectItem value="outbound">Вихідні</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={load} className="ml-auto" data-testid="calls-refresh"><RefreshCw className="mr-1.5 h-4 w-4" /> Оновити</Button>
          <Button variant="outline" onClick={simulate} data-testid="calls-simulate"><Sparkles className="mr-1.5 h-4 w-4" /> Симулювати</Button>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        {loading ? <div className="p-6"><TableSkeleton rows={6} /></div> : calls.length === 0 ? (
          <EmptyState icon={Phone} title="Дзвінків немає" hint="За обраний період дзвінки відсутні. Натисніть «Симулювати», щоб згенерувати тестовий." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Напрям</TableHead>
                <TableHead>Від</TableHead>
                <TableHead>До</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Тривалість</TableHead>
                <TableHead>Розширення</TableHead>
                <TableHead>Час</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {calls.map((c, i) => (
                <TableRow key={c.call_id || c.id || i} data-testid="call-row">
                  <TableCell><div className="flex items-center gap-1.5"><DirIcon d={c.direction} /><span className="text-xs text-muted-foreground">{c.direction === "inbound" ? "вхідний" : c.direction === "outbound" ? "вихідний" : "—"}</span></div></TableCell>
                  <TableCell className="font-mono text-xs">{c.from || c.caller_number || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{c.to || "—"}</TableCell>
                  <TableCell><CallStatusPill s={c.status} /></TableCell>
                  <TableCell>{durFmt(c.duration)}</TableCell>
                  <TableCell className="font-mono text-xs">{c.manager_extension || "—"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{dtFmt(c.started_at || c.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

// ── Tab: Статистика ──────────────────────────────────────────────────
function StatsTab() {
  const [days, setDays] = useState(7);
  const [overview, setOverview] = useState(null);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, mg] = await Promise.all([RingostatAPI.statsOverview(days), RingostatAPI.statsManagers(days)]);
      setOverview(ov); setManagers(mg.managers || []);
    } catch { toast.error("Не вдалося завантажити статистику"); }
    finally { setLoading(false); }
  }, [days]);
  useEffect(() => { load(); }, [load]);

  const t = overview?.totals || {};
  const maxDay = Math.max(1, ...((overview?.by_day || []).map((d) => d.total)));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground">Період аналітики</h3>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-40" data-testid="stats-days"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 днів</SelectItem>
            <SelectItem value="30">30 днів</SelectItem>
            <SelectItem value="90">90 днів</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Phone} label="Усього дзвінків" value={t.all ?? 0} hint={`вх ${t.inbound ?? 0} · вих ${t.outbound ?? 0}`} />
        <StatCard icon={PhoneCall} label="Відповіли" value={t.answered ?? 0} hint={`${overview?.answer_rate ?? 0}% відповідей`} />
        <StatCard icon={PhoneMissed} label="Пропущені" value={t.missed ?? 0} />
        <StatCard icon={Clock} label="Сер. тривалість" value={durFmt(overview?.avg_duration_sec)} />
      </div>

      <Card className="p-6">
        <h3 className="mb-4 text-sm font-semibold">Динаміка по днях</h3>
        {loading ? <TableSkeleton rows={3} /> : (overview?.by_day || []).length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">Немає даних за період</div>
        ) : (
          <div className="flex items-end gap-2 overflow-x-auto pb-2" style={{ minHeight: 140 }}>
            {overview.by_day.map((d) => (
              <div key={d.day} className="flex min-w-[40px] flex-1 flex-col items-center gap-1">
                <div className="flex w-full flex-col justify-end" style={{ height: 110 }}>
                  <div className="w-full rounded-t bg-emerald-500/80" style={{ height: `${(d.total / maxDay) * 100}%`, minHeight: d.total ? 4 : 0 }} title={`${d.total} дзвінків`} />
                </div>
                <span className="text-[10px] font-medium text-foreground">{d.total}</span>
                <span className="text-[10px] text-muted-foreground">{d.day.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="border-b border-border px-6 py-4"><h3 className="text-sm font-semibold">Продуктивність менеджерів</h3></div>
        {loading ? <div className="p-6"><TableSkeleton rows={4} /></div> : managers.length === 0 ? (
          <EmptyState icon={Users} title="Немає даних по менеджерах" hint="Призначте дзвінки менеджерам через прив'язки розширень." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Менеджер</TableHead>
                <TableHead>Розш.</TableHead>
                <TableHead>Усього</TableHead>
                <TableHead>Відп.</TableHead>
                <TableHead>Проп.</TableHead>
                <TableHead>% відп.</TableHead>
                <TableHead>Сер. трив.</TableHead>
                <TableHead>Останній</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {managers.map((m, i) => (
                <TableRow key={(m.manager_id || "unassigned") + i} data-testid="manager-stat-row">
                  <TableCell className="font-medium">{m.manager_name}</TableCell>
                  <TableCell className="font-mono text-xs">{m.extension || "—"}</TableCell>
                  <TableCell>{m.total}</TableCell>
                  <TableCell className="text-emerald-700">{m.answered}</TableCell>
                  <TableCell className="text-rose-600">{m.missed}</TableCell>
                  <TableCell>{m.answer_rate}%</TableCell>
                  <TableCell>{durFmt(m.avg_duration_sec)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{dtFmt(m.last_call_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

// ── Tab: Автоматизація ───────────────────────────────────────────────
function AutomationTab({ reloadHealth }) {
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { const s = await RingostatAPI.settings(); setRules(s.automation_rules || {}); }
    catch { toast.error("Не вдалося завантажити правила"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try { await RingostatAPI.updateSettings({ automation_rules: rules }); toast.success("Правила збережено"); reloadHealth(); }
    catch { toast.error("Не вдалося зберегти (потрібні права master_admin)"); }
    finally { setSaving(false); }
  };
  const upd = (k, v) => setRules((r) => ({ ...r, [k]: v }));

  if (loading || !rules) return <TableSkeleton rows={4} />;
  const Row = ({ k, title, desc, children }) => (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <Switch checked={!!rules[k]} onCheckedChange={(v) => upd(k, v)} data-testid={`rule-${k}`} />
        <div>
          <div className="text-sm font-medium">{title}</div>
          <div className="text-xs text-muted-foreground">{desc}</div>
        </div>
      </div>
      {children}
    </div>
  );

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2"><Settings2 className="h-4 w-4 text-emerald-600" /><h3 className="text-sm font-semibold">Правила автоматизації дзвінків</h3></div>
      <div className="space-y-3">
        <Row k="auto_create_lead" title="Авто-створення ліда" desc="Створювати лід для нового невідомого номера" />
        <Row k="missed_call_task" title="Задача на пропущений" desc="Створювати задачу-нагадування при пропущеному дзвінку">
          <div className="flex items-center gap-2">
            <Input type="number" className="w-20" value={rules.missed_call_task_minutes ?? 5} onChange={(e) => upd("missed_call_task_minutes", Number(e.target.value))} data-testid="rule-missed-minutes" />
            <span className="text-xs text-muted-foreground">хв</span>
          </div>
        </Row>
        <Row k="require_outcome" title="Обов'язковий результат" desc="Вимагати фіксацію підсумку після дзвінка">
          <div className="flex items-center gap-2">
            <Input type="number" className="w-20" value={rules.require_outcome_duration ?? 10} onChange={(e) => upd("require_outcome_duration", Number(e.target.value))} data-testid="rule-outcome-duration" />
            <span className="text-xs text-muted-foreground">сек+</span>
          </div>
        </Row>
      </div>
      <Button className="mt-5" onClick={save} disabled={saving} data-testid="automation-save-btn"><Save className="mr-1.5 h-4 w-4" /> {saving ? "Зберігаю…" : "Зберегти правила"}</Button>
    </Card>
  );
}

// ── Page shell ───────────────────────────────────────────────────────
export default function RingostatAdmin() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const reloadHealth = useCallback(async () => {
    try { setHealth(await RingostatAPI.health()); } catch { /* silent */ }
  }, []);
  useEffect(() => { reloadHealth(); }, [reloadHealth]);

  // Налаштування інтеграції — лише для головного адміна. Менеджерів
  // перенаправляємо на консоль дзвінків (їхній робочий простір).
  if (user && user.role !== "admin") {
    return <Navigate to="/app/crm/calls" replace />;
  }

  return (
    <div className="mx-auto max-w-6xl p-6" data-testid="ringostat-admin-page">
      <PageHeader
        title="Ringostat — кол-трекінг"
        subtitle="Налаштування інтеграції, прив'язка менеджерів, дзвінки та аналітика"
        testid="ringostat-header"
      />
      <Tabs defaultValue="connection" className="mt-6">
        <TabsList className="flex w-full flex-wrap gap-1 bg-secondary/60">
          <TabsTrigger value="connection" data-testid="tab-connection"><Plug className="mr-1.5 h-4 w-4" /> Підключення</TabsTrigger>
          <TabsTrigger value="webhook" data-testid="tab-webhook"><Webhook className="mr-1.5 h-4 w-4" /> Webhook</TabsTrigger>
          <TabsTrigger value="mappings" data-testid="tab-mappings"><Users className="mr-1.5 h-4 w-4" /> Менеджери</TabsTrigger>
          <TabsTrigger value="calls" data-testid="tab-calls"><Phone className="mr-1.5 h-4 w-4" /> Дзвінки</TabsTrigger>
          <TabsTrigger value="stats" data-testid="tab-stats"><BarChart3 className="mr-1.5 h-4 w-4" /> Статистика</TabsTrigger>
          <TabsTrigger value="automation" data-testid="tab-automation"><Settings2 className="mr-1.5 h-4 w-4" /> Автоматизація</TabsTrigger>
        </TabsList>
        <TabsContent value="connection" className="mt-5"><ConnectionTab health={health} reloadHealth={reloadHealth} /></TabsContent>
        <TabsContent value="webhook" className="mt-5"><WebhookTab /></TabsContent>
        <TabsContent value="mappings" className="mt-5"><MappingsTab /></TabsContent>
        <TabsContent value="calls" className="mt-5"><CallsTab /></TabsContent>
        <TabsContent value="stats" className="mt-5"><StatsTab /></TabsContent>
        <TabsContent value="automation" className="mt-5"><AutomationTab reloadHealth={reloadHealth} /></TabsContent>
      </Tabs>
    </div>
  );
}
