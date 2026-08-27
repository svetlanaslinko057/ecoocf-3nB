import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Truck, BadgeCheck, MoreHorizontal } from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import {
  CONTRACT_ORDER, CONTRACT_LABELS, PICKUP_ORDER, PICKUP_LABELS,
  ACT_ORDER, ACT_LABELS, fmtDate, fmtDateTime, itemsSummary,
} from "@/lib/portalMeta";
import { PageHeader, StatusBadge, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { OperationDetailDrawer } from "@/components/portal/OperationDetailDrawer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

function StatusChanger({ value, order, labels, onChange, testid }) {
  const [busy, setBusy] = useState(false);
  const handle = async (v) => {
    setBusy(true);
    try { await onChange(v); toast.success(`Статус → ${labels[v]}`); }
    catch { toast.error("Не вдалося змінити статус"); }
    finally { setBusy(false); }
  };
  return (
    <Select value={value} onValueChange={handle} disabled={busy}>
      <SelectTrigger className="h-9 w-[180px]" data-testid={testid}><SelectValue /></SelectTrigger>
      <SelectContent>{order.map((s) => <SelectItem key={s} value={s}>{labels[s]}</SelectItem>)}</SelectContent>
    </Select>
  );
}

function OpsTable({ loading, rows, columns, emptyIcon, emptyTitle, emptyHint, rowTestid, onRowClick }) {
  if (loading) return <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={5} /></div>;
  if (!rows.length) return <EmptyState icon={emptyIcon} title={emptyTitle} hint={emptyHint} />;
  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
      <Table>
        <TableHeader><TableRow>{columns.map((c) => <TableHead key={c.key} className={c.className}>{c.label}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id} data-testid={rowTestid} className={onRowClick ? "cursor-pointer hover:bg-[hsl(var(--secondary))]" : ""}
              onClick={(e) => { if (onRowClick && !e.target.closest("[data-no-row-click]")) onRowClick(r); }}>
              {columns.map((c) => <TableCell key={c.key} className={c.cellClassName}>{c.render(r)}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function Operations() {
  useSeo("Операції", "Договори, вивози та акти утилізації.");
  const navigate = useNavigate();
  const [contracts, setContracts] = useState([]);
  const [pickups, setPickups] = useState([]);
  const [acts, setActs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, p, a] = await Promise.all([
        PortalAPI.contracts({ limit: 500 }),
        PortalAPI.pickups({ limit: 500 }),
        PortalAPI.acts({ limit: 500 }),
      ]);
      setContracts(c.items || []); setPickups(p.items || []); setActs(a.items || []);
    } catch { /* keep empty */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patchLocal = (setter) => (id, status) => setter((rows) => rows.map((r) => (r.id === id ? { ...r, status } : r)));
  const [drawer, setDrawer] = useState({ open: false, kind: "contract", id: null });
  const openDrawer = (kind) => (row) => setDrawer({ open: true, kind, id: row.id });
  const onDrawerSaved = (fresh) => {
    if (!fresh) return load();
    if (drawer.kind === "contract") setContracts((p) => p.map((r) => r.id === fresh.id ? fresh : r));
    if (drawer.kind === "pickup") setPickups((p) => p.map((r) => r.id === fresh.id ? fresh : r));
    if (drawer.kind === "act") setActs((p) => p.map((r) => r.id === fresh.id ? fresh : r));
  };

  return (
    <div data-testid="portal-operations">
      <PageHeader title="Операції" subtitle="Договори, замовлення на вивіз та акти утилізації" />

      <Tabs defaultValue="contracts" className="w-full">
        <TabsList>
          <TabsTrigger value="contracts" data-testid="ops-tab-contracts" className="gap-1.5"><FileText className="h-4 w-4" /> Договори <span className="ml-1 text-xs text-slate-400">{contracts.length}</span></TabsTrigger>
          <TabsTrigger value="pickups" data-testid="ops-tab-pickups" className="gap-1.5"><Truck className="h-4 w-4" /> Вивози <span className="ml-1 text-xs text-slate-400">{pickups.length}</span></TabsTrigger>
          <TabsTrigger value="acts" data-testid="ops-tab-acts" className="gap-1.5"><BadgeCheck className="h-4 w-4" /> Акти <span className="ml-1 text-xs text-slate-400">{acts.length}</span></TabsTrigger>
        </TabsList>

        <TabsContent value="contracts" className="mt-4">
          <OpsTable loading={loading} rows={contracts} rowTestid="contract-row" onRowClick={openDrawer("contract")} emptyIcon={FileText} emptyTitle="Договорів немає" emptyHint="Згенеруйте договір із заявки у воронці."
            columns={[
              { key: "number", label: "Номер", render: (r) => <span className="font-mono text-sm font-medium text-slate-900">{r.number}</span> },
              { key: "items", label: "Відходи", render: (r) => <span className="font-mono text-xs text-slate-500">{itemsSummary(r.items)}</span> },
              { key: "amount", label: "Сума", render: (r) => <span className="text-slate-500">{(r.financials?.contract_value ?? r.amount) ? `${(r.financials?.contract_value ?? r.amount)} ${r.currency || "UAH"}` : "—"}</span> },
              { key: "signed", label: "Підписано", render: (r) => <span className="text-slate-500 text-xs">{r.signed_at ? fmtDate(r.signed_at) : "—"}</span> },
              { key: "created", label: "Створено", render: (r) => <span className="text-slate-500">{fmtDate(r.created_at)}</span> },
              { key: "status", label: "Статус", render: (r) => <StatusBadge status={r.status} /> },
              { key: "exec", label: "Виконання", render: (r) => <div data-no-row-click><Button size="sm" variant="outline" data-testid="contract-exec-btn" onClick={() => navigate(`/app/operations/contracts/${r.id}`)}>Графік / Фінанси</Button></div> },
              { key: "action", label: "Змінити", render: (r) => <div data-no-row-click><StatusChanger value={r.status} order={CONTRACT_ORDER} labels={CONTRACT_LABELS} testid="contract-status-select" onChange={async (v) => { await PortalAPI.setContractStatus(r.id, v); patchLocal(setContracts)(r.id, v); }} /></div> },
            ]}
          />
        </TabsContent>

        <TabsContent value="pickups" className="mt-4">
          <OpsTable loading={loading} rows={pickups} rowTestid="pickup-row" onRowClick={openDrawer("pickup")} emptyIcon={Truck} emptyTitle="Вивозів немає" emptyHint="Замовлення на вивіз генеруються із заявок."
            columns={[
              { key: "number", label: "Номер", render: (r) => <span className="font-mono text-sm font-medium text-slate-900">{r.number}</span> },
              { key: "items", label: "Відходи", render: (r) => <span className="font-mono text-xs text-slate-500">{itemsSummary(r.items)}</span> },
              { key: "scheduled", label: "Заплановано", render: (r) => <span className="text-slate-500">{fmtDateTime(r.scheduled_at)}</span> },
              { key: "driver", label: "Водій", render: (r) => <span className="text-slate-500 text-xs">{r.driver?.name || "—"}</span> },
              { key: "weight", label: "Вага", render: (r) => <span className="text-slate-500 font-mono text-xs">{r.weight_kg ? `${r.weight_kg} кг` : "—"}</span> },
              { key: "status", label: "Статус", render: (r) => <StatusBadge status={r.status} /> },
              { key: "action", label: "Змінити", render: (r) => <div data-no-row-click><StatusChanger value={r.status} order={PICKUP_ORDER} labels={PICKUP_LABELS} testid="pickup-status-select" onChange={async (v) => { await PortalAPI.setPickupStatus(r.id, v); patchLocal(setPickups)(r.id, v); }} /></div> },
            ]}
          />
        </TabsContent>

        <TabsContent value="acts" className="mt-4">
          <OpsTable loading={loading} rows={acts} rowTestid="act-row" onRowClick={openDrawer("act")} emptyIcon={BadgeCheck} emptyTitle="Актів немає" emptyHint="Акти утилізації формуються після вивозу."
            columns={[
              { key: "number", label: "Номер", render: (r) => <span className="font-mono text-sm font-medium text-slate-900">{r.number}</span> },
              { key: "items", label: "Відходи", render: (r) => <span className="font-mono text-xs text-slate-500">{itemsSummary(r.items)}</span> },
              { key: "weight", label: "Факт. вага", render: (r) => <span className="text-slate-500 font-mono">{r.total_weight_kg ? `${r.total_weight_kg} кг` : "—"}</span> },
              { key: "method", label: "Метод", render: (r) => <span className="text-slate-500 text-xs">{r.utilization_method || "—"}</span> },
              { key: "act_date", label: "Дата акту", render: (r) => <span className="text-slate-500">{fmtDate(r.act_date || r.signed_at || r.created_at)}</span> },
              { key: "status", label: "Статус", render: (r) => <StatusBadge status={r.status} /> },
              { key: "action", label: "Змінити", render: (r) => <div data-no-row-click><StatusChanger value={r.status} order={ACT_ORDER} labels={ACT_LABELS} testid="act-status-select" onChange={async (v) => { await PortalAPI.setActStatus(r.id, v); patchLocal(setActs)(r.id, v); }} /></div> },
            ]}
          />
        </TabsContent>
      </Tabs>

      <OperationDetailDrawer open={drawer.open} onOpenChange={(v) => setDrawer((p) => ({ ...p, open: v }))} kind={drawer.kind} id={drawer.id} onSaved={onDrawerSaved} />
    </div>
  );
}
