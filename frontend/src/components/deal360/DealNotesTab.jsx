import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { NotePencil, PaperPlaneRight } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const DealNotesTab = ({ dealId, timeline = [], onChange }) => {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const notes = (timeline || []).filter((e) => e.event_type === 'note_added');

  const send = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/notes`, { text: t });
      setText('');
      toast.success('Note added');
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3" data-testid="deal-notes-tab">
      <form onSubmit={send} className="bg-white border border-[#E4E4E7] rounded-2xl p-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Add a note for the team (visible in timeline)…"
          rows={3}
          className="w-full text-sm px-2 py-1 outline-none resize-none"
          data-testid="deal-note-input"
        />
        <div className="flex items-center justify-end">
          <button
            type="submit" disabled={busy || !text.trim()}
            className="inline-flex items-center gap-1 bg-[#18181B] text-white text-sm font-semibold rounded-lg px-3 py-1.5 disabled:opacity-50"
            data-testid="deal-note-submit"
          >
            <PaperPlaneRight size={14} weight="bold" /> Send
          </button>
        </div>
      </form>

      {notes.length === 0 ? (
        <div className="bg-white border border-dashed border-[#E4E4E7] rounded-2xl p-8 text-center">
          <NotePencil size={28} className="mx-auto text-[#A1A1AA] mb-2" />
          <div className="text-[#71717A]">No notes yet</div>
        </div>
      ) : (
        <ul className="space-y-2">
          {notes.map((n, i) => (
            <li key={n.id || i} className="bg-white border border-[#E4E4E7] rounded-2xl p-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-wider font-bold text-[#52525B]">Note</span>
                <span className="text-[11px] text-[#A1A1AA]">{n.at ? new Date(n.at).toLocaleString() : ''}</span>
              </div>
              <div className="text-sm text-[#18181B] mt-1 whitespace-pre-wrap">{n.message}</div>
              {n.actor?.email ? (
                <div className="text-[11px] text-[#71717A] mt-1">— {n.actor.email}</div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default DealNotesTab;
