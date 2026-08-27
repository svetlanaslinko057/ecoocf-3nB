/**
 * Customer360 — CommentsTab (Sprint 4)
 * --------------------------------------
 * Staff-facing notes attached to a customer.
 *  - Manager / Team Lead / Admin can post.
 *  - Only author or admin can edit / delete.
 *  - Team Lead / Admin can pin (pinned float to the top).
 *  - Edits show the "edited" badge; soft-deletes are hidden by default.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ChatCircle,
  PushPin,
  PushPinSlash,
  PencilSimple,
  Trash,
  Check,
  X,
  PaperPlaneRight,
} from '@phosphor-icons/react';
import { useAuth } from '../../App';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const roleBadge = (role) => {
  const r = (role || '').toLowerCase();
  const map = {
    manager:      'bg-indigo-100 text-indigo-700 border-indigo-200',
    team_lead:    'bg-amber-100 text-amber-700 border-amber-200',
    admin:        'bg-emerald-100 text-emerald-700 border-emerald-200',
    master_admin: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    owner:        'bg-rose-100 text-rose-700 border-rose-200',
  };
  const label = r.replace(/_/g, ' ');
  return <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-bold border ${map[r] || 'bg-zinc-100 text-zinc-600 border-zinc-200'}`}>{label}</span>;
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(); } catch { return ''; }
};

const CommentsTab = ({ customerId }) => {
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canPin = ['team_lead', 'admin', 'master_admin', 'owner'].includes(role);
  const isPriv = ['admin', 'master_admin', 'owner'].includes(role);
  const myId = user?.id;

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editBody, setEditBody] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/customers/${customerId}/comments`, { headers: authHeaders() });
      setItems(res.data?.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load comments');
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/comments`, { headers: authHeaders() });
        if (!cancelled) setItems(res.data?.items || []);
      } catch (e) {
        if (!cancelled) toast.error(e.response?.data?.detail || 'Failed to load comments');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const send = async () => {
    const body = text.trim();
    if (!body) return;
    setSending(true);
    try {
      await axios.post(
        `${API_URL}/api/customers/${customerId}/comments`,
        { body },
        { headers: authHeaders() },
      );
      setText('');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to add comment');
    } finally {
      setSending(false);
    }
  };

  const togglePin = async (c) => {
    try {
      await axios.patch(
        `${API_URL}/api/customers/${customerId}/comments/${c.id}`,
        { pinned: !c.pinned },
        { headers: authHeaders() },
      );
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to toggle pin');
    }
  };

  const saveEdit = async (c) => {
    const body = (editBody || '').trim();
    if (!body) return;
    try {
      await axios.patch(
        `${API_URL}/api/customers/${customerId}/comments/${c.id}`,
        { body },
        { headers: authHeaders() },
      );
      setEditing(null);
      setEditBody('');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to edit');
    }
  };

  const remove = async (c) => {
    if (!window.confirm('Видалити коментар?')) return;
    try {
      await axios.delete(`${API_URL}/api/customers/${customerId}/comments/${c.id}`, { headers: authHeaders() });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-32" data-testid="comments-loading">
      <div className="animate-spin w-7 h-7 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
    </div>;
  }

  return (
    <div className="space-y-4" data-testid="customer360-comments-tab">
      {/* Composer */}
      <div className="section-card">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 shrink-0 rounded-full bg-[#18181B] text-white text-sm flex items-center justify-center font-semibold">
            {(user?.name || user?.email || '?').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <textarea
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') send(); }}
              placeholder="Залиште коментар (Cmd/Ctrl+Enter — надіслати)…"
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#18181B] focus:ring-2 focus:ring-zinc-200/50"
              data-testid="comment-textarea"
            />
            <div className="mt-2 flex items-center justify-between">
              <p className="text-[11px] text-zinc-400">{text.length}/8000</p>
              <button
                onClick={send}
                disabled={!text.trim() || sending}
                className="inline-flex items-center gap-2 px-4 py-1.5 bg-[#18181B] text-white text-sm rounded-lg hover:bg-[#27272A] disabled:opacity-50"
                data-testid="comment-send-btn"
              >
                <PaperPlaneRight size={14} weight="bold" /> Надіслати
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* List */}
      {items.length === 0 && (
        <div className="section-card text-center py-12" data-testid="comments-empty">
          <ChatCircle size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">Поки немає коментарів. Станьте першим.</p>
        </div>
      )}
      <div className="space-y-3">
        {items.map((c) => {
          const mine = c.author_id && c.author_id === myId;
          const canEdit = mine || isPriv;
          const canDelete = mine || isPriv;
          const isEditing = editing === c.id;
          return (
            <div key={c.id} className={`section-card ${c.pinned ? 'border-2 border-amber-300 bg-amber-50/40' : ''}`} data-testid={`comment-row-${c.id}`}>
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 shrink-0 rounded-full bg-zinc-200 text-zinc-700 text-sm flex items-center justify-center font-semibold">
                  {(c.author_name || c.author_email || '?').charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-[#18181B] text-sm">{c.author_name || c.author_email || '—'}</span>
                    {roleBadge(c.author_role)}
                    {c.pinned && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200 font-medium"><PushPin size={10} weight="fill" /> Pinned</span>}
                    {c.edited && <span className="text-[10px] text-zinc-400 italic">edited</span>}
                    <span className="text-[11px] text-zinc-400 ml-auto">{fmtDate(c.created_at)}</span>
                  </div>
                  {isEditing ? (
                    <div className="mt-2">
                      <textarea
                        rows={2}
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                        className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm"
                        autoFocus
                      />
                      <div className="mt-2 flex justify-end gap-2">
                        <button onClick={() => { setEditing(null); setEditBody(''); }} className="px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-100 rounded"><X size={12} className="inline" /> Скасувати</button>
                        <button onClick={() => saveEdit(c)} className="px-3 py-1 text-xs bg-[#18181B] text-white rounded hover:bg-[#27272A]"><Check size={12} className="inline mr-1" />Зберегти</button>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm text-[#3F3F46] whitespace-pre-wrap break-words">{c.body}</p>
                  )}
                </div>
                {!isEditing && (
                  <div className="shrink-0 flex items-center gap-1">
                    {canPin && (
                      <button onClick={() => togglePin(c)} className="p-1.5 hover:bg-zinc-100 rounded-md" title={c.pinned ? 'Unpin' : 'Pin'} data-testid={`comment-pin-${c.id}`}>
                        {c.pinned ? <PushPinSlash size={14} className="text-amber-600" /> : <PushPin size={14} className="text-zinc-400" />}
                      </button>
                    )}
                    {canEdit && (
                      <button onClick={() => { setEditing(c.id); setEditBody(c.body); }} className="p-1.5 hover:bg-zinc-100 rounded-md" title="Edit">
                        <PencilSimple size={14} className="text-zinc-400" />
                      </button>
                    )}
                    {canDelete && (
                      <button onClick={() => remove(c)} className="p-1.5 hover:bg-red-50 rounded-md" title="Delete">
                        <Trash size={14} className="text-red-400" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CommentsTab;
