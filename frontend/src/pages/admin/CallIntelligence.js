import React, { useEffect, useState, useCallback } from "react";
import { CallIntelAPI } from "@/lib/api";
import { RefreshCw, Sparkles, Phone, PhoneIncoming, PhoneOutgoing, AlertTriangle, CheckCircle2, Clock, XCircle, MicOff, X, Play } from "lucide-react";

/* ──────────────────────────────────────────────────────────────────────────
   Call Intelligence — on-demand transcription + AI summary over Ringostat calls
   Restyled to match ECO.NOVA light admin theme (cream bg, dark-green primary,
   emerald accents) — no more black surfaces.
   ──────────────────────────────────────────────────────────────────────── */

/* Sentiment / intent → tailwind badge classes */
const SENT_STYLE = {
  positive: "bg-emerald-50 text-emerald-700 border-emerald-200",
  negative: "bg-rose-50 text-rose-700 border-rose-200",
  neutral:  "bg-slate-50 text-slate-600 border-slate-200",
};
const INTENT_STYLE = {
  very_high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  high:      "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium:    "bg-amber-50 text-amber-700 border-amber-200",
  low:       "bg-slate-50 text-slate-600 border-slate-200",
};
const STATUS_STYLE = {
  ready:            { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "Готово",           Icon: CheckCircle2 },
  running:          { cls: "bg-sky-50 text-sky-700 border-sky-200",             label: "Обробка…",         Icon: RefreshCw },
  pending:          { cls: "bg-amber-50 text-amber-700 border-amber-200",       label: "У черзі",          Icon: Clock },
  failed:           { cls: "bg-rose-50 text-rose-700 border-rose-200",          label: "Помилка",          Icon: XCircle },
  analyze_failed:   { cls: "bg-rose-50 text-rose-700 border-rose-200",          label: "Помилка аналізу",  Icon: XCircle },
  no_recording:     { cls: "bg-slate-50 text-slate-500 border-slate-200",       label: "Немає запису",     Icon: MicOff },
  empty_transcript: { cls: "bg-amber-50 text-amber-700 border-amber-200",       label: "Порожній транскрипт", Icon: AlertTriangle },
};

function Badge({ map, value }) {
  const cls = map[value] || "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${cls}`}>
      {value || "—"}
    </span>
  );
}

function StatusChip({ status }) {
  const conf = STATUS_STYLE[status] || { cls: "bg-slate-50 text-slate-500 border-slate-200", label: status || "Не оброблено", Icon: Clock };
  const Icon = conf.Icon;
  const spin = status === "running";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${conf.cls}`}>
      <Icon className={`w-3 h-3 ${spin ? "animate-spin" : ""}`} />
      {conf.label}
    </span>
  );
}

export default function CallIntelligence() {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [period, setPeriod] = useState("month");
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState({});
  const [drawer, setDrawer] = useState(null); // { call, data }
  const [toast, setToast] = useState("");
  const [tab, setTab] = useState("calls"); // "calls" | "coaching"
  const [selected, setSelected] = useState({}); // { call_id: true }
  const [bulkBusy, setBulkBusy] = useState(false);
  const [coaching, setCoaching] = useState([]);
  const [coachingLoading, setCoachingLoading] = useState(false);
  const [coachMgr, setCoachMgr] = useState("");

  const flash = (m) => { setToast(m); setTimeout(() => setToast(""), 3500); };

  const loadCalls = useCallback(async () => {
    setLoading(true);
    try {
      const [cfg, st, cl] = await Promise.all([
        CallIntelAPI.config().catch(() => null),
        CallIntelAPI.stats({ days: 30 }).catch(() => null),
        CallIntelAPI.calls({ period, limit: 100 }).catch(() => ({ calls: [] })),
      ]);
      setConfig(cfg);
      setStats(st?.stats || null);
      setCalls(cl?.calls || []);
    } finally { setLoading(false); }
  }, [period]);

  useEffect(() => { loadCalls(); }, [loadCalls]);

  const loadCoaching = useCallback(async () => {
    setCoachingLoading(true);
    try {
      const r = await CallIntelAPI.atRisk({ days: 30, limit: 50, ...(coachMgr ? { manager_id: coachMgr } : {}) });
      setCoaching(r?.items || []);
    } catch { setCoaching([]); } finally { setCoachingLoading(false); }
  }, [coachMgr]);

  useEffect(() => { if (tab === "coaching") loadCoaching(); }, [tab, loadCoaching]);

  const toggleSel = (id) => setSelected((s) => ({ ...s, [id]: !s[id] }));
  const selectedIds = Object.keys(selected).filter((k) => selected[k]);
  const bulkAnalyze = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    flash(`Пакетна обробка ${selectedIds.length} дзвінків…`);
    try {
      const r = await CallIntelAPI.bulkProcess(selectedIds, false);
      flash(`Готово: ${r.succeeded}/${r.processed} успішно${r.failed ? `, ${r.failed} з помилкою` : ""}`);
      setSelected({});
      await loadCalls();
    } catch (e) {
      flash("Помилка пакетної обробки: " + (e?.response?.data?.detail || e.message));
    } finally { setBulkBusy(false); }
  };

  const createTask = async (callId) => {
    flash("Створення завдання…");
    try {
      await CallIntelAPI.apply(callId, { create_task: true });
      flash("Завдання-follow-up створено та призначено менеджеру");
      if (tab === "coaching") loadCoaching();
    } catch (e) {
      flash("Не вдалося створити завдання: " + (e?.response?.data?.detail || e.message));
    }
  };

  const analyze = async (call, force = false) => {
    const id = call.call_id;
    setProcessing((p) => ({ ...p, [id]: true }));
    flash("Розшифровка та AI-аналіз запущені…");
    try {
      const res = await CallIntelAPI.process(id, force);
      if (res?.success) {
        flash("Готово — транскрипт та AI-summary сформовано");
        await loadCalls();
        openDrawer(call);
      } else {
        flash("Не вдалося: " + (res?.error || "невідома помилка"));
      }
    } catch (e) {
      flash("Помилка: " + (e?.response?.data?.detail || e.message));
    } finally {
      setProcessing((p) => ({ ...p, [id]: false }));
    }
  };

  const openDrawer = async (call) => {
    setDrawer({ call, data: null, loading: true });
    try {
      const data = await CallIntelAPI.get(call.call_id);
      setDrawer({ call, data, loading: false });
    } catch {
      setDrawer({ call, data: null, loading: false });
    }
  };

  const configured = config && config.openai_configured;

  const kpis = [
    { label: "Проаналізовано (30д)", value: stats?.total_calls_with_ci ?? 0, tint: "text-slate-900" },
    { label: "Позитивні",             value: stats?.positive ?? 0,          tint: "text-emerald-700" },
    { label: "Негативні",             value: stats?.negative ?? 0,          tint: "text-rose-700" },
    { label: "Високий інтент",        value: stats?.high_intent ?? 0,       tint: "text-emerald-700" },
    { label: "Покриття next-action",  value: stats ? Math.round((stats.next_action_coverage || 0) * 100) + "%" : "—", tint: "text-slate-900" },
  ];

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0 flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#0F3E2C] text-white flex items-center justify-center shrink-0">
              <Sparkles className="w-[18px] h-[18px]" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">AI-розшифровка дзвінків</h1>
              <p className="text-xs sm:text-sm text-gray-500 mt-1.5">
                Дзвінки зберігаються автоматично. Розшифрування та AI-аналіз — <span className="font-semibold text-gray-700">лише по запиту</span>.
              </p>
            </div>
          </div>
          <button
            onClick={loadCalls}
            data-testid="ci-refresh"
            className="shrink-0 inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Оновити
          </button>
        </div>
      </div>

      {/* Config banner */}
      <div
        className={`rounded-xl border p-4 ${configured ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/60"}`}
        data-testid="ci-config"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Статус AI</div>
            <div className="mt-2">
              {config == null
                ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-slate-50 text-slate-600 border-slate-200">завантаження…</span>
                : configured
                  ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200"><CheckCircle2 className="w-3 h-3" /> Підключено</span>
                  : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-amber-50 text-amber-700 border-amber-200"><AlertTriangle className="w-3 h-3" /> Ключ не налаштовано</span>}
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Модель транскрибації</div>
            <div className="mt-2 text-sm font-semibold text-gray-900">whisper-1 (MR Gate) / {config?.transcribe_model || "—"}</div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Модель аналізу</div>
            <div className="mt-2 text-sm font-semibold text-gray-900">{config?.analyze_model || "gpt-4o"}</div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Мова</div>
            <div className="mt-2 text-sm font-semibold text-gray-900">{config?.transcribe_language || "auto"}</div>
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Ключ</div>
            <div className="mt-2 text-xs text-gray-600 leading-relaxed">
              {config?.key_source === "openai"
                ? <>Використовується ваш <span className="font-semibold text-emerald-700">OpenAI</span> ключ (production).</>
                : config?.key_source === "emergent"
                  ? <>Зараз <span className="font-semibold">Emergent (MR Gate)</span>. На production додайте ключ OpenAI у <a href="/app/settings/integrations" className="font-semibold text-emerald-700 hover:text-emerald-800 underline">Admin → Integrations → OpenAI</a>.</>
                  : <>Ключ не налаштовано. Додайте OpenAI у <a href="/app/settings/integrations" className="font-semibold text-emerald-700 hover:text-emerald-800 underline">Admin → Integrations → OpenAI</a>.</>}
            </div>
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-xl border border-gray-200 bg-white p-4 hover:shadow-sm transition-shadow">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{k.label}</div>
            <div className={`mt-2 text-2xl font-bold ${k.tint}`}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 flex gap-1">
        {[["calls", "Дзвінки"], ["coaching", "Коучинг-фід (ризики)"]].map(([v, l]) => (
          <button
            key={v}
            onClick={() => setTab(v)}
            data-testid={`ci-tab-${v}`}
            className={`relative px-4 py-2.5 text-sm font-semibold transition-colors ${
              tab === v ? "text-[#0F3E2C]" : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {l}
            {tab === v && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-[#0F3E2C] rounded-full" />}
          </button>
        ))}
      </div>

      {tab === "calls" && (
        <>
          {/* Period + bulk toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mr-1">Період:</span>
            {[["today", "Сьогодні"], ["week", "Тиждень"], ["month", "Місяць"]].map(([v, l]) => (
              <button
                key={v}
                onClick={() => setPeriod(v)}
                data-testid={`ci-period-${v}`}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  period === v
                    ? "bg-[#0F3E2C] border-[#0F3E2C] text-white"
                    : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
                }`}
              >{l}</button>
            ))}
            <div className="flex-1" />
            {selectedIds.length > 0 && (
              <button
                disabled={bulkBusy}
                onClick={bulkAnalyze}
                data-testid="ci-bulk-analyze"
                className="inline-flex items-center gap-2 rounded-lg bg-[#0F3E2C] px-3.5 py-2 text-xs font-semibold text-white hover:bg-[#0A2E20] disabled:opacity-60 transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {bulkBusy ? "Обробка…" : `Проаналізувати обране (${selectedIds.length})`}
              </button>
            )}
          </div>

          {/* Calls table */}
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="w-10 px-3 py-2.5 text-left"></th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Дзвінок</th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Напрям</th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Тривал.</th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">Запис</th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">AI-статус</th>
                    <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap">AI-summary</th>
                    <th className="px-3 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-gray-500"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {loading && (
                    <tr><td colSpan={8} className="px-3 py-8 text-center text-sm text-gray-500">
                      <RefreshCw className="w-4 h-4 animate-spin inline mr-2" />Завантаження…
                    </td></tr>
                  )}
                  {!loading && calls.length === 0 && (
                    <tr><td colSpan={8} className="px-3 py-10 text-center text-sm text-gray-500">
                      <Phone className="w-6 h-6 inline mr-2 text-gray-300" />
                      Дзвінків за період немає.
                    </td></tr>
                  )}
                  {!loading && calls.map((c) => {
                    const num = c.number || c.from_number || c.caller || c.callee || c.to_number || c.phone || c.call_id;
                    const hasRec = !!c.recording_url;
                    const busy = !!processing[c.call_id];
                    const DirIcon = c.direction === "outbound" ? PhoneOutgoing : PhoneIncoming;
                    return (
                      <tr key={c.call_id} data-testid="ci-call-row" className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-3 py-3 align-top">
                          <input
                            type="checkbox"
                            checked={!!selected[c.call_id]}
                            disabled={!hasRec}
                            onChange={() => toggleSel(c.call_id)}
                            data-testid="ci-row-check"
                            className="rounded border-gray-300 text-[#0F3E2C] focus:ring-[#0F3E2C] disabled:opacity-40"
                          />
                        </td>
                        <td className="px-3 py-3 align-top">
                          <div className="text-sm font-semibold text-gray-900">{num}</div>
                          <div className="text-[11px] text-gray-500 mt-0.5">
                            {c.started_at ? new Date(c.started_at).toLocaleString("uk-UA") : ""}
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top">
                          <span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
                            <DirIcon className={`w-3.5 h-3.5 ${c.direction === "outbound" ? "text-sky-600" : "text-emerald-600"}`} />
                            {c.direction === "inbound" ? "Вхідний" : c.direction === "outbound" ? "Вихідний" : (c.direction || "—")}
                          </span>
                        </td>
                        <td className="px-3 py-3 align-top text-sm text-gray-700 whitespace-nowrap">{c.duration ? `${c.duration}s` : "—"}</td>
                        <td className="px-3 py-3 align-top">
                          {hasRec
                            ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200"><Play className="w-2.5 h-2.5" /> є</span>
                            : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-slate-50 text-slate-500 border-slate-200"><MicOff className="w-2.5 h-2.5" /> немає</span>}
                        </td>
                        <td className="px-3 py-3 align-top"><StatusChip status={c.intelligence_status} /></td>
                        <td className="px-3 py-3 align-top max-w-[320px]">
                          <div className="text-sm text-gray-700 line-clamp-2">
                            {c.ai_summary ? c.ai_summary : <span className="text-gray-400">—</span>}
                          </div>
                          {c.ai_sentiment && <div className="mt-1"><Badge map={SENT_STYLE} value={c.ai_sentiment} /></div>}
                        </td>
                        <td className="px-3 py-3 align-top text-right whitespace-nowrap">
                          <button
                            disabled={!hasRec || busy}
                            onClick={() => analyze(c, c.intelligence_status === "ready")}
                            data-testid="ci-analyze-btn"
                            title={hasRec ? "" : "Немає аудіозапису"}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F3E2C] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0A2E20] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                          >
                            {busy
                              ? <><RefreshCw className="w-3 h-3 animate-spin" />…</>
                              : (c.intelligence_status === "ready"
                                  ? <><Sparkles className="w-3 h-3" />Переаналізувати</>
                                  : <><Sparkles className="w-3 h-3" />Розшифрувати + AI</>)}
                          </button>
                          <button
                            onClick={() => openDrawer(c)}
                            data-testid="ci-details-btn"
                            className="ml-2 inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                          >Деталі</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "coaching" && (
        <div className="space-y-4" data-testid="ci-coaching">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-xs text-gray-600">
              Дзвінки, що потребують уваги (негативний настрій або високий інтент без наступного кроку, 30д)
            </div>
            <div className="flex-1" />
            <input
              placeholder="ID менеджера (фільтр)"
              value={coachMgr}
              onChange={(e) => setCoachMgr(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadCoaching()}
              data-testid="ci-coach-mgr"
              className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#0F3E2C]/20 focus:border-[#0F3E2C]"
            />
            <button
              onClick={loadCoaching}
              className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >Оновити</button>
          </div>

          {coachingLoading && (
            <div className="text-sm text-gray-500 flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />Завантаження…
            </div>
          )}
          {!coachingLoading && coaching.length === 0 && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-6 text-sm text-emerald-800">
              <CheckCircle2 className="w-5 h-5 inline mr-2" />
              Немає дзвінків, що потребують уваги.
            </div>
          )}

          <div className="grid gap-3">
            {coaching.map((c) => (
              <div
                key={c.call_id}
                data-testid="ci-coach-item"
                className={`rounded-xl border bg-white p-4 border-l-4 ${
                  c.sentiment === "negative" ? "border-l-rose-500 border-gray-200" : "border-l-amber-500 border-gray-200"
                } hover:shadow-sm transition-shadow`}
              >
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex-1 min-w-[260px]">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold text-gray-900">{c.number || c.call_id}</span>
                      <Badge map={SENT_STYLE} value={c.sentiment} />
                      <Badge map={INTENT_STYLE} value={c.purchase_intent} />
                      {c.manager_name && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-slate-50 text-slate-600 border-slate-200">
                          {c.manager_name}
                        </span>
                      )}
                      <span className="text-[11px] text-gray-500">
                        {c.started_at ? new Date(c.started_at).toLocaleString("uk-UA") : ""}
                      </span>
                    </div>
                    <div className="mt-2 text-sm text-gray-700 leading-relaxed">{c.summary}</div>
                    {(c.objections || []).length > 0 && (
                      <div className="mt-1.5 text-xs text-gray-500">
                        Заперечення: {c.objections.join("; ")}
                      </div>
                    )}
                    <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-2 text-sm">
                      <span className="font-semibold">Рекомендований крок:</span> {c.suggested_next_step}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 items-end">
                    <button
                      onClick={() => createTask(c.call_id)}
                      data-testid="ci-coach-create-task"
                      className="rounded-lg bg-[#0F3E2C] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0A2E20] transition-colors"
                    >Створити завдання</button>
                    <button
                      onClick={() => openDrawer({ call_id: c.call_id, number: c.number, started_at: c.started_at, recording_url: null })}
                      className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >Деталі</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {drawer && <Drawer state={drawer} onClose={() => setDrawer(null)} onAnalyze={analyze} onCreateTask={createTask} processing={processing} />}

      {toast && (
        <div
          className="fixed bottom-6 right-6 rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 text-sm text-gray-800 z-[90] max-w-sm"
          data-testid="ci-toast"
        >{toast}</div>
      )}
    </div>
  );
}

function Drawer({ state, onClose, onAnalyze, onCreateTask, processing }) {
  const { call, data, loading } = state;
  const ci = data?.intelligence || {};
  const tr = data?.transcript || {};
  const busy = !!processing[call.call_id];
  const num = call.number || call.from_number || call.caller || call.call_id;
  const [taskDone, setTaskDone] = useState(false);

  return (
    <div
      className="fixed inset-0 z-[80] bg-black/40 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <div
        className="w-[min(680px,96vw)] h-full overflow-y-auto bg-white border-l border-gray-200 p-6"
        onClick={(e) => e.stopPropagation()}
        data-testid="ci-drawer"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-lg font-bold text-gray-900">Дзвінок · {num}</div>
            <div className="text-xs text-gray-500 mt-0.5">
              {call.started_at ? new Date(call.started_at).toLocaleString("uk-UA") : ""}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-200 bg-white p-2 text-gray-600 hover:bg-gray-50"
            aria-label="Закрити"
          ><X className="w-4 h-4" /></button>
        </div>

        {call.recording_url && (
          <div className="mt-5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-2">Аудіозапис</div>
            <audio controls src={call.recording_url} className="w-full" data-testid="ci-audio" />
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            disabled={!call.recording_url || busy}
            onClick={() => onAnalyze(call, !!ci.summary)}
            data-testid="ci-drawer-analyze"
            className="inline-flex items-center gap-2 rounded-lg bg-[#0F3E2C] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0A2E20] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {busy ? "Обробка…" : (ci.summary ? "Переаналізувати" : "Розшифрувати + AI-аналіз")}
          </button>
          {ci.summary && (
            <button
              disabled={taskDone}
              onClick={async () => { await onCreateTask(call.call_id); setTaskDone(true); }}
              data-testid="ci-drawer-create-task"
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-60 transition-colors"
            >
              {taskDone ? "✓ Завдання створено" : "Створити завдання-follow-up"}
            </button>
          )}
        </div>

        {loading && (
          <div className="mt-6 text-sm text-gray-500 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />Завантаження…
          </div>
        )}

        {!loading && ci.summary && (
          <>
            <Section title="AI Summary">
              <p className="text-sm text-gray-800 leading-relaxed">{ci.summary}</p>
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetaCell label="Настрій"><Badge map={SENT_STYLE} value={ci.sentiment} /></MetaCell>
                <MetaCell label="Намір купівлі"><Badge map={INTENT_STYLE} value={ci.purchase_intent} /></MetaCell>
                <MetaCell label="Ймовірність угоди"><Badge map={INTENT_STYLE} value={ci.deal_probability} /></MetaCell>
                <MetaCell label="Мова"><span className="text-sm font-semibold text-gray-900">{ci.language || tr.language || "—"}</span></MetaCell>
              </div>
            </Section>

            {Array.isArray(ci.next_actions) && ci.next_actions.length > 0 && (
              <Section title="Наступні дії">
                <ul className="space-y-1.5 text-sm text-gray-800 list-disc list-inside">
                  {ci.next_actions.map((a, i) => (
                    <li key={i}>
                      {typeof a === "string" ? a : (a.action || JSON.stringify(a))}
                      {a.due_date ? <span className="text-gray-500"> · до {a.due_date}</span> : ""}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {Array.isArray(ci.objections) && ci.objections.length > 0 && (
              <Section title="Заперечення">
                <ul className="space-y-1.5 text-sm text-gray-800 list-disc list-inside">
                  {ci.objections.map((o, i) => <li key={i}>{typeof o === "string" ? o : JSON.stringify(o)}</li>)}
                </ul>
              </Section>
            )}
            {Array.isArray(ci.risks) && ci.risks.length > 0 && (
              <Section title="Ризики">
                <ul className="space-y-1.5 text-sm text-gray-800 list-disc list-inside">
                  {ci.risks.map((o, i) => <li key={i}>{typeof o === "string" ? o : JSON.stringify(o)}</li>)}
                </ul>
              </Section>
            )}
          </>
        )}

        {!loading && tr.full_text && (
          <Section title={`Транскрипт${tr.language ? " · " + tr.language : ""}`}>
            <div
              className="whitespace-pre-wrap leading-relaxed text-sm text-gray-800 max-h-80 overflow-y-auto rounded-lg bg-gray-50 border border-gray-200 p-3"
              data-testid="ci-transcript"
            >{tr.full_text}</div>
          </Section>
        )}

        {!loading && !ci.summary && !tr.full_text && (
          <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
            {data?.error ? `Помилка: ${data.error}` : "Ще не розшифровано. Натисніть «Розшифрувати + AI-аналіз»."}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaCell({ label, children }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mt-5 rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-2">{title}</div>
      {children}
    </div>
  );
}
