/**
 * VersionHistoryPanel — Phase D1.
 *
 * Modal-side-panel: list of versions for a page. "Restore" clones an old
 * snapshot into a new draft; the backend enforces that current published
 * versions are never silently overwritten.
 */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { X, ArrowCounterClockwise, ClockCounterClockwise } from '@phosphor-icons/react';
import { contentApi } from './contentApi';
import { Button } from '../seo/_shared';

export default function VersionHistoryPanel({ pageId, onClose, onRestored }) {
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState([]);
  const [restoring, setRestoring] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await contentApi.listVersions(pageId);
        setVersions(r.items || []);
      } catch (e) {
        toast.error(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [pageId]);

  const doRestore = async (v) => {
    if (!window.confirm(`Відновити версію v${v.version}? Поточна версія опиниться в бекапі.`)) return;
    setRestoring(v.version);
    try {
      await contentApi.restoreVersion(pageId, v.version);
      toast.success(`Відновлено до v${v.version} (стало чернеткою)`);
      onRestored && onRestored();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRestoring(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-stretch justify-end" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[440px] h-full bg-white flex flex-col border-l border-[#E4E4E7]"
      >
        <header className="flex items-center gap-2 px-4 py-3 border-b border-[#E4E4E7]">
          <ClockCounterClockwise size={16} weight="bold" className="text-emerald-700" />
          <h3 className="flex-1 text-[14px] font-semibold">Історія версій</h3>
          <button onClick={onClose} className="h-8 w-8 rounded-md hover:bg-[#F4F4F5] inline-flex items-center justify-center" data-testid="history-close">
            <X size={14} weight="bold" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading ? (
            <div className="text-[12px] text-[#71717A]">Завантаження…</div>
          ) : versions.length === 0 ? (
            <div className="text-[12px] text-[#71717A]">Записів немає</div>
          ) : versions.map((v) => (
            <div key={v.id} className="rounded-lg border border-[#E4E4E7] p-3">
              <div className="flex items-center gap-2">
                <div className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 text-[11px] font-semibold">v{v.version}</div>
                <div className="text-[12px] text-[#3F3F46] flex-1 truncate">{v.action}</div>
              </div>
              <div className="text-[11px] text-[#71717A] mt-1">
                {v.created_at ? new Date(v.created_at).toLocaleString() : ''} · {v.actor_email || 'unknown'}
              </div>
              <div className="mt-2 flex items-center justify-end">
                <Button size="sm" variant="secondary" onClick={() => doRestore(v)} disabled={restoring === v.version} data-testid={`history-restore-v${v.version}`}>
                  <ArrowCounterClockwise size={11} weight="bold" />
                  {restoring === v.version ? '…' : 'Відновити'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
