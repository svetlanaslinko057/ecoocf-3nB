/**
 * AdminDocumentTemplatesPage — Mini Sprint Contracts Final
 * --------------------------------------------------------
 * Master-admin editor for the document templates that drive the PDF
 * Engine (contract / invoice / acceptance act / etc).
 *
 * Lists templates per type+language, lets admin edit:
 *   - name
 *   - html (Jinja2 template body + inline CSS; raw textarea editor for now)
 *   - is_active
 * Provides a "Seed defaults" button when the collection is empty.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  FilePdf,
  Plus,
  FloppyDisk,
  Trash,
  ArrowsClockwise,
  CheckCircle,
  XCircle,
} from '@phosphor-icons/react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const TYPE_OPTIONS = [
  { value: 'contract',       label: 'Contract' },
  { value: 'invoice',        label: 'Invoice (PDF)' },
  { value: 'acceptance_act', label: 'Acceptance Act' },
];
const LANG_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'uk', label: 'Українська' },
  { value: 'bg', label: 'Български' },
];

const AdminDocumentTemplatesPage = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('');
  const [filterLang, setFilterLang] = useState('');
  const [selected, setSelected] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterType) params.set('type', filterType);
      if (filterLang) params.set('language', filterLang);
      const res = await axios.get(`${API_URL}/api/admin/document-templates?${params}`, { headers: authHeaders() });
      setItems(res.data?.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, [filterType, filterLang]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const params = new URLSearchParams();
        if (filterType) params.set('type', filterType);
        if (filterLang) params.set('language', filterLang);
        const res = await axios.get(`${API_URL}/api/admin/document-templates?${params}`, { headers: authHeaders() });
        if (!cancelled) setItems(res.data?.items || []);
      } catch (e) {
        if (!cancelled) toast.error(e.response?.data?.detail || 'Failed to load templates');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [filterType, filterLang]);

  const seedDefaults = async () => {
    if (!window.confirm('Створити шаблони за замовчуванням? Існуючі не будуть перезаписані.')) return;
    try {
      await axios.post(`${API_URL}/api/admin/document-templates/seed-defaults`, {}, { headers: authHeaders() });
      toast.success('Defaults seeded');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const patch = {
        name: selected.name,
        html: selected.html,
        is_active: selected.is_active,
      };
      const res = await axios.patch(
        `${API_URL}/api/admin/document-templates/${selected.id}`,
        patch,
        { headers: authHeaders() },
      );
      toast.success('Template saved');
      setSelected(res.data?.template);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (tpl) => {
    if (!window.confirm(`Видалити шаблон «${tpl.name}»?`)) return;
    try {
      await axios.delete(`${API_URL}/api/admin/document-templates/${tpl.id}`, { headers: authHeaders() });
      toast.success('Deleted');
      if (selected?.id === tpl.id) setSelected(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const grouped = useMemo(() => {
    const m = new Map();
    items.forEach((tpl) => {
      const k = tpl.type || 'other';
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(tpl);
    });
    return Array.from(m.entries());
  }, [items]);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" /></div>;
  }

  return (
    <div className="space-y-5" data-testid="admin-doctpl-page">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Document Templates</h1>
          <p className="text-sm text-zinc-500">PDF шаблоны для договоров, инвойсов и актов приёма. Используют Jinja2 + HTML/CSS.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm">
            <option value="">All types</option>
            {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={filterLang} onChange={(e) => setFilterLang(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm">
            <option value="">All languages</option>
            {LANG_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button onClick={seedDefaults} className="inline-flex items-center gap-1 px-3 py-1.5 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50">
            <ArrowsClockwise size={14} /> Seed defaults
          </button>
          <button onClick={() => setShowNew(true)} className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#18181B] text-white rounded-lg text-sm hover:bg-[#27272A]" data-testid="doctpl-new-btn">
            <Plus size={14} /> New template
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
        {/* List sidebar */}
        <div className="section-card max-h-[80vh] overflow-y-auto">
          {items.length === 0 ? (
            <p className="text-zinc-500 text-center py-8 text-sm">Нет шаблонов. Нажмите «Seed defaults».</p>
          ) : grouped.map(([type, list]) => (
            <div key={type} className="mb-3">
              <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-400 mb-1.5">{type.replace(/_/g, ' ')}</p>
              <ul className="space-y-1">
                {list.map((tpl) => (
                  <li key={tpl.id}>
                    <button
                      onClick={() => setSelected(tpl)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors ${selected?.id === tpl.id ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white border-zinc-200 hover:bg-zinc-50'}`}
                      data-testid={`doctpl-item-${tpl.id}`}
                    >
                      <div className="flex items-center gap-2">
                        <FilePdf size={14} className={selected?.id === tpl.id ? 'text-white' : 'text-rose-500'} />
                        <span className="flex-1 truncate font-medium">{tpl.name}</span>
                        <span className={`text-[10px] uppercase tracking-wider font-mono ${selected?.id === tpl.id ? 'text-zinc-300' : 'text-zinc-500'}`}>{tpl.language}</span>
                        {tpl.is_active ? <CheckCircle size={12} weight="fill" className="text-emerald-400" /> : <XCircle size={12} className="text-zinc-400" />}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Editor */}
        <div className="section-card">
          {!selected ? (
            <div className="text-center py-16 text-zinc-400">
              <FilePdf size={36} className="mx-auto mb-2" />
              <p>Выберите шаблон слева</p>
            </div>
          ) : (
            <div data-testid="doctpl-editor">
              <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                <div>
                  <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-400">{selected.type} · {selected.language}</p>
                  <input
                    value={selected.name || ''}
                    onChange={(e) => setSelected({ ...selected, name: e.target.value })}
                    className="text-lg font-semibold text-zinc-900 border-b border-transparent hover:border-zinc-200 focus:border-zinc-900 focus:outline-none w-full max-w-md"
                    data-testid="doctpl-name"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="inline-flex items-center gap-2 text-sm text-zinc-700 select-none">
                    <input type="checkbox" checked={!!selected.is_active} onChange={(e) => setSelected({ ...selected, is_active: e.target.checked })} className="accent-[#18181B]" />
                    Active
                  </label>
                  <button onClick={() => remove(selected)} className="px-3 py-1.5 border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-sm inline-flex items-center gap-1">
                    <Trash size={14} /> Delete
                  </button>
                  <button onClick={save} disabled={saving} className="px-4 py-1.5 bg-[#18181B] text-white rounded-lg text-sm hover:bg-[#27272A] disabled:opacity-50 inline-flex items-center gap-1" data-testid="doctpl-save">
                    <FloppyDisk size={14} /> {saving ? '…' : 'Save'}
                  </button>
                </div>
              </div>

              <div className="mb-3">
                <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">HTML body (Jinja2 + inline CSS)</label>
                <textarea
                  rows={22}
                  value={selected.html || ''}
                  onChange={(e) => setSelected({ ...selected, html: e.target.value })}
                  className="w-full border border-zinc-200 rounded-lg px-3 py-2 font-mono text-xs bg-zinc-50 leading-5"
                  spellCheck={false}
                  data-testid="doctpl-body"
                />
                <p className="text-[11px] text-zinc-400 mt-1">Доступные переменные: {'{{ customer.firstName }}, {{ invoice.total }}, {{ invoice["items"] }}, {{ company.name }}, {{ generated_at }}'}. Стили задаются через {'<style>'} / @page прямо в HTML.</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {showNew && (
        <NewTemplateModal
          onClose={() => setShowNew(false)}
          onCreated={(tpl) => { setShowNew(false); load(); setSelected(tpl); }}
        />
      )}
    </div>
  );
};

const NewTemplateModal = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [type, setType] = useState('contract');
  const [language, setLanguage] = useState('en');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const res = await axios.post(
        `${API_URL}/api/admin/document-templates`,
        {
          name: name.trim(),
          type,
          language,
          html: '<h1>{{ customer.firstName }} {{ customer.lastName }}</h1>\n<p>Contract body here.</p>',
          is_active: true,
        },
        { headers: authHeaders() },
      );
      toast.success('Template created');
      onCreated?.(res.data?.template);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-zinc-900 mb-4">Новый шаблон</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Название</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Тип</label>
              <select value={type} onChange={(e) => setType(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm">
                {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Язык</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm">
                {LANG_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg">Cancel</button>
          <button onClick={submit} disabled={saving || !name.trim()} className="px-4 py-2 bg-[#18181B] text-white text-sm rounded-lg hover:bg-[#27272A] disabled:opacity-50">{saving ? '…' : 'Create'}</button>
        </div>
      </div>
    </div>
  );
};

export default AdminDocumentTemplatesPage;
