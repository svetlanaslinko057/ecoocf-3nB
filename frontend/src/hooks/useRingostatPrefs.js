/**
 * Hook: useRingostatPrefs
 *
 * Loads the current user's effective Ringostat UI preferences from
 * ``GET /api/me/preferences/ringostat-ui`` and exposes:
 *
 *   { prefs, role, savedPrefs, save, loading }
 *
 * Backend already enforces:
 *   - role-based defaults (admin/owner/master_admin → silent;
 *     team_lead → supervision mode; manager → intrusive)
 *   - manager cannot disable `force_outcome_blocking` or
 *     `show_outcome_banner` (hard guard)
 *
 * The frontend just reads ``prefs`` and shows/hides UI accordingly.
 */
import { useCallback, useEffect, useState } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

function getToken() {
  return (
    localStorage.getItem('token') ||
    localStorage.getItem('auth_token') ||
    localStorage.getItem('access_token') ||
    ''
  );
}

async function rawFetch(url, opts = {}) {
  const token = getToken();
  return fetch(`${BACKEND_URL}${url}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
    ...opts,
  });
}

const FALLBACK = {
  show_live_bar: true,
  show_incoming_popup: true,
  show_missed_alerts: true,
  show_outcome_banner: true,
  force_outcome_blocking: true,
  show_aggregate_summary: false,
};

export function useRingostatPrefs() {
  const [prefs, setPrefs] = useState(FALLBACK);
  const [savedPrefs, setSavedPrefs] = useState({});
  const [role, setRole] = useState('');
  const [roleDefaults, setRoleDefaults] = useState(FALLBACK);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await rawFetch('/api/me/preferences/ringostat-ui');
      if (!r.ok) {
        setLoading(false);
        return;
      }
      const d = await r.json();
      setPrefs(d.effective || FALLBACK);
      setSavedPrefs(d.saved || {});
      setRole(d.role || '');
      setRoleDefaults(d.role_defaults || FALLBACK);
    } catch {
      // Silent fallback to FALLBACK — never break the UI
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(
    async (patch) => {
      try {
        const r = await rawFetch('/api/me/preferences/ringostat-ui', {
          method: 'PATCH',
          body: JSON.stringify(patch),
        });
        if (r.ok) {
          const d = await r.json();
          setPrefs(d.effective || prefs);
          setSavedPrefs(d.saved || savedPrefs);
          return true;
        }
      } catch {
        // ignore
      }
      return false;
    },
    [prefs, savedPrefs]
  );

  return { prefs, savedPrefs, role, roleDefaults, save, loading, refresh: load };
}

export default useRingostatPrefs;
