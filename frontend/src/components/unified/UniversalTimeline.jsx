// UniversalTimeline — Phase D1.5 Slice 2.
// One component that shows the full history of ANY entity: comments, files
// (attachments), audit changes, status and events — in a single timeline.
// Includes a comment composer and an attach-file control. Reusable across the
// admin (Company360, Deal360, Content editor, etc.).
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  MessageSquare, Paperclip, History, Activity, Send, Loader2, Trash2, Download,
} from "lucide-react";
import { UnifiedAPI } from "@/lib/api";
import LifecycleBadge from "@/components/unified/LifecycleBadge";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const mediaSrc = (url) => (url && url.startsWith("http") ? url : `${BACKEND_URL}${url || ""}`);

const KIND_META = {
  comment: { icon: MessageSquare, color: "text-blue-600", ring: "bg-blue-50" },
  attachment: { icon: Paperclip, color: "text-violet-600", ring: "bg-violet-50" },
  audit: { icon: History, color: "text-amber-600", ring: "bg-amber-50" },
  event: { icon: Activity, color: "text-slate-500", ring: "bg-slate-50" },
};

const fmt = (ts) => {
  if (!ts) return "";
  try { return new Date(ts).toLocaleString("uk-UA", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return ""; }
};

const TABS = [
  { key: "all", label: "Усе" },
  { key: "comment", label: "Коментарі" },
  { key: "attachment", label: "Файли" },
  { key: "audit", label: "Зміни" },
];

export default function UniversalTimeline({ entityType, entityId, title = "Історія" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    if (!entityType || !entityId) return;
    try {
      const d = await UnifiedAPI.timeline(entityType, entityId);
      setData(d);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, [entityType, entityId]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  const submitComment = async () => {
    const t = text.trim();
    if (!t) return;
    setSending(true);
    try {
      await UnifiedAPI.addComment({ entity_type: entityType, entity_id: entityId, text: t });
      setText("");
      await load();
    } catch { /* ignore */ } finally { setSending(false); }
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await UnifiedAPI.uploadAttachment(entityType, entityId, fd);
      await load();
    } catch { /* ignore */ } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeAttachment = async (id) => {
    await UnifiedAPI.deleteAttachment(id).catch(() => {});
    await load();
  };
  const removeComment = async (id) => {
    await UnifiedAPI.deleteComment(id).catch(() => {});
    await load();
  };

  const events = (data?.events || []).filter((e) => tab === "all" || e.kind === tab);

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm" data-testid="universal-timeline">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <History className="h-4 w-4 text-[#0E5E3A]" /> {title}
        </h3>
        {data?.lifecycle && <LifecycleBadge lifecycle={data.lifecycle} showStepper />}
      </div>

      {/* Composer */}
      <div className="mb-4 rounded-xl border border-slate-200 p-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitComment(); }}
          rows={2}
          placeholder="Додати коментар… (Ctrl+Enter)"
          className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none"
          data-testid="timeline-comment-input"
        />
        <div className="flex items-center justify-between border-t border-slate-100 px-1 pt-2">
          <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading}
                  className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-50 disabled:opacity-60"
                  data-testid="timeline-attach-btn">
            {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Paperclip className="h-3.5 w-3.5" />} Прикріпити файл
          </button>
          <input ref={fileRef} type="file" className="hidden" onChange={onUpload} data-testid="timeline-file-input" />
          <button type="button" onClick={submitComment} disabled={sending || !text.trim()}
                  className="flex items-center gap-1.5 rounded-lg bg-[#0E5E3A] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0b4d30] disabled:opacity-50"
                  data-testid="timeline-comment-submit">
            {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />} Надіслати
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-3 flex gap-1.5">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${tab === t.key ? "bg-[#0E5E3A] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            data-testid={`timeline-tab-${t.key}`}>
            {t.label}
            {t.key === "comment" && data?.counts?.comments ? ` (${data.counts.comments})` : ""}
            {t.key === "attachment" && data?.counts?.attachments ? ` (${data.counts.attachments})` : ""}
            {t.key === "audit" && data?.counts?.audit ? ` (${data.counts.audit})` : ""}
          </button>
        ))}
      </div>

      {/* Events */}
      {loading ? (
        <div className="flex h-24 items-center justify-center text-slate-400"><Loader2 className="h-5 w-5 animate-spin" /></div>
      ) : events.length === 0 ? (
        <div className="py-8 text-center text-sm text-slate-400">Поки немає записів</div>
      ) : (
        <ul className="space-y-3" data-testid="timeline-events">
          {events.map((ev) => {
            const meta = KIND_META[ev.kind] || KIND_META.event;
            const Icon = meta.icon;
            return (
              <li key={`${ev.kind}-${ev.id}`} className="flex gap-3" data-testid="timeline-event">
                <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${meta.ring}`}>
                  <Icon className={`h-4 w-4 ${meta.color}`} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-slate-700">{ev.actor?.name || "Система"}</span>
                    <span className="text-[11px] text-slate-400">{fmt(ev.ts)}</span>
                  </div>
                  {ev.kind === "comment" && (
                    <div className="group flex items-start justify-between gap-2">
                      <p className="whitespace-pre-wrap text-sm text-slate-600">{ev.text}</p>
                      <button type="button" onClick={() => removeComment(ev.id)} className="text-slate-300 opacity-0 transition hover:text-rose-500 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  )}
                  {ev.kind === "attachment" && (
                    <div className="group flex items-center justify-between gap-2">
                      <a href={mediaSrc(ev.url)} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-sm text-[#0E5E3A] hover:underline">
                        <Download className="h-3.5 w-3.5" /> {ev.title}
                      </a>
                      <button type="button" onClick={() => removeAttachment(ev.id)} className="text-slate-300 opacity-0 transition hover:text-rose-500 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  )}
                  {ev.kind === "audit" && (
                    <p className="text-sm text-slate-500">Зміна: <span className="font-medium">{ev.action}</span></p>
                  )}
                  {ev.kind === "event" && (
                    <p className="text-sm text-slate-500">{ev.title || ev.action}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
