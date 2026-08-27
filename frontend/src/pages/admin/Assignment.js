import React, { useEffect, useState, useCallback } from "react";
import { Search, Building2, UserCheck, Inbox } from "lucide-react";
import { StaffAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill } from "@/components/manager/ManagerUI";
import { LEAD_STATUS_LABELS, LEAD_STATUS_TONE, fmtMoney, fmtDate } from "@/lib/managerMeta";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

export default function Assignment() {
  useSeo("Розподіл лідів", "Призначення та реасайн лідів між менеджерами.");
  const [managers, setManagers] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | unassigned | <managerId>
  const [q, setQ] = useState("");

  const loadManagers = useCallback(() => {
    StaffAPI.members({ role: "manager" }).then((r) => setManagers(r.items || [])).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params = { q: q || undefined };
    if (filter === "unassigned") params.unassigned = true;
    else if (filter !== "all") params.managerId = filter;
    StaffAPI.leads(params)
      .then((r) => setItems(r.items || []))
      .catch(() => toast.error("Не вдалося завантажити ліди"))
      .finally(() => setLoading(false));
  }, [filter, q]);

  useEffect(() => { loadManagers(); }, [loadManagers]);
  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  const reassign = async (lead, managerId) => {
    const mgr = managers.find((m) => m.id === managerId);
    setItems((p) => p.map((x) => (x.id === lead.id ? { ...x, managerId, ownerName: mgr?.name } : x)));
    try {
      await StaffAPI.assign([lead.id], managerId);
      toast.success(`Ліда призначено: ${mgr?.name || "менеджер"}`);
      if (filter !== "all") load();
    } catch { toast.error("Не вдалося призначити"); load(); }
  };

  const unassignedCount = items.filter((i) => !i.managerId).length;

  return (
    <div data-testid="assignment-page">
      <PageHeader title="Розподіл лідів" subtitle="Призначення та реасайн лідів між менеджерами" />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {[["all", "Усі"], ["unassigned", "Без менеджера"]].map(([v, label]) => (
            <button key={v} onClick={() => setFilter(v)} data-testid={`assign-filter-${v}`}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${filter === v ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"}`}>
              {label}
            </button>
          ))}
          <Select value={managers.some((m) => m.id === filter) ? filter : ""} onValueChange={(v) => setFilter(v)}>
            <SelectTrigger className="h-[34px] w-[200px]" data-testid="assign-filter-manager"><SelectValue placeholder="За менеджером…" /></SelectTrigger>
            <SelectContent>{managers.map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="relative sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук: ім'я, компанія…" className="pl-9" data-testid="assign-search" />
        </div>
      </div>

      {filter === "unassigned" && !loading && items.length > 0 && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-[#FDE68A] bg-[#FFFBEB] p-3 text-sm text-[#92400E]">
          <Inbox className="h-4 w-4" /> {unassignedCount} лідів без відповідального — призначте менеджера.
        </div>
      )}

      {loading ? <TableSkeleton rows={6} /> : items.length === 0 ? (
        <EmptyState icon={UserCheck} title="Лідів не знайдено" hint="Змініть фільтр або пошук." testid="assign-empty" />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3 font-semibold">Клієнт</th>
                  <th className="px-4 py-3 font-semibold">Статус</th>
                  <th className="px-4 py-3 font-semibold text-right">Бюджет</th>
                  <th className="px-4 py-3 font-semibold">Поточний менеджер</th>
                  <th className="px-4 py-3 font-semibold">Призначити</th>
                </tr>
              </thead>
              <tbody>
                {items.map((l) => (
                  <tr key={l.id} className="border-b border-slate-50 last:border-0 hover:bg-[#F2F8F3]/50" data-testid={`assign-row-${l.id}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 shrink-0 text-slate-300" />
                        <div>
                          <div className="font-medium text-slate-900">{l.company || l.name}</div>
                          <div className="text-xs text-slate-400">{l.name} · {fmtDate(l.created_at)}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3"><StatusPill tone={LEAD_STATUS_TONE[l.status]}>{LEAD_STATUS_LABELS[l.status] || l.status}</StatusPill></td>
                    <td className="px-4 py-3 text-right font-medium text-slate-800">{l.budgetEur ? fmtMoney(l.budgetEur) : "—"}</td>
                    <td className="px-4 py-3">
                      {l.ownerName ? <span className="text-slate-700">{l.ownerName}</span> : <StatusPill tone="warn">Без менеджера</StatusPill>}
                    </td>
                    <td className="px-4 py-3">
                      <Select value={l.managerId || ""} onValueChange={(v) => reassign(l, v)}>
                        <SelectTrigger className="h-8 w-[190px]" data-testid={`assign-select-${l.id}`}><SelectValue placeholder="Обрати менеджера…" /></SelectTrigger>
                        <SelectContent>{managers.map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
