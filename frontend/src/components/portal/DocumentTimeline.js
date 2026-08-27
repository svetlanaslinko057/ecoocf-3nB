import React, { useEffect, useState } from "react";
import { History, FileText, CheckCircle2, Send, Archive, Sparkles, FileBadge, Download, ExternalLink, Loader2 } from "lucide-react";
import { DocumentsAPI, FilesAPI, openStoredFile } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

// Lifecycle pill colors per state (uses ECO palette).
const PILL = {
  draft:     { cls: "bg-slate-100 text-slate-700 border-slate-200", icon: FileText, label: "Чернетка" },
  generated: { cls: "bg-sky-50 text-sky-700 border-sky-200", icon: Sparkles, label: "Згенеровано" },
  sent:      { cls: "bg-violet-50 text-violet-700 border-violet-200", icon: Send, label: "Надіслано" },
  signed:    { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2, label: "Підписано" },
  paid:      { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2, label: "Сплачено" },
  archived:  { cls: "bg-slate-100 text-slate-500 border-slate-200", icon: Archive, label: "Архів" },
};

function Pill({ status }) {
  const s = PILL[status] || PILL.draft;
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${s.cls}`}>
      <Icon className="h-3.5 w-3.5" /> {s.label}
    </span>
  );
}

function nextStates(states, current) {
  if (!states || !states.length) return [];
  const i = states.indexOf(current || "draft");
  const out = [];
  if (i >= 0 && i < states.length - 1) out.push(states[i + 1]);
  // archived terminal allowed from anywhere except itself
  if (current !== "archived" && states.includes("archived")) out.push("archived");
  return [...new Set(out)];
}

/**
 * DocumentTimeline
 *
 * Compact stripe widget for use inside operation drawers: shows current
 * lifecycle pill + version count + last 3 versions, plus a primary CTA
 * to advance the lifecycle.
 *
 * Props:
 *   entityType: 'contract' | 'act' | 'invoice' | 'pickup'
 *   entityId:   id of the underlying entity
 *   onChanged:  () => void  (called after a successful transition)
 *   compact:    boolean (drops version table in compact mode)
 */
export default function DocumentTimeline({ entityType, entityId, onChanged, compact = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  const load = async () => {
    if (!entityType || !entityId) return;
    setLoading(true);
    try {
      const r = await DocumentsAPI.get(entityType, entityId);
      setData(r);
    } catch (e) {
      setData({ lifecycle: { status: "draft", history: [], available: [] }, versions: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [entityType, entityId]);

  const versions = data?.versions || [];
  const lifecycle = data?.lifecycle || { status: "draft", history: [] };
  const states = lifecycle.available || [];
  const next = nextStates(states, lifecycle.status);

  const transitionTo = async (to) => {
    setBusy(to);
    try {
      const r = await DocumentsAPI.transition(entityType, entityId, to);
      toast.success(`Статус → ${PILL[to]?.label || to}`);
      setData((d) => ({ ...(d || {}), lifecycle: r.lifecycle }));
      onChanged && onChanged(r.lifecycle);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const missing = detail?.missing || (typeof detail === "object" ? detail.missing : null);
      if (missing && missing.length) toast.error(`Невистачає фото: ${missing.join(", ")}`);
      else toast.error(typeof detail === "string" ? detail : "Перехід неможливий");
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return <div className="h-20 animate-pulse rounded-xl bg-slate-100" data-testid="doc-timeline-loading" />;
  }

  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/30 p-3" data-testid={`doc-timeline-${entityType}`}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-emerald-700" />
          <span className="text-xs font-semibold text-emerald-900">Життєвий цикл документа:</span>
          <Pill status={lifecycle.status} />
        </div>
        <span className="text-xs text-slate-500">· версій: <b className="text-slate-700">{versions.length}</b></span>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          {next.map((s) => (
            <Button key={s} size="sm" variant="secondary" disabled={busy === s} onClick={() => transitionTo(s)} data-testid={`doc-timeline-to-${s}`}>
              {busy === s ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              → {PILL[s]?.label || s}
            </Button>
          ))}
        </div>
      </div>
      {!compact && versions.length > 0 && (
        <ol className="mt-3 grid gap-1.5">
          {versions.slice(0, 5).map((v) => (
            <li key={v.id} className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 text-xs ${v.status === "active" ? "border-emerald-200 bg-white" : "border-slate-200 bg-slate-50 text-slate-500"}`} data-testid={`doc-version-${v.version}`}>
              <div className="flex items-center gap-2">
                <span className={`inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-bold ${v.status === "active" ? "bg-emerald-500 text-white" : "bg-slate-300 text-white"}`}>v{v.version}</span>
                <FileBadge className="h-3.5 w-3.5 text-slate-400" />
                <span className="max-w-[260px] truncate">{v.filename || v.title}</span>
                {v.status !== "active" && <span className="text-[10px] uppercase tracking-wider text-slate-400">замінено</span>}
              </div>
              <div className="flex items-center gap-1">
                <button className="rounded-md p-1 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700" title="Відкрити" onClick={() => openStoredFile(v.id)} data-testid={`doc-version-open-${v.version}`}>
                  <ExternalLink className="h-3.5 w-3.5" />
                </button>
                <button className="rounded-md p-1 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700" title="Скачати" onClick={() => openStoredFile(v.id, { download: true, filename: v.filename })}>
                  <Download className="h-3.5 w-3.5" />
                </button>
              </div>
            </li>
          ))}
          {versions.length > 5 && (
            <li className="text-center text-xs text-slate-400">+{versions.length - 5} старіших версій</li>
          )}
        </ol>
      )}
    </div>
  );
}
