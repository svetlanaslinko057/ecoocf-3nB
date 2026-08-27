/**
 * ResendApiKeysPanel — управление дополнительными API-ключами Resend из админки.
 *
 * Возможности:
 *   • Список ключей (id / name / created_at / last_used_at)
 *   • Создать новый ключ (POST /api-keys) с выбором permission и опционально domain_id
 *   • После создания — модалка с copy-кнопкой и предупреждением "save now, won't show again"
 *   • Удалить ключ (DELETE /api-keys/{id}) с confirm
 *
 * Важная UX-деталь: Resend показывает значение ключа ТОЛЬКО при создании.
 * Поэтому реализована модалка-однострел с большой copy-кнопкой и amber-warning.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus,
  RefreshCw,
  Trash2,
  Copy,
  Key,
  AlertTriangle,
  Eye,
  EyeOff,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useLang } from '../../i18n/LanguageContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Permission metadata. `hintKey` is resolved with t() at render time so the
// description switches with the active locale (uk / en / bg).
const PERMISSION_INFO = {
  full_access: {
    label: 'Full access',
    hintKey: 'resendFullAccessDesc',
    chip: 'bg-rose-50 text-rose-700 ring-rose-200',
  },
  sending_access: {
    label: 'Sending access',
    hintKey: 'resendSendingOnlyDesc',
    chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  },
};

function copyToClipboard(text) {
  if (!text) return;
  try {
    navigator.clipboard.writeText(text);
    toast.success('Copied');
  } catch {
    toast.error('Copy failed');
  }
}

export default function ResendApiKeysPanel({ hasApiKey }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPermission, setNewPermission] = useState('sending_access');
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState({});

  // Modal that shows freshly-created key value (Resend returns it once)
  const [createdKey, setCreatedKey] = useState(null); // { id, token, name }
  const [tokenVisible, setTokenVisible] = useState(false);

  const fetchList = useCallback(async () => {
    if (!hasApiKey) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/integrations/resend/api-keys`, { headers: authHeaders() });
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load API keys');
    } finally {
      setLoading(false);
    }
  }, [hasApiKey]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleCreate = async () => {
    const name = (newName || '').trim();
    if (!name) {
      toast.error(t('resendKeyNamePlaceholder'));
      return;
    }
    setAdding(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/integrations/resend/api-keys`,
        { name, permission: newPermission },
        { headers: authHeaders() },
      );
      const created = r.data?.key;
      if (created?.token) {
        setCreatedKey({ id: created.id, token: created.token, name });
        toast.success(t('resendKeyCreatedSaveNow'));
      } else {
        toast.success(t('resendKeyCreated'));
      }
      setNewName('');
      setShowAdd(false);
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create API key');
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (key) => {
    if (!window.confirm(t('resendConfirmDeleteKey').replace('{name}', key.name))) return;
    setDeleting((d) => ({ ...d, [key.id]: true }));
    try {
      await axios.delete(
        `${API_URL}/api/admin/integrations/resend/api-keys/${key.id}`,
        { headers: authHeaders() },
      );
      toast.success(t('resendKeyDeleted').replace('{name}', key.name));
      await fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    } finally {
      setDeleting((d) => ({ ...d, [key.id]: false }));
    }
  };

  if (!hasApiKey) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12.5px] text-amber-800 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{t('resendNeedSaveMainKey')}</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Key className="w-4 h-4 text-[#71717A]" />
          <h4 className="text-[13px] font-semibold text-[#18181B]">API Keys</h4>
          <span className="text-[11.5px] text-[#71717A]">({items.length})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={fetchList}
            disabled={loading}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white border border-[#E4E4E7] hover:bg-[#FAFAFA] disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#71717A] ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => setShowAdd(!showAdd)}
            data-testid="resend-add-apikey-toggle"
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-[#18181B] text-white text-[12px] font-medium hover:bg-[#27272A]"
          >
            <Plus className="w-3.5 h-3.5" />
            New key
          </button>
        </div>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] p-3 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="production-backend"
                className="w-full h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
                data-testid="resend-new-apikey-name"
              />
            </div>
            <div>
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">Permission</label>
              <select
                value={newPermission}
                onChange={(e) => setNewPermission(e.target.value)}
                className="w-full h-9 px-2 rounded-lg border border-[#E4E4E7] bg-white text-[13px]"
                data-testid="resend-new-apikey-permission"
              >
                <option value="sending_access">Sending access (recommended)</option>
                <option value="full_access">Full access (admin only)</option>
              </select>
            </div>
          </div>
          <p className="text-[11px] text-[#71717A] leading-relaxed">
            {t(PERMISSION_INFO[newPermission].hintKey)}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCreate}
              disabled={adding || !newName}
              className="h-9 px-3 rounded-lg bg-emerald-600 text-white text-[12.5px] font-medium hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="resend-create-apikey"
            >
              <Plus className={`w-3.5 h-3.5 ${adding ? 'animate-pulse' : ''}`} />
              {adding ? 'Creating…' : 'Create key'}
            </button>
            <button
              type="button"
              onClick={() => { setShowAdd(false); setNewName(''); }}
              className="h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[12.5px] text-[#71717A] hover:bg-[#FAFAFA]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Keys list */}
      {items.length === 0 && !loading ? (
        <div className="rounded-xl border border-dashed border-[#E4E4E7] p-6 text-center text-[12.5px] text-[#71717A]">
          В аккаунте Resend ещё нет ключей.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((k) => (
            <div key={k.id} className="rounded-xl border border-[#E4E4E7] bg-white px-3.5 py-2.5 flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#71717A] shrink-0" />
                <span className="font-mono text-[13px] font-semibold text-[#18181B] truncate">{k.name}</span>
                <span className="text-[10.5px] text-[#A1A1AA] hidden sm:inline">
                  · created {k.created_at ? new Date(k.created_at).toLocaleDateString() : '—'}
                  {k.last_used_at && (
                    <> · last used {new Date(k.last_used_at).toLocaleDateString()}</>
                  )}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(k)}
                disabled={deleting[k.id]}
                className="inline-flex items-center justify-center w-7 h-7 rounded-lg border border-rose-100 bg-white text-rose-600 hover:bg-rose-50 disabled:opacity-50 shrink-0"
                title="Delete key"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* One-time created key modal */}
      {createdKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setCreatedKey(null)}>
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <Key className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-[15px] font-semibold text-[#18181B]">Key created · {createdKey.name}</h3>
                  <p className="text-[11.5px] text-[#71717A]">{t('resendShowOnce')}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCreatedKey(null)}
                className="p-1.5 rounded-lg hover:bg-[#FAFAFA]"
              >
                <X className="w-4 h-4 text-[#71717A]" />
              </button>
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-[12px] text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span><b>{t('resendSaveNow')}</b> {t('resendCannotRecover')}</span>
            </div>

            <div>
              <label className="text-[10.5px] uppercase tracking-wider text-[#71717A] font-semibold block mb-1">API Key</label>
              <div className="flex items-center gap-2">
                <input
                  type={tokenVisible ? 'text' : 'password'}
                  readOnly
                  value={createdKey.token}
                  className="flex-1 h-10 px-3 rounded-lg border border-[#E4E4E7] bg-[#FAFAFA] text-[13px] font-mono"
                />
                <button
                  type="button"
                  onClick={() => setTokenVisible(!tokenVisible)}
                  className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-[#E4E4E7] hover:bg-[#FAFAFA]"
                  title={tokenVisible ? 'Hide' : 'Show'}
                >
                  {tokenVisible ? <EyeOff className="w-4 h-4 text-[#71717A]" /> : <Eye className="w-4 h-4 text-[#71717A]" />}
                </button>
                <button
                  type="button"
                  onClick={() => copyToClipboard(createdKey.token)}
                  className="inline-flex items-center gap-1.5 h-10 px-3 rounded-lg bg-[#18181B] text-white text-[12.5px] font-medium hover:bg-[#27272A]"
                >
                  <Copy className="w-3.5 h-3.5" />
                  Copy
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setCreatedKey(null)}
              className="w-full h-10 rounded-lg bg-[#18181B] text-white text-[13px] font-medium hover:bg-[#27272A]"
            >
              I've saved it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
