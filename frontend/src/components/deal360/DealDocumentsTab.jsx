import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { File as FileIcon, Plus, Trash, ArrowSquareOut } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const kindLabel = (k) => ({
  invoice:   'Invoice',
  contract:  'Contract',
  receipt:   'Receipt',
  passport:  'Passport',
  title:     'Title',
  shipping:  'Shipping',
  other:     'Other',
}[(k || '').toLowerCase()] || 'Other');

const DealDocumentsTab = ({ dealId, documents = [], onChange }) => {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: '', url: '', kind: 'other' });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.url.trim()) { toast.error('URL is required'); return; }
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/documents`, {
        name: form.name.trim() || form.url.split('/').pop() || 'Document',
        url:  form.url.trim(),
        kind: form.kind,
      });
      toast.success('Document added');
      setForm({ name: '', url: '', kind: 'other' });
      setAdding(false);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add');
    } finally { setBusy(false); }
  };

  const remove = async (docId) => {
    if (!window.confirm('Remove this document?')) return;
    try {
      await axios.delete(`${API_URL}/api/deals/${dealId}/documents/${docId}`);
      toast.success('Removed');
      onChange?.();
    } catch { toast.error('Failed'); }
  };

  return (
    <div className="space-y-3" data-testid="deal-documents-tab">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{documents.length} document(s)</div>
        <button
          onClick={() => setAdding((v) => !v)}
          className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#4F46E5] hover:underline"
          data-testid="deal-add-document-btn"
        >
          <Plus size={14} /> Add document
        </button>
      </div>

      {adding ? (
        <form onSubmit={submit} className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-3 space-y-2" data-testid="deal-add-document-form">
          <input
            type="text" placeholder="Name (optional)"
            value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm"
          />
          <input
            type="url" required placeholder="https://..."
            value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
            className="w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm"
          />
          <div className="flex items-center gap-2">
            <select
              value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}
              className="px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm bg-white"
            >
              {['invoice', 'contract', 'receipt', 'passport', 'title', 'shipping', 'other'].map((k) => (
                <option key={k} value={k}>{kindLabel(k)}</option>
              ))}
            </select>
            <button
              type="submit" disabled={busy}
              className="ml-auto bg-[#18181B] text-white text-sm font-semibold rounded-lg px-3 py-2 disabled:opacity-50"
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button type="button" onClick={() => setAdding(false)} className="text-sm text-[#71717A] hover:underline">
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {documents.length === 0 ? (
        <div className="bg-white border border-dashed border-[#E4E4E7] rounded-2xl p-8 text-center" data-testid="deal-documents-empty">
          <FileIcon size={28} className="mx-auto text-[#A1A1AA] mb-2" />
          <div className="text-[#71717A]">No documents attached yet</div>
        </div>
      ) : (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl divide-y divide-[#F4F4F5]">
          {documents.map((d, i) => (
            <div key={d.id || i} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-[#F4F4F5] flex items-center justify-center text-[#52525B]">
                  <FileIcon size={18} />
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-[#18181B] truncate">{d.name}</div>
                  <div className="text-[12px] text-[#71717A]">{kindLabel(d.kind)} · {d.uploaded_at ? new Date(d.uploaded_at).toLocaleString() : ''}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {d.url ? (
                  <a href={d.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#4F46E5] hover:underline">
                    <ArrowSquareOut size={12} /> Open
                  </a>
                ) : null}
                {d.source === 'deal_documents' && d.id ? (
                  <button onClick={() => remove(d.id)} className="text-[#A1A1AA] hover:text-red-600" title="Remove">
                    <Trash size={14} />
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DealDocumentsTab;
