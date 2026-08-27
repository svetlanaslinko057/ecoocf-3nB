/**
 * BIBI Cars — Wave 7 — useManagersMap hook
 *
 * Returns a memoized map: { [managerId]: { id, name, email, role } }.
 * Loads once per mount from /api/admin/reassign/managers (workload payload).
 *
 * For non-admin/non-team-lead users (403), falls back to /api/team/managers,
 * which is publicly readable for staff.
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from '../App';

let _cache = null;
let _cacheTs = 0;
const TTL_MS = 30_000;

export default function useManagersMap() {
  const [map, setMap] = useState(_cache || {});
  const [loading, setLoading] = useState(!_cache);

  useEffect(() => {
    const fresh = _cache && (Date.now() - _cacheTs < TTL_MS);
    if (fresh) {
      setMap(_cache);
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        // Try the workload endpoint first (admin/team_lead see all/own team)
        let res;
        try {
          res = await axios.get(`${API_URL}/api/admin/reassign/managers`);
        } catch (_) {
          // Fallback for plain manager role
          res = await axios.get(`${API_URL}/api/team/managers`);
        }
        const list = Array.isArray(res.data) ? res.data : (res.data?.data || []);
        const m = {};
        list.forEach(x => {
          if (x.id) m[x.id] = {
            id: x.id,
            name: x.name,
            email: x.email,
            role: x.role,
            loadScore: x.loadScore,
            avatarUrl: x.avatarUrl,
          };
        });
        if (cancelled) return;
        _cache = m;
        _cacheTs = Date.now();
        setMap(m);
      } catch (_) {
        if (cancelled) return;
        setMap({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return { managers: map, loading, invalidate: () => { _cache = null; _cacheTs = 0; } };
}
