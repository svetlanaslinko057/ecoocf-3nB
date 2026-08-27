import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  BookText, AlertTriangle, ListTree, Layers, Search, Plus, Pencil, Trash2,
  RefreshCw, ChevronRight, ChevronDown, ShieldAlert, BadgeCheck, Filter,
  X,
} from "lucide-react";
import { WasteAdminAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const CATEGORY_OPTIONS = [
  { key: "medical", label: "Медичні відходи" },
  { key: "pharma", label: "Фармацевтичні відходи" },
  { key: "batteries", label: "Батарейки" },
  { key: "accumulators", label: "Акумулятори" },
  { key: "electronics", label: "Електроніка (ВЕЕО)" },
  { key: "mercury", label: "Ртутовмісні відходи" },
  { key: "lamps", label: "Лампи" },
  { key: "pesticides", label: "Пестициди" },
  { key: "agrochem", label: "Агрохімія" },
  { key: "paints", label: "Лакофарбові матеріали" },
  { key: "oils", label: "Відпрацьовані масла" },
  { key: "tires", label: "Шини" },
  { key: "plastic", label: "Пластик" },
  { key: "polymers", label: "Полімери" },
  { key: "organic", label: "Органічні відходи" },
  { key: "other_hazard", label: "Інші небезпечні" },
];

const EMPTY_CODE = {
  code: "", name: "", chapter: "", group: "", category: "other_hazard",
  hazardous: false, hazard_class: null, price_from: null,
  license_allowed: true, service_available: true, notes: "",
  human_names: [],
};
const EMPTY_CHAPTER = { code: "", name: "", category: "other_hazard" };
const EMPTY_GROUP = { code: "", name: "", chapter: "" };

export default function WasteCodesAdmin() {
  useSeo(
    "Каталог відходів — Адмін",
    "Керування Національним переліком відходів (Постанова КМУ № 1102): глави, підгрупи, коди.",
  );

  const [stats, setStats] = useState(null);
  const [chapters, setChapters] = useState([]);
  const [groups, setGroups] = useState([]);
  const [codes, setCodes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Фільтри
  const [q, setQ] = useState("");
  const [activeChapter, setActiveChapter] = useState("all");
  const [activeGroup, setActiveGroup] = useState("all");
  const [activeCategory, setActiveCategory] = useState("all");
  const [hazardOnly, setHazardOnly] = useState(false);

  // Модалки
  const [codeForm, setCodeForm] = useState(null);          // {edit?:bool, ...EMPTY_CODE}
  const [chapForm, setChapForm] = useState(null);
  const [grpForm, setGrpForm] = useState(null);
  const [confirm, setConfirm] = useState(null);            // {kind, code, label}
  const [reseedOpen, setReseedOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  // Розгорнуті глави у дереві
  const [expanded, setExpanded] = useState(() => new Set());

  // ── Завантаження ──────────────────────────────────────────────────
  const reloadStats = useCallback(async () => {
    try { setStats(await WasteAdminAPI.stats()); } catch { /* noop */ }
  }, []);

  const reloadChapters = useCallback(async () => {
    try {
      const r = await WasteAdminAPI.listChapters();
      setChapters(r.items || []);
    } catch (e) { toast.error("Не вдалося завантажити глави"); }
  }, []);

  const reloadGroups = useCallback(async (chapter = null) => {
    try {
      const r = await WasteAdminAPI.listGroups(chapter || undefined);
      setGroups(r.items || []);
    } catch (e) { toast.error("Не вдалося завантажити підгрупи"); }
  }, []);

  const reloadCodes = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 500, offset: 0 };
      if (q) params.q = q;
      if (activeChapter !== "all") params.chapter = activeChapter;
      if (activeGroup !== "all") params.group = activeGroup;
      if (activeCategory !== "all") params.category = activeCategory;
      if (hazardOnly) params.hazardous = true;
      const r = await WasteAdminAPI.listCodes(params);
      setCodes(r.items || []);
      setTotal(r.total ?? (r.items || []).length);
    } catch (e) {
      toast.error("Не вдалося завантажити коди");
    } finally {
      setLoading(false);
    }
  }, [q, activeChapter, activeGroup, activeCategory, hazardOnly]);

  useEffect(() => {
    const t = setTimeout(() => {
      reloadStats();
      reloadChapters();
      reloadGroups();
    }, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounced re-fetch when filters change
  useEffect(() => {
    const t = setTimeout(reloadCodes, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [reloadCodes, q]);

  // Скинути підгрупу, якщо змінили главу (тільки на зміну активної глави)
  useEffect(() => {
    const t = setTimeout(() => setActiveGroup("all"), 0);
    return () => clearTimeout(t);
  }, [activeChapter]);

  // ── Дерево «глави -> підгрупи -> кількість кодів» ─────────────────
  const groupsByChapter = useMemo(() => {
    const map = {};
    for (const g of groups) {
      (map[g.chapter || "?"] ||= []).push(g);
    }
    return map;
  }, [groups]);

  const toggleExpanded = (code) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  };

  // ── CRUD: codes ────────────────────────────────────────────────────
  const submitCode = async () => {
    const f = codeForm || {};
    if (!f.code?.trim() || !f.name?.trim()) {
      return toast.error("Код та найменування обовʼязкові");
    }
    setBusy(true);
    try {
      const payload = {
        code: f.code.trim(),
        name: f.name.trim(),
        category: f.category || "other_hazard",
        hazardous: !!f.hazardous,
        hazard_class: f.hazard_class || null,
        chapter: f.chapter || f.code.trim().split(" ")[0],
        group: f.group || f.code.trim().split(" ").slice(0, 2).join(" "),
        parent_code: f.group || f.code.trim().split(" ").slice(0, 2).join(" "),
        price_from: f.price_from !== "" && f.price_from != null ? Number(f.price_from) : null,
        license_allowed: f.license_allowed !== false,
        service_available: f.service_available !== false,
        notes: f.notes || null,
        human_names: Array.isArray(f.human_names) ? f.human_names : String(f.human_names || "").split(",").map((s) => s.trim()).filter(Boolean),
        level: 3,
      };
      if (f.edit) {
        await WasteAdminAPI.updateCode(f.originalCode, payload);
        toast.success("Код оновлено");
      } else {
        await WasteAdminAPI.createCode(payload);
        toast.success("Код створено");
      }
      setCodeForm(null);
      reloadStats();
      reloadCodes();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти код");
    } finally { setBusy(false); }
  };

  const submitChapter = async () => {
    const f = chapForm || {};
    if (!f.code?.trim() || !f.name?.trim()) return toast.error("Код та назва обовʼязкові");
    setBusy(true);
    try {
      const payload = { code: f.code.trim(), name: f.name.trim(), category: f.category };
      if (f.edit) {
        await WasteAdminAPI.updateChapter(f.originalCode, { name: payload.name, category: payload.category });
        toast.success("Главу оновлено");
      } else {
        await WasteAdminAPI.createChapter(payload);
        toast.success("Главу створено");
      }
      setChapForm(null);
      reloadStats();
      reloadChapters();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти главу");
    } finally { setBusy(false); }
  };

  const submitGroup = async () => {
    const f = grpForm || {};
    if (!f.code?.trim() || !f.name?.trim() || !f.chapter) return toast.error("Код, назва та глава обовʼязкові");
    setBusy(true);
    try {
      const payload = { code: f.code.trim(), name: f.name.trim(), chapter: f.chapter };
      if (f.edit) {
        await WasteAdminAPI.updateGroup(f.originalCode, { name: payload.name });
        toast.success("Підгрупу оновлено");
      } else {
        await WasteAdminAPI.createGroup(payload);
        toast.success("Підгрупу створено");
      }
      setGrpForm(null);
      reloadStats();
      reloadGroups();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося зберегти підгрупу");
    } finally { setBusy(false); }
  };

  const doDelete = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.kind === "code") await WasteAdminAPI.deleteCode(confirm.code);
      if (confirm.kind === "chapter") await WasteAdminAPI.deleteChapter(confirm.code);
      if (confirm.kind === "group") await WasteAdminAPI.deleteGroup(confirm.code);
      toast.success("Видалено");
      setConfirm(null);
      reloadStats(); reloadChapters(); reloadGroups(); reloadCodes();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося видалити");
    } finally { setBusy(false); }
  };

  const doReseed = async () => {
    setBusy(true);
    try {
      const r = await WasteAdminAPI.reseedNational();
      toast.success(`Імпорт офіційного переліку: ${r.total} кодів`);
      setReseedOpen(false);
      reloadStats(); reloadChapters(); reloadGroups(); reloadCodes();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося переімпортувати");
    } finally { setBusy(false); }
  };

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="space-y-6" data-testid="waste-codes-admin">
      <PageHeader
        title="Каталог відходів"
        subtitle="Національний перелік відходів (Постанова КМУ № 1102 від 20.10.2023). 18 глав → 81 підгрупа → 431 код."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => setReseedOpen(true)}
              data-testid="reseed-national-btn"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Переімпортувати офіційний перелік
            </Button>
            <Button
              onClick={() => setCodeForm({ ...EMPTY_CODE })}
              data-testid="add-code-btn"
            >
              <Plus className="mr-2 h-4 w-4" />
              Додати код
            </Button>
          </>
        }
      />

      {/* KPI */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          icon={BookText}
          label="Усього кодів"
          value={stats?.codes ?? "—"}
          hint={stats?.official != null ? `${stats.official} офіційних, ${stats.custom || 0} власних` : ""}
          testid="stat-codes"
        />
        <StatCard
          icon={AlertTriangle}
          label="Небезпечні"
          value={stats?.hazardous ?? "—"}
          hint="З абсолютною небезпечністю (*)"
          testid="stat-hazardous"
        />
        <StatCard
          icon={Layers}
          label="Глави"
          value={stats?.chapters ?? "—"}
          hint={`${stats?.groups ?? 0} підгруп`}
          testid="stat-chapters"
        />
        <StatCard
          icon={BadgeCheck}
          label="З тарифом"
          value={stats?.with_price ?? "—"}
          hint="Готові до прорахунку"
          testid="stat-with-price"
        />
      </div>

      <Tabs defaultValue="codes" className="w-full">
        <TabsList className="w-full max-w-md sm:grid sm:grid-cols-3">
          <TabsTrigger value="codes" data-testid="tab-codes">
            <BookText className="mr-2 h-4 w-4" />Коди
          </TabsTrigger>
          <TabsTrigger value="chapters" data-testid="tab-chapters">
            <Layers className="mr-2 h-4 w-4" />Глави
          </TabsTrigger>
          <TabsTrigger value="groups" data-testid="tab-groups">
            <ListTree className="mr-2 h-4 w-4" />Підгрупи
          </TabsTrigger>
        </TabsList>

        {/* ── ВКЛАДКА: КОДИ ─────────────────────────────────────────── */}
        <TabsContent value="codes" className="mt-4">
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            {/* Фільтри */}
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-12">
              <div className="relative md:col-span-4">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  className="pl-9"
                  placeholder="Пошук за кодом або назвою…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  data-testid="codes-search-input"
                />
              </div>
              <div className="md:col-span-2">
                <Select value={activeChapter} onValueChange={setActiveChapter}>
                  <SelectTrigger data-testid="codes-chapter-filter"><SelectValue placeholder="Глава" /></SelectTrigger>
                  <SelectContent className="max-h-72">
                    <SelectItem value="all">Усі глави</SelectItem>
                    {chapters.map((c) => (
                      <SelectItem key={c.code} value={c.code}>{c.code} · {(c.name || "").slice(0, 40)}…</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-3">
                <Select value={activeGroup} onValueChange={setActiveGroup}>
                  <SelectTrigger data-testid="codes-group-filter"><SelectValue placeholder="Підгрупа" /></SelectTrigger>
                  <SelectContent className="max-h-72">
                    <SelectItem value="all">Усі підгрупи</SelectItem>
                    {groups
                      .filter((g) => activeChapter === "all" || g.chapter === activeChapter)
                      .map((g) => (
                        <SelectItem key={g.code} value={g.code}>{g.code} · {(g.name || "").slice(0, 50)}…</SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2">
                <Select value={activeCategory} onValueChange={setActiveCategory}>
                  <SelectTrigger data-testid="codes-category-filter"><SelectValue placeholder="Категорія" /></SelectTrigger>
                  <SelectContent className="max-h-72">
                    <SelectItem value="all">Усі категорії</SelectItem>
                    {CATEGORY_OPTIONS.map((c) => (
                      <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-end gap-2 md:col-span-1">
                <Switch
                  id="hazard-only"
                  checked={hazardOnly}
                  onCheckedChange={setHazardOnly}
                  data-testid="codes-hazard-toggle"
                />
                <label htmlFor="hazard-only" className="text-xs font-medium text-slate-600">
                  Тільки *
                </label>
              </div>
            </div>

            {/* Лічильник + clear filters */}
            <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
              <span data-testid="codes-total">
                Знайдено: <b className="text-slate-800">{total}</b>{" "}
                {codes.length < total && <>(показано перші {codes.length})</>}
              </span>
              {(q || activeChapter !== "all" || activeGroup !== "all" || activeCategory !== "all" || hazardOnly) && (
                <button
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-slate-600 hover:bg-slate-100"
                  onClick={() => {
                    setQ(""); setActiveChapter("all"); setActiveGroup("all"); setActiveCategory("all"); setHazardOnly(false);
                  }}
                  data-testid="clear-filters-btn"
                >
                  <X className="h-3 w-3" /> Скинути фільтри
                </button>
              )}
            </div>

            {/* Таблиця кодів */}
            {loading ? (
              <TableSkeleton rows={8} />
            ) : codes.length === 0 ? (
              <EmptyState
                icon={Filter}
                title="Кодів не знайдено"
                hint="Спробуйте змінити фільтри або скиньте їх."
                testid="codes-empty"
              />
            ) : (
              <div className="overflow-x-auto rounded-xl border">
                <table className="w-full text-sm" data-testid="codes-table">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2.5">Код</th>
                      <th className="px-3 py-2.5">Найменування</th>
                      <th className="px-3 py-2.5">Категорія</th>
                      <th className="px-3 py-2.5">Клас</th>
                      <th className="px-3 py-2.5">Тариф, грн/кг</th>
                      <th className="px-3 py-2.5">Джерело</th>
                      <th className="px-3 py-2.5 w-28 text-right">Дії</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {codes.map((c) => (
                      <tr key={c.code} data-testid={`code-row-${c.code}`} className="hover:bg-slate-50/50">
                        <td className="whitespace-nowrap px-3 py-2 font-mono text-[13px] font-semibold text-slate-800">
                          <span className={c.hazardous ? "text-rose-700" : ""}>{c.code}</span>
                          {c.hazardous && (
                            <ShieldAlert className="ml-1.5 inline h-3.5 w-3.5 text-rose-500" />
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          <div className="line-clamp-2 max-w-[42ch]">{c.name}</div>
                          {c.group && (
                            <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-slate-400">
                              група {c.group}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant="secondary" className="font-normal">
                            {c.category_name || c.category}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{c.hazard_class ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-700">{c.price_from ? `${c.price_from}` : "—"}</td>
                        <td className="px-3 py-2">
                          {c.official ? (
                            <Badge className="bg-emerald-50 font-normal text-emerald-700 hover:bg-emerald-50">
                              КМУ № 1102
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="font-normal">власний</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex justify-end gap-1">
                            <Button
                              size="icon" variant="ghost" className="h-8 w-8"
                              onClick={() => setCodeForm({
                                ...EMPTY_CODE,
                                ...c,
                                edit: true,
                                originalCode: c.code,
                                human_names: (c.human_names || []).join(", "),
                              })}
                              data-testid={`edit-code-${c.code}`}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon" variant="ghost" className="h-8 w-8 text-rose-600"
                              onClick={() => setConfirm({ kind: "code", code: c.code, label: c.name })}
                              data-testid={`delete-code-${c.code}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ── ВКЛАДКА: ГЛАВИ ─────────────────────────────────────────── */}
        <TabsContent value="chapters" className="mt-4">
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Глави «Національного переліку»</h3>
                <p className="text-xs text-slate-500">Підрозділ верхнього рівня: визначає природу та походження відходу.</p>
              </div>
              <Button size="sm" onClick={() => setChapForm({ ...EMPTY_CHAPTER })} data-testid="add-chapter-btn">
                <Plus className="mr-2 h-4 w-4" /> Додати главу
              </Button>
            </div>
            <div className="space-y-1.5">
              {chapters.map((ch) => {
                const open = expanded.has(ch.code);
                const grps = groupsByChapter[ch.code] || [];
                return (
                  <div key={ch.code} className="rounded-xl border bg-white" data-testid={`chapter-row-${ch.code}`}>
                    <div className="flex items-start gap-2 px-3 py-2.5">
                      <button
                        className="mt-0.5 rounded p-0.5 text-slate-400 hover:bg-slate-100"
                        onClick={() => toggleExpanded(ch.code)}
                        data-testid={`toggle-chapter-${ch.code}`}
                      >
                        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                      <span className="mt-0.5 inline-flex h-7 min-w-[2rem] items-center justify-center rounded-md bg-[#0E5E3A]/10 px-2 font-mono text-xs font-bold text-[#0E5E3A]">
                        {ch.code}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="line-clamp-2 text-sm font-medium text-slate-800">{ch.name}</div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {ch.groups_count || 0} підгруп · {ch.codes_count || 0} кодів
                          {!!ch.hazardous_count && (
                            <span className="ml-1 text-rose-600">· {ch.hazardous_count} небезпечних</span>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          size="icon" variant="ghost" className="h-8 w-8"
                          onClick={() => setChapForm({ ...EMPTY_CHAPTER, ...ch, edit: true, originalCode: ch.code })}
                          data-testid={`edit-chapter-${ch.code}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon" variant="ghost" className="h-8 w-8 text-rose-600"
                          onClick={() => setConfirm({ kind: "chapter", code: ch.code, label: ch.name })}
                          data-testid={`delete-chapter-${ch.code}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {open && (
                      <div className="border-t bg-slate-50/40 px-3 py-2">
                        {grps.length === 0 ? (
                          <div className="px-2 py-3 text-xs text-slate-400">Підгруп не знайдено.</div>
                        ) : (
                          <ul className="space-y-1">
                            {grps.map((g) => (
                              <li key={g.code} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-white">
                                <span className="inline-flex min-w-[3.25rem] items-center justify-center rounded bg-white px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-700 border">
                                  {g.code}
                                </span>
                                <span className="line-clamp-1 flex-1 text-sm text-slate-700">{g.name}</span>
                                <span className="shrink-0 text-xs text-slate-400">{g.codes_count || 0} кодів</span>
                                <Button
                                  size="icon" variant="ghost" className="h-7 w-7"
                                  onClick={() => setGrpForm({ ...EMPTY_GROUP, ...g, edit: true, originalCode: g.code })}
                                  data-testid={`edit-group-${g.code}`}
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </Button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </TabsContent>

        {/* ── ВКЛАДКА: ПІДГРУПИ ──────────────────────────────────────── */}
        <TabsContent value="groups" className="mt-4">
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Усі підгрупи</h3>
                <p className="text-xs text-slate-500">Другий рівень ієрархії: тип процесу/походження.</p>
              </div>
              <Button size="sm" onClick={() => setGrpForm({ ...EMPTY_GROUP })} data-testid="add-group-btn">
                <Plus className="mr-2 h-4 w-4" /> Додати підгрупу
              </Button>
            </div>
            <div className="overflow-x-auto rounded-xl border">
              <table className="w-full text-sm" data-testid="groups-table">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2.5">Код</th>
                    <th className="px-3 py-2.5">Глава</th>
                    <th className="px-3 py-2.5">Найменування</th>
                    <th className="px-3 py-2.5">Кодів</th>
                    <th className="px-3 py-2.5 w-28 text-right">Дії</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {groups.map((g) => (
                    <tr key={g.code} data-testid={`group-row-${g.code}`} className="hover:bg-slate-50/50">
                      <td className="whitespace-nowrap px-3 py-2 font-mono text-[13px] font-semibold text-slate-800">{g.code}</td>
                      <td className="px-3 py-2 text-slate-600">{g.chapter}</td>
                      <td className="px-3 py-2 text-slate-700">
                        <div className="line-clamp-2 max-w-[60ch]">{g.name}</div>
                      </td>
                      <td className="px-3 py-2 text-slate-700">{g.codes_count || 0}</td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          <Button
                            size="icon" variant="ghost" className="h-8 w-8"
                            onClick={() => setGrpForm({ ...EMPTY_GROUP, ...g, edit: true, originalCode: g.code })}
                            data-testid={`edit-group-table-${g.code}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon" variant="ghost" className="h-8 w-8 text-rose-600"
                            onClick={() => setConfirm({ kind: "group", code: g.code, label: g.name })}
                            data-testid={`delete-group-${g.code}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ── МОДАЛКА: КОД ────────────────────────────────────────────── */}
      <Dialog open={!!codeForm} onOpenChange={(o) => !o && setCodeForm(null)}>
        <DialogContent className="max-w-2xl" data-testid="code-form-dialog">
          <DialogHeader>
            <DialogTitle>{codeForm?.edit ? "Редагувати код" : "Новий код"}</DialogTitle>
            <DialogDescription>
              Код виду відходу у форматі «NN NN NN», офіційний — з постанови КМУ № 1102.
              Зірочка в кінці (*) — абсолютна небезпечність.
            </DialogDescription>
          </DialogHeader>
          {codeForm && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="md:col-span-1">
                <label className="mb-1 block text-xs font-medium text-slate-600">Код *</label>
                <Input
                  placeholder="20 01 21*"
                  value={codeForm.code || ""}
                  onChange={(e) => setCodeForm({ ...codeForm, code: e.target.value, hazardous: e.target.value.includes("*") })}
                  disabled={!!codeForm.edit}
                  data-testid="code-form-code"
                />
              </div>
              <div className="md:col-span-1">
                <label className="mb-1 block text-xs font-medium text-slate-600">Категорія *</label>
                <Select
                  value={codeForm.category || "other_hazard"}
                  onValueChange={(v) => setCodeForm({ ...codeForm, category: v })}
                >
                  <SelectTrigger data-testid="code-form-category"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => (
                      <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-medium text-slate-600">Найменування *</label>
                <Textarea
                  rows={3}
                  placeholder="Найменування виду відходу за постановою…"
                  value={codeForm.name || ""}
                  onChange={(e) => setCodeForm({ ...codeForm, name: e.target.value })}
                  data-testid="code-form-name"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Глава</label>
                <Input
                  placeholder="20"
                  value={codeForm.chapter || ""}
                  onChange={(e) => setCodeForm({ ...codeForm, chapter: e.target.value })}
                  data-testid="code-form-chapter"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Підгрупа</label>
                <Input
                  placeholder="20 01"
                  value={codeForm.group || ""}
                  onChange={(e) => setCodeForm({ ...codeForm, group: e.target.value })}
                  data-testid="code-form-group"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Клас небезпеки</label>
                <Select
                  value={codeForm.hazard_class ? String(codeForm.hazard_class) : "none"}
                  onValueChange={(v) => setCodeForm({ ...codeForm, hazard_class: v === "none" ? null : Number(v) })}
                >
                  <SelectTrigger data-testid="code-form-hazclass"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— (не визначено)</SelectItem>
                    <SelectItem value="1">1 (надзвичайно небезпечні)</SelectItem>
                    <SelectItem value="2">2 (високонебезпечні)</SelectItem>
                    <SelectItem value="3">3 (помірно небезпечні)</SelectItem>
                    <SelectItem value="4">4 (мало небезпечні)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Тариф (грн/кг)</label>
                <Input
                  type="number" step="0.01"
                  placeholder="напр. 38"
                  value={codeForm.price_from ?? ""}
                  onChange={(e) => setCodeForm({ ...codeForm, price_from: e.target.value })}
                  data-testid="code-form-price"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-medium text-slate-600">
                  Синоніми для пошуку (через кому)
                </label>
                <Input
                  placeholder="ртутні лампи, люмінесцентні лампи, лампи денного світла"
                  value={typeof codeForm.human_names === "string" ? codeForm.human_names : (codeForm.human_names || []).join(", ")}
                  onChange={(e) => setCodeForm({ ...codeForm, human_names: e.target.value })}
                  data-testid="code-form-synonyms"
                />
              </div>
              <div className="md:col-span-2 flex items-center justify-between rounded-lg border bg-slate-50/60 px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={!!codeForm.hazardous}
                    onCheckedChange={(v) => setCodeForm({ ...codeForm, hazardous: v })}
                    data-testid="code-form-hazardous"
                  />
                  <span className="text-sm text-slate-700">Небезпечний (*)</span>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={codeForm.license_allowed !== false}
                    onCheckedChange={(v) => setCodeForm({ ...codeForm, license_allowed: v })}
                    data-testid="code-form-license"
                  />
                  <span className="text-sm text-slate-700">Дозволено ліцензією</span>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={codeForm.service_available !== false}
                    onCheckedChange={(v) => setCodeForm({ ...codeForm, service_available: v })}
                    data-testid="code-form-service"
                  />
                  <span className="text-sm text-slate-700">Послуга доступна</span>
                </div>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-medium text-slate-600">Нотатки</label>
                <Textarea
                  rows={2}
                  placeholder="Внутрішні нотатки, особливості…"
                  value={codeForm.notes || ""}
                  onChange={(e) => setCodeForm({ ...codeForm, notes: e.target.value })}
                  data-testid="code-form-notes"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCodeForm(null)} data-testid="code-form-cancel">Скасувати</Button>
            <Button onClick={submitCode} disabled={busy} data-testid="code-form-save">
              {codeForm?.edit ? "Зберегти" : "Створити"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── МОДАЛКА: ГЛАВА ─────────────────────────────────────────── */}
      <Dialog open={!!chapForm} onOpenChange={(o) => !o && setChapForm(null)}>
        <DialogContent data-testid="chapter-form-dialog">
          <DialogHeader>
            <DialogTitle>{chapForm?.edit ? "Редагувати главу" : "Нова глава"}</DialogTitle>
            <DialogDescription>Глави верхнього рівня (двозначний код, наприклад «18»).</DialogDescription>
          </DialogHeader>
          {chapForm && (
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Код *</label>
                <Input
                  placeholder="21"
                  maxLength={2}
                  value={chapForm.code || ""}
                  onChange={(e) => setChapForm({ ...chapForm, code: e.target.value })}
                  disabled={!!chapForm.edit}
                  data-testid="chapter-form-code"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Найменування *</label>
                <Textarea
                  rows={3}
                  value={chapForm.name || ""}
                  onChange={(e) => setChapForm({ ...chapForm, name: e.target.value })}
                  data-testid="chapter-form-name"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Категорія</label>
                <Select
                  value={chapForm.category || "other_hazard"}
                  onValueChange={(v) => setChapForm({ ...chapForm, category: v })}
                >
                  <SelectTrigger data-testid="chapter-form-category"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => (
                      <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setChapForm(null)}>Скасувати</Button>
            <Button onClick={submitChapter} disabled={busy} data-testid="chapter-form-save">
              {chapForm?.edit ? "Зберегти" : "Створити"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── МОДАЛКА: ПІДГРУПА ──────────────────────────────────────── */}
      <Dialog open={!!grpForm} onOpenChange={(o) => !o && setGrpForm(null)}>
        <DialogContent data-testid="group-form-dialog">
          <DialogHeader>
            <DialogTitle>{grpForm?.edit ? "Редагувати підгрупу" : "Нова підгрупа"}</DialogTitle>
            <DialogDescription>Чотиризначний код у форматі «NN NN», наприклад «20 01».</DialogDescription>
          </DialogHeader>
          {grpForm && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Код *</label>
                <Input
                  placeholder="20 01"
                  value={grpForm.code || ""}
                  onChange={(e) => setGrpForm({ ...grpForm, code: e.target.value })}
                  disabled={!!grpForm.edit}
                  data-testid="group-form-code"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Глава *</label>
                <Select
                  value={grpForm.chapter || ""}
                  onValueChange={(v) => setGrpForm({ ...grpForm, chapter: v })}
                >
                  <SelectTrigger data-testid="group-form-chapter"><SelectValue placeholder="Оберіть главу" /></SelectTrigger>
                  <SelectContent className="max-h-72">
                    {chapters.map((c) => (
                      <SelectItem key={c.code} value={c.code}>{c.code} · {(c.name || "").slice(0, 50)}…</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-medium text-slate-600">Найменування *</label>
                <Textarea
                  rows={3}
                  value={grpForm.name || ""}
                  onChange={(e) => setGrpForm({ ...grpForm, name: e.target.value })}
                  data-testid="group-form-name"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setGrpForm(null)}>Скасувати</Button>
            <Button onClick={submitGroup} disabled={busy} data-testid="group-form-save">
              {grpForm?.edit ? "Зберегти" : "Створити"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── DELETE CONFIRM ─────────────────────────────────────────── */}
      <AlertDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent data-testid="delete-confirm">
          <AlertDialogHeader>
            <AlertDialogTitle>Видалити запис?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirm && (
                <>
                  <span className="block">
                    {confirm.kind === "code" && "Код"}
                    {confirm.kind === "chapter" && "Главу"}
                    {confirm.kind === "group" && "Підгрупу"}
                    {" "}<b className="font-mono text-slate-900">{confirm.code}</b>
                  </span>
                  <span className="mt-2 block text-slate-600">{confirm.label}</span>
                  <span className="mt-3 block text-rose-600">Дія незворотна.</span>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Скасувати</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} disabled={busy} className="bg-rose-600 hover:bg-rose-700" data-testid="delete-confirm-action">
              Видалити
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── RESEED CONFIRM ─────────────────────────────────────────── */}
      <AlertDialog open={reseedOpen} onOpenChange={setReseedOpen}>
        <AlertDialogContent data-testid="reseed-confirm">
          <AlertDialogHeader>
            <AlertDialogTitle>Переімпортувати офіційний перелік?</AlertDialogTitle>
            <AlertDialogDescription>
              Усі поточні коди, глави та підгрупи будуть <b>видалені</b> та замінені офіційним
              «Національним переліком відходів» (Постанова КМУ № 1102 від 20.10.2023): 18 глав, 81 підгрупа, 431 код.
              Будь-які ваші зміни в існуючих кодах буде втрачено.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Скасувати</AlertDialogCancel>
            <AlertDialogAction onClick={doReseed} disabled={busy} data-testid="reseed-confirm-action">
              Переімпортувати
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
