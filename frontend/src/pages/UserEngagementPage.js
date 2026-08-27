/**
 * BIBI Cars — User Engagement (Unified, Wave 7.5)
 * ==================================================
 *
 * Single source of truth for customer-engagement analytics.
 *
 * - Replaces the legacy "User Engagement Control" (which had a 50% mock
 *   surface: campaigns / sends / templates / history) and the duplicate
 *   "Customer Engagement" manager page in one consolidated screen.
 * - 100% real data — only what the backend can actually produce.
 *
 * Backend surface (all under /api/admin/engagement/*, gated by
 * require_manager_or_admin):
 *
 *     GET /analytics              — KPI counts
 *     GET /top-users              — ranked customers (with phone)
 *     GET /top-vehicles           — ranked stock (with current_bid)
 *     GET /vin-stats?vin=…        — per-VIN engagement counts
 *     GET /customer/{id}          — full per-customer activity trail
 *
 * Adaptive: 1-col on phone, 2-col tablet, 4-col desktop. Tabs stack
 * vertically on phone width.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API_URL } from '../App';
import { useLang } from '../i18n';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Heart, Users, Fire, ChartLine, MagnifyingGlass, Phone, EnvelopeSimple,
  ArrowSquareOut, Scales, Share, CaretLeft, Car, Clock, X
} from '@phosphor-icons/react';
import { AdminPageHeader } from '../components/ui/AdminPagePrimitives';
import RefreshButton from '../components/ui/RefreshButton';

/* ─────────────────────────────────────────────────────────────────────
 * Small presentational helpers
 * ──────────────────────────────────────────────────────────────────── */

const StatCard = ({ label, value, icon: Icon, accent = '#18181B', testid }) => (
  <div
    className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5 transition-shadow hover:shadow-sm"
    data-testid={testid}
  >
    <div className="flex items-center justify-between mb-2 sm:mb-3">
      <span className="text-[10px] sm:text-[11px] font-semibold uppercase tracking-wider text-[#71717A]">{label}</span>
      <Icon size={18} weight="duotone" style={{ color: accent }} />
    </div>
    <div className="text-2xl sm:text-3xl font-bold tabular-nums" style={{ color: accent }}>{value}</div>
  </div>
);

const LevelBadge = ({ level }) => {
  const map = {
    hot:  { bg: '#FEE2E2', fg: '#991B1B', label: 'Hot' },
    warm: { bg: '#FEF3C7', fg: '#92400E', label: 'Warm' },
    cold: { bg: '#E0E7FF', fg: '#3730A3', label: 'Cold' },
  };
  const m = map[level] || map.cold;
  return (
    <span
      className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md"
      style={{ background: m.bg, color: m.fg }}
    >
      {m.label}
    </span>
  );
};

const InitialAvatar = ({ name, email }) => (
  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-semibold flex-shrink-0">
    {(name || email || '?').slice(0, 1).toUpperCase()}
  </div>
);

const EmptyState = ({ icon: Icon, title, hint }) => (
  <div className="py-12 sm:py-16 px-4 text-center text-[#71717A]">
    <Icon size={36} weight="duotone" className="mx-auto mb-3 text-[#A1A1AA]" />
    <div className="font-medium text-[#3F3F46]">{title}</div>
    {hint && <div className="text-sm text-[#71717A] mt-1">{hint}</div>}
  </div>
);

/* ─────────────────────────────────────────────────────────────────────
 * Customer drill-down panel (slides in over the page)
 * ──────────────────────────────────────────────────────────────────── */
const CustomerDrillDown = ({ customerId, onClose }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API_URL}/api/admin/engagement/customer/${encodeURIComponent(customerId)}?limit=50`);
        if (!cancelled) setData(res.data || null);
      } catch (e) {
        if (!cancelled) toast.error('Failed to load customer activity');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const profile = data?.profile || {};
  const allEvents = useMemo(() => {
    if (!data) return [];
    const events = [
      ...((data.favorites || []).map(x => ({ ...x, type: 'favorite' }))),
      ...((data.compares  || []).map(x => ({ ...x, type: 'compare'  }))),
      ...((data.shares    || []).map(x => ({ ...x, type: 'share'    }))),
    ];
    return events.sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
  }, [data]);

  const typeIcon = (t) => t === 'favorite' ? Heart : t === 'compare' ? Scales : Share;
  const typeColor = (t) => t === 'favorite' ? '#DC2626' : t === 'compare' ? '#2563EB' : '#059669';
  const typeLabel = (t) => t === 'favorite' ? 'Favorited' : t === 'compare' ? 'Compared' : 'Shared';

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'tween', duration: 0.25 }}
      className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-white shadow-2xl z-50 flex flex-col"
      data-testid="customer-drilldown"
    >
      <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-[#E4E4E7]">
        <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded-lg" data-testid="customer-drilldown-close">
          <CaretLeft size={18} className="text-[#71717A]" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-[#18181B] truncate">{profile.name || customerId}</div>
          {profile.email && <div className="text-xs text-[#71717A] truncate">{profile.email}</div>}
        </div>
        {data && <LevelBadge level={data.level} />}
        <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded-lg sm:hidden">
          <X size={18} className="text-[#71717A]" />
        </button>
      </div>

      {/* Counters */}
      {data && (
        <div className="grid grid-cols-3 gap-2 px-4 sm:px-6 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA]">
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[#71717A]">Fav</div>
            <div className="font-bold text-[#DC2626] text-lg">{data.counts?.favorites ?? 0}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[#71717A]">Cmp</div>
            <div className="font-bold text-[#2563EB] text-lg">{data.counts?.compares ?? 0}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[#71717A]">Share</div>
            <div className="font-bold text-[#059669] text-lg">{data.counts?.shares ?? 0}</div>
          </div>
        </div>
      )}

      {/* Quick contact actions */}
      {(profile.phone || profile.email) && (
        <div className="flex gap-2 px-4 sm:px-6 py-3 border-b border-[#F4F4F5]">
          {profile.phone && (
            <a
              href={`tel:${profile.phone}`}
              className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-[#18181B] text-white text-sm font-semibold rounded-lg hover:bg-[#27272A]"
              data-testid="customer-drilldown-call"
            >
              <Phone size={14} /> Call
            </a>
          )}
          {profile.email && (
            <a
              href={`mailto:${profile.email}`}
              className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 border border-[#E4E4E7] text-[#18181B] text-sm font-semibold rounded-lg hover:bg-[#F4F4F5]"
              data-testid="customer-drilldown-email"
            >
              <EnvelopeSimple size={14} /> Email
            </a>
          )}
        </div>
      )}

      {/* Activity trail */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-3">
        <div className="text-xs uppercase tracking-wider font-semibold text-[#71717A] mb-3">Recent activity</div>
        {loading ? (
          <div className="text-center py-8 text-[#71717A]">Loading…</div>
        ) : allEvents.length === 0 ? (
          <EmptyState icon={Clock} title="No activity yet" hint="No favorites, comparisons or shares from this customer." />
        ) : (
          <div className="space-y-2">
            {allEvents.map((ev, i) => {
              const TypeIcon = typeIcon(ev.type);
              return (
                <div key={i} className="flex items-start gap-3 p-3 rounded-xl border border-[#F4F4F5] hover:border-[#E4E4E7] transition-colors">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: `${typeColor(ev.type)}1A`, color: typeColor(ev.type) }}
                  >
                    <TypeIcon size={14} weight="bold" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-[#71717A]">{typeLabel(ev.type)}</div>
                    <div className="font-medium text-[#18181B] truncate">
                      {ev.title || [ev.year, ev.make, ev.model].filter(Boolean).join(' ') || ev.vin || '—'}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-[#71717A] mt-0.5">
                      {ev.vin && <span className="font-mono">{ev.vin}</span>}
                      {ev.currentBid && <span>· ${Number(ev.currentBid).toLocaleString()}</span>}
                      {ev.createdAt && <span>· {new Date(ev.createdAt).toLocaleString()}</span>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </motion.div>
  );
};

/* ─────────────────────────────────────────────────────────────────────
 * Main page
 * ──────────────────────────────────────────────────────────────────── */
const UserEngagementPage = () => {
  const { t } = useLang();
  const [loading, setLoading]   = useState(true);
  const [analytics, setAnalytics] = useState(null);
  const [topUsers, setTopUsers]    = useState([]);
  const [topVehicles, setTopVehicles] = useState([]);

  // VIN lookup
  const [vinSearch, setVinSearch] = useState('');
  const [vinStats, setVinStats]   = useState(null);
  const [vinLoading, setVinLoading] = useState(false);

  // Active tab
  const [tab, setTab] = useState('customers'); // 'customers' | 'vehicles'

  // Drill-down panel
  const [drilldownId, setDrilldownId] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [a, u, v] = await Promise.all([
        axios.get(`${API_URL}/api/admin/engagement/analytics`),
        axios.get(`${API_URL}/api/admin/engagement/top-users?limit=50`),
        axios.get(`${API_URL}/api/admin/engagement/top-vehicles?limit=50`),
      ]);
      setAnalytics(a.data || null);
      setTopUsers(Array.isArray(u.data) ? u.data : []);
      setTopVehicles(Array.isArray(v.data) ? v.data : []);
    } catch (err) {
      toast.error(t('adm_data_loading_error') || 'Failed to load engagement data');
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleVinLookup = async (e) => {
    e?.preventDefault?.();
    const vin = (vinSearch || '').trim().toUpperCase();
    if (!vin) return;
    setVinLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/admin/engagement/vin-stats?vin=${encodeURIComponent(vin)}`);
      setVinStats(res.data || null);
    } catch (err) {
      toast.error('VIN lookup failed');
      setVinStats(null);
    } finally {
      setVinLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-5 sm:space-y-6 pb-12"
      data-testid="user-engagement-page"
    >
      <AdminPageHeader
        icon={Heart}
        title="User Engagement"
        subtitle="Watch which cars your customers are hunting — call them before they cool off."
        actions={<RefreshButton onClick={fetchAll} ariaLabel="Refresh engagement data" testId="engagement-refresh-btn" />}
      />

      {/* KPI cards — adaptive grid: 2 cols on phone, 4 cols ≥ md */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          label="Total customers"
          value={loading ? '…' : (analytics?.totalUsers ?? 0)}
          icon={Users}
          accent="#18181B"
          testid="kpi-total"
        />
        <StatCard
          label="Active"
          value={loading ? '…' : (analytics?.activeUsers ?? 0)}
          icon={ChartLine}
          accent="#4F46E5"
          testid="kpi-active"
        />
        <StatCard
          label="Hot"
          value={loading ? '…' : (analytics?.hotUsers ?? 0)}
          icon={Fire}
          accent="#DC2626"
          testid="kpi-hot"
        />
        <StatCard
          label="Engagement"
          value={loading ? '…' : `${analytics?.engagementRate ?? 0}%`}
          icon={ChartLine}
          accent="#059669"
          testid="kpi-rate"
        />
      </div>

      {/* VIN demand check */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#18181B] mb-3">
          <MagnifyingGlass size={16} className="text-[#71717A]" />
          VIN demand check
        </div>
        <form onSubmit={handleVinLookup} className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={vinSearch}
            onChange={(e) => setVinSearch(e.target.value)}
            placeholder="Enter VIN to see exact engagement counts"
            className="flex-1 h-11 px-4 rounded-xl border border-[#E4E4E7] bg-white focus:outline-none focus:border-[#4F46E5] font-mono text-sm uppercase"
            data-testid="vin-input"
          />
          <button
            type="submit"
            disabled={vinLoading || !vinSearch.trim()}
            className="h-11 px-5 bg-[#F4B500] hover:bg-[#E5A800] disabled:bg-[#F4F4F5] disabled:text-[#A1A1AA] text-[#18181B] font-semibold rounded-xl transition-colors"
            data-testid="vin-lookup-btn"
          >
            {vinLoading ? 'Looking up…' : 'Look up'}
          </button>
        </form>

        {vinStats && (vinStats.vin || vinStats.viewsCount > 0) && (
          <div className="mt-4 p-3 sm:p-4 rounded-xl bg-[#FAFAFA] border border-[#F4F4F5]" data-testid="vin-stats-result">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
              <div>
                <div className="font-mono text-sm font-bold text-[#18181B]">{vinStats.vin}</div>
                {(vinStats.make || vinStats.model) && (
                  <div className="text-xs text-[#71717A]">{[vinStats.year, vinStats.make, vinStats.model].filter(Boolean).join(' ')}</div>
                )}
              </div>
              {vinStats.currentBid && (
                <div className="text-sm font-semibold text-[#059669]">
                  ${Number(vinStats.currentBid).toLocaleString()}
                </div>
              )}
            </div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div><div className="text-[10px] uppercase tracking-wider text-[#71717A]">Favorites</div><div className="font-bold text-[#DC2626] text-lg">{vinStats.favoritesCount || 0}</div></div>
              <div><div className="text-[10px] uppercase tracking-wider text-[#71717A]">Compare</div><div className="font-bold text-[#2563EB] text-lg">{vinStats.comparesCount || 0}</div></div>
              <div><div className="text-[10px] uppercase tracking-wider text-[#71717A]">Shares</div><div className="font-bold text-[#059669] text-lg">{vinStats.sharesCount || 0}</div></div>
              <div><div className="text-[10px] uppercase tracking-wider text-[#71717A]">Total</div><div className="font-bold text-[#18181B] text-lg">{vinStats.viewsCount || 0}</div></div>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
        <div className="flex border-b border-[#E4E4E7]" role="tablist">
          <button
            role="tab"
            aria-selected={tab === 'customers'}
            onClick={() => setTab('customers')}
            className={`flex-1 sm:flex-none px-4 sm:px-6 py-3 text-sm font-semibold flex items-center justify-center gap-2 transition-colors border-b-2 ${
              tab === 'customers' ? 'border-[#F4B500] text-[#18181B]' : 'border-transparent text-[#71717A] hover:text-[#18181B]'
            }`}
            data-testid="tab-customers"
          >
            <Users size={16} weight={tab === 'customers' ? 'bold' : 'regular'} />
            Top customers <span className="text-[#A1A1AA]">({topUsers.length})</span>
          </button>
          <button
            role="tab"
            aria-selected={tab === 'vehicles'}
            onClick={() => setTab('vehicles')}
            className={`flex-1 sm:flex-none px-4 sm:px-6 py-3 text-sm font-semibold flex items-center justify-center gap-2 transition-colors border-b-2 ${
              tab === 'vehicles' ? 'border-[#F4B500] text-[#18181B]' : 'border-transparent text-[#71717A] hover:text-[#18181B]'
            }`}
            data-testid="tab-vehicles"
          >
            <Car size={16} weight={tab === 'vehicles' ? 'bold' : 'regular'} />
            Top vehicles <span className="text-[#A1A1AA]">({topVehicles.length})</span>
          </button>
        </div>

        {/* Tab content */}
        {loading ? (
          <div className="py-16 text-center text-[#71717A]">Loading…</div>
        ) : tab === 'customers' ? (
          topUsers.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No customer activity yet"
              hint="Once users add favorites, comparisons or share links, they'll appear here."
            />
          ) : (
            <div className="divide-y divide-[#F4F4F5]" data-testid="top-customers-list">
              {topUsers.map((u) => (
                <button
                  key={u.id}
                  onClick={() => setDrilldownId(u.id)}
                  className="w-full px-4 sm:px-5 py-3 flex items-center gap-3 hover:bg-[#FAFAFA] transition-colors text-left"
                  data-testid={`customer-row-${u.id}`}
                >
                  <InitialAvatar name={u.name} email={u.email} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-[#18181B] truncate">{u.name || u.email || u.id}</span>
                      <LevelBadge level={u.level} />
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#71717A] mt-0.5 truncate">
                      {u.email && <span className="truncate">{u.email}</span>}
                      {u.phone && <span>· {u.phone}</span>}
                    </div>
                  </div>
                  <div className="hidden sm:flex items-center gap-3 text-xs text-[#52525B]">
                    <span title="Favorites">❤ {u.favoritesCount}</span>
                    <span title="Compares">⚖ {u.comparesCount}</span>
                    <span title="Shares">↗ {u.sharesCount}</span>
                  </div>
                  <div className="flex flex-col items-end ml-2">
                    <div className="text-base font-bold text-[#18181B] tabular-nums">{u.score}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA]">score</div>
                  </div>
                  <ArrowSquareOut size={14} className="text-[#A1A1AA] flex-shrink-0 ml-1" />
                </button>
              ))}
            </div>
          )
        ) : (
          topVehicles.length === 0 ? (
            <EmptyState
              icon={Car}
              title="No vehicle interest yet"
              hint="Once users favorite or compare vehicles, the hottest ones will show up here."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4" data-testid="top-vehicles-list">
              {topVehicles.map((v) => (
                <div
                  key={v.vin}
                  className="border border-[#E4E4E7] rounded-xl overflow-hidden hover:shadow-sm transition-shadow flex flex-col"
                  data-testid={`vehicle-card-${v.vin}`}
                >
                  <div className="aspect-[4/3] bg-[#F4F4F5] flex items-center justify-center overflow-hidden">
                    {v.image
                      ? <img src={v.image} alt={v.vin} className="w-full h-full object-cover" loading="lazy" />
                      : <Car size={32} className="text-[#A1A1AA]" />}
                  </div>
                  <div className="p-3 flex-1 flex flex-col">
                    <div className="font-semibold text-[#18181B] text-sm truncate">
                      {v.title || [v.year, v.make, v.model].filter(Boolean).join(' ') || v.vin}
                    </div>
                    <div className="font-mono text-[11px] text-[#71717A] mt-0.5">{v.vin}</div>
                    {v.currentBid && (
                      <div className="text-sm font-semibold text-[#059669] mt-1">${Number(v.currentBid).toLocaleString()}</div>
                    )}
                    <div className="flex items-center gap-3 mt-auto pt-3 text-xs text-[#52525B]">
                      <span className="text-[#DC2626]" title="Favorites">❤ {v.favoritesCount}</span>
                      <span className="text-[#2563EB]" title="Compares">⚖ {v.comparesCount}</span>
                      <span className="text-[#059669]" title="Shares">↗ {v.sharesCount}</span>
                      <span className="ml-auto font-bold text-[#18181B]">{v.viewsCount}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Drill-down panel */}
      <AnimatePresence>
        {drilldownId && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/40 z-40"
              onClick={() => setDrilldownId(null)}
            />
            <CustomerDrillDown
              customerId={drilldownId}
              onClose={() => setDrilldownId(null)}
            />
          </>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default UserEngagementPage;
