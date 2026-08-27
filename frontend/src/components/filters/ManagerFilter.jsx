/**
 * ManagerFilter — reusable assignee/manager filter (Доопр #14).
 * Loads /api/team/managers once and renders a select. Visible only for
 * admin/team_lead roles (manager sees own anyway).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Users } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function authHeaders() {
  const token = (typeof window !== 'undefined' && window.localStorage)
    ? window.localStorage.getItem('token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function readMe() {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try { return JSON.parse(window.localStorage.getItem('user') || 'null'); } catch { return null; }
}

export default function ManagerFilter({ value, onChange, t, testId = 'manager-filter' }) {
  const me = readMe();
  const role = (me?.role || '').toLowerCase();
  const visible = ['admin', 'master_admin', 'owner', 'team_lead'].includes(role);
  const [items, setItems] = useState([]);

  const tt = (key, fallback) => {
    if (!t) return fallback;
    const v = t(key);
    return (!v || v === key) ? fallback : v;
  };

  useEffect(() => {
    if (!visible) return;
    (async () => {
      try {
        const r = await axios.get(`${API_URL}/api/team/managers`, { headers: authHeaders() });
        const list = r.data?.items || r.data?.managers || r.data?.data || [];
        setItems(Array.isArray(list) ? list : []);
      } catch { /* silent */ }
    })();
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="flex items-center gap-1.5" data-testid={testId}>
      <Users className="w-3.5 h-3.5 text-[#71717A]" />
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
        data-testid={`${testId}-select`}
      >
        <option value="">{tt('allManagers', 'All managers')}</option>
        {items.map((m) => (
          <option key={m.id} value={m.id}>{m.name || m.email}</option>
        ))}
      </select>
    </div>
  );
}
