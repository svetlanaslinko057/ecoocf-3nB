import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { NotePencil, Trash, Paperclip } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const formatWhen = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch { return String(iso); }
};

const LeadNotesPanel = ({ leadId, onAfterChange }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/leads/${leadId}/notes`);
      setNotes(r.data?.items || []);
    } catch (e) {
      toast.error('Failed to load notes');
    } finally { setLoading(false); }
  };

  useEffect(() => { if (leadId) load(); }, [leadId]);

  const submit = async (e) => {
    e.preventDefault();
    const value = (text || '').trim();
    if (!value) return;
    setSaving(true);
    try {
      const r = await axios.post(`${API_URL}/api/leads/${leadId}/notes`, { text: value });
      setNotes((prev) => [r.data.note, ...prev]);
      setText('');
      onAfterChange && onAfterChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setSaving(false); }
  };

  const del = async (id) => {
    if (!window.confirm('Delete this note?')) return;
    try {
      await axios.delete(`${API_URL}/api/leads/${leadId}/notes/${id}`);
      setNotes((prev) => prev.filter(n => n.id !== id));
      onAfterChange && onAfterChange();
    } catch (err) { toast.error('Failed'); }
  };

  return (
    <div data-testid="lead-notes-panel">
      <form onSubmit={submit} className="bg-white border border-[#E4E4E7] rounded-2xl p-3 mb-4">
        <div className="flex items-start gap-2">
          <NotePencil size={16} className="text-[#71717A] mt-2 shrink-0" />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Напишіть примітку…"
            rows={2}
            className="flex-1 text-[13px] outline-none resize-none"
            data-testid="lead-note-input"
          />
        </div>
        <div className="flex items-center justify-end mt-2 gap-2">
          <button type="submit" disabled={saving || !text.trim()} className="px-3 py-1.5 text-[12px] bg-[#18181B] hover:bg-black disabled:opacity-40 text-white rounded-lg font-semibold" data-testid="lead-note-submit">
            {saving ? 'Saving…' : 'Додати'}
          </button>
        </div>
      </form>

      {loading ? (
        <div className="text-[12px] text-[#71717A] text-center py-6">Loading…</div>
      ) : notes.length === 0 ? (
        <div className="text-[12px] text-[#A1A1AA] italic text-center py-6">Поки немає приміток</div>
      ) : (
        <ul className="space-y-2">
          {notes.map(n => (
            <li key={n.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-3 group" data-testid={`lead-note-${n.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">
                  {n.created_by_name || n.created_by || 'unknown'} · {formatWhen(n.created_at)}
                </div>
                <button onClick={() => del(n.id)} className="opacity-0 group-hover:opacity-100 p-1 text-[#DC2626] hover:bg-[#FEE2E2] rounded transition-opacity" data-testid={`lead-note-del-${n.id}`}>
                  <Trash size={12} />
                </button>
              </div>
              <div className="text-[13px] text-[#18181B] mt-1 whitespace-pre-wrap">{n.text}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default LeadNotesPanel;
