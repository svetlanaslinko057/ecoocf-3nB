import React, { useEffect, useState, useCallback } from "react";
import { Inbox, Phone, Mail, Building2, Search, MessageSquare } from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";

const STATUS_TABS = [
  { key: "", label: "Усі" },
  { key: "new", label: "Нові" },
  { key: "in_progress", label: "В роботі" },
  { key: "contacted", label: "Зв'язалися" },
  { key: "closed", label: "Закриті" },
];

const STATUS_CLS = {
  new: "border-[#BAE6FD] bg-[#F0F9FF] text-[#075985]",
  in_progress: "border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]",
  contacted: "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]",
  closed: "border-[hsl(var(--border))] bg-[hsl(var(--secondary))] text-slate-500",
};

const TYPE_LABEL = { callback: "Дзвінок", inquiry: "Звернення", request: "Заявка" };

export default function Inquiries() {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("");
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await PortalAPI.inquiries({ ...(tab ? { status: tab } : {}), ...(q ? { q } : {}) });
      setItems(d.items || []);
      setCounts(d.counts || {});
    } catch (e) {
      toast.error("Не вдалося завантажити звернення");
    } finally {
      setLoading(false);
    }
  }, [tab, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 350 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const setStatus = async (id, status) => {
    try {
      await PortalAPI.updateInquiry(id, { status });
      toast.success("Статус оновлено");
      load();
    } catch (e) {
      toast.error("Не вдалося оновити");
    }
  };

  return (
    <div data-testid="inquiries-page">
      <PageHeader title="Звернення з сайту" subtitle="Запити на дзвінок та звернення з публічних форм" testid="inquiries-header" />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard icon={Inbox} label="Усього" value={counts.total ?? 0} testid="inq-stat-total" />
        <StatCard icon={MessageSquare} label="Нові" value={counts.new ?? 0} testid="inq-stat-new" />
        <StatCard icon={Phone} label="В роботі" value={counts.in_progress ?? 0} />
        <StatCard icon={Mail} label="Зв'язалися" value={counts.contacted ?? 0} />
        <StatCard icon={Building2} label="Закриті" value={counts.closed ?? 0} />
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key || "all"}
              onClick={() => setTab(t.key)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${tab === t.key ? "bg-[#0E5E3A] text-white" : "bg-white text-slate-600 ring-1 ring-[hsl(var(--border))] hover:bg-slate-50"}`}
              data-testid={`inq-tab-${t.key || "all"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук за ім'ям, телефоном…" className="pl-9" data-testid="inq-search" />
        </div>
      </div>

      {loading ? (
        <TableSkeleton rows={6} />
      ) : items.length === 0 ? (
        <EmptyState icon={Inbox} title="Звернень немає" hint="Тут з'являться запити на дзвінок та звернення з публічних форм сайту." testid="inq-empty" />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white shadow-[0_1px_3px_rgba(11,26,20,0.06)]">
          <div className="divide-y divide-[hsl(var(--border))]">
            {items.map((it) => (
              <div key={it.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between" data-testid={`inq-row-${it.id}`}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{it.name}</span>
                    <span className="rounded-md bg-[hsl(var(--secondary))] px-2 py-0.5 text-[11px] font-medium text-slate-500">{TYPE_LABEL[it.type] || it.type}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                    <a href={`tel:${it.phone}`} className="inline-flex items-center gap-1 hover:text-[#0E5E3A]"><Phone className="h-3.5 w-3.5" />{it.phone}</a>
                    {it.email && <a href={`mailto:${it.email}`} className="inline-flex items-center gap-1 hover:text-[#0E5E3A]"><Mail className="h-3.5 w-3.5" />{it.email}</a>}
                    {it.company_name && <span className="inline-flex items-center gap-1"><Building2 className="h-3.5 w-3.5" />{it.company_name}</span>}
                  </div>
                  {it.message && <p className="mt-1.5 max-w-2xl text-sm text-slate-600">«{it.message}»</p>}
                  <div className="mt-1 text-xs text-slate-400">{(it.created_at || "").slice(0, 16).replace("T", " ")}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_CLS[it.status] || STATUS_CLS.closed}`}>{it.status_label}</span>
                  <select
                    value={it.status}
                    onChange={(e) => setStatus(it.id, e.target.value)}
                    className="rounded-lg border border-[hsl(var(--border))] bg-white px-2 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#0E5E3A]/20"
                    data-testid={`inq-status-${it.id}`}
                  >
                    <option value="new">Нове</option>
                    <option value="in_progress">В роботі</option>
                    <option value="contacted">Зв'язалися</option>
                    <option value="closed">Закрите</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
