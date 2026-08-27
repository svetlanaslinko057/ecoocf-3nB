import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../App';
import { useLang, getLocale } from '../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { 
  Plus, 
  Pencil, 
  UserCirclePlus,
  UserCircleMinus,
  Key,
  ChartBar,
  Phone,
  CheckCircle,
  Warning,
  Clock,
  UsersThree,
} from '@phosphor-icons/react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';

// Canonical 4-role taxonomy. `master_admin`/`owner`/`moderator`/`finance` are
// legacy values kept elsewhere only for back-compat reading of old rows —
// new staff accounts should only ever be assigned one of these three
// staff-facing roles (the 4th role, `user`, is for customers).
const ROLES = ['admin', 'team_lead', 'manager'];

const Staff = () => {
  const { t } = useLang();
  const [staff, setStaff] = useState([]);
  const [stats, setStats] = useState({});
  const [performance, setPerformance] = useState([]);
  const [inactiveManagers, setInactiveManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('day');
  const [activeTab, setActiveTab] = useState('list');
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    firstName: '', lastName: '', email: '', phone: '', role: 'manager', teamId: '', password: ''
  });
  const [knownTeams, setKnownTeams] = useState([]);

  useEffect(() => {
    fetchStaff();
    fetchStats();
    fetchTeams();
  }, []);

  useEffect(() => {
    if (activeTab === 'performance') {
      fetchPerformance();
      fetchInactive();
    }
  }, [activeTab, period]);

  // ── Normalisers ────────────────────────────────────────────────
  // Backend returns `name`, `disabled`, no firstName/lastName/isActive.
  // The original UI code read the opposite shape, leaving every row
  // showing as "Inactive" with empty initials. Normalise at fetch time.
  const normalizeStaff = (u) => {
    if (!u) return u;
    const [firstName = '', ...rest] = (u.name || u.email || '').split(/\s+/);
    const lastName = rest.join(' ');
    // Derive isActive from `disabled` when the backend didn't set it.
    // Careful: backend sends `isActive: null` (not undefined) for existing
    // seeded rows, so we treat both null/undefined as "missing".
    const isActiveRaw = u.isActive ?? u.is_active;
    const isActive = isActiveRaw === true || isActiveRaw === false
      ? isActiveRaw
      : !u.disabled;
    return {
      ...u,
      firstName: u.firstName || firstName,
      lastName: u.lastName || lastName,
      isActive,
      lastLoginAt: u.lastLoginAt || u.last_login_at || u.lastLogin || null,
    };
  };

  const fetchStaff = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/staff`);
      // Backend may return `items`, `data`, or a bare array — accept all.
      const raw = Array.isArray(res.data) ? res.data
                : res.data?.items
                || res.data?.data
                || [];
      const normalized = raw.map(normalizeStaff);
      setStaff(normalized);
      // Re-derive the 4 stat cards locally so they match the visible rows
      // (backend's /api/staff/stats can lag / use a different heuristic).
      setStats((prev) => ({
        ...prev,
        total: normalized.length,
        active: normalized.filter((u) => u.isActive).length,
        inactive: normalized.filter((u) => !u.isActive).length,
        online: normalized.filter((u) => u.isOnline).length,
      }));
    } catch (err) {
      toast.error(t('error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/staff/stats`);
      // Backend: { success, stats: {...} }. Fallback for legacy shape.
      const s = res.data?.stats || res.data?.data || res.data || {};
      // Keep counts that fetchStaff has already derived from the actual
      // staff list — backend's `/api/staff/stats` can lag or use different
      // heuristics (sessions-based), which produced the "0 active / 3 inactive"
      // mismatch even though every visible row was ACTIVE.
      setStats((prev) => ({
        ...s,
        total: prev.total ?? s.total ?? 0,
        active: prev.active ?? s.active ?? 0,
        inactive: prev.inactive ?? s.inactive ?? 0,
        online: prev.online ?? s.online ?? 0,
      }));
    } catch (err) {}
  };

  const fetchPerformance = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/staff/performance?period=${period}`);
      // Backend returns { success, data: [...] } — not a bare array.
      // Accept array | {data} | {items} to stay compatible with both.
      const raw = Array.isArray(res.data)
        ? res.data
        : res.data?.data || res.data?.items || [];
      setPerformance(raw);
    } catch (err) {
      console.error('Performance error:', err);
    }
  };

  const fetchInactive = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/staff/inactive?hours=2`);
      const raw = Array.isArray(res.data)
        ? res.data
        : res.data?.data || res.data?.items || [];
      setInactiveManagers(raw);
    } catch (err) {}
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Normalise teamId — empty string => null so backend ACL no-team cohort works.
      const payload = { ...formData, teamId: (formData.teamId || '').trim() || null };
      if (editingUser) {
        const updateData = { ...payload };
        if (!updateData.password) delete updateData.password;
        await axios.put(`${API_URL}/api/staff/${editingUser.id}`, updateData);
        toast.success(t('userUpdated'));
      } else {
        await axios.post(`${API_URL}/api/staff`, payload);
        toast.success(t('userCreated'));
      }
      setShowModal(false);
      resetForm();
      fetchStaff();
      fetchStats();
      fetchTeams();
    } catch (err) {
      toast.error(err.response?.data?.message || t('error'));
    }
  };

  const fetchTeams = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/staff/teams`);
      const raw = Array.isArray(res.data) ? res.data : (res.data?.data || []);
      setKnownTeams(raw);
    } catch (_) {
      /* non-fatal — the field still works as a free-form input */
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await axios.put(`${API_URL}/api/staff/${user.id}/toggle-active`);
      toast.success(user.isActive ? t('userDeactivated') : t('userActivated'));
      fetchStaff();
    } catch (err) { 
      toast.error(t('error')); 
    }
  };

  const handleResetPassword = async (userId) => {
    const newPassword = prompt(t('enterNewPassword'));
    if (!newPassword) return;
    try {
      await axios.post(`${API_URL}/api/staff/${userId}/reset-password`, { newPassword });
      toast.success(t('passwordReset'));
    } catch (err) { 
      toast.error(t('error')); 
    }
  };

  const openEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      firstName: user.firstName,
      lastName: user.lastName,
      email: user.email,
      phone: user.phone || '',
      role: user.role,
      teamId: user.teamId || '',
      password: ''
    });
    setShowModal(true);
  };

  const resetForm = () => {
    setEditingUser(null);
    setFormData({ firstName: '', lastName: '', email: '', phone: '', role: 'manager', teamId: '', password: '' });
  };

  const roleLabels = { 
    master_admin: t('roleMasterAdmin'),
    owner: t('roleMasterAdmin'),
    team_lead: 'Team Lead',
    admin: t('roleAdmin'), 
    moderator: t('roleModerator'), 
    manager: t('roleManager'), 
    finance: t('roleFinance') 
  };

  const periodLabels = { day: t('today'), week: t('week'), month: t('month') };

  return (
    <motion.div 
      data-testid="staff-page" 
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }} 
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <UsersThree size={20} weight="bold" />
          </div>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-[#18181B] leading-tight" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('staffTitle')}
            </h1>
            <p className="text-[12px] text-[#71717A] mt-0.5">{t('teamManagement')}</p>
          </div>
        </div>
        <button 
          onClick={() => { resetForm(); setShowModal(true); }} 
          className="btn-primary w-full sm:w-auto" 
          data-testid="create-user-btn"
        >
          <Plus size={18} weight="bold" />{t('newEmployee')}
        </button>
      </div>

      {/* Shared HR zone marker + cross-link to Manager Load Board */}
      <div className="mb-6">
        <RoleZoneBadge
          variant="hr"
          link={{ href: '/team/managers', label: 'Open Manager Load Board' }}
        />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
        <div className="kpi-card" data-testid="staff-stat-total">
          <div className="kpi-value">{stats.total || 0}</div>
          <div className="kpi-label">{t('total')}</div>
        </div>
        <div className="kpi-card" data-testid="staff-stat-active">
          <div className="kpi-value text-[#059669]">{stats.active || 0}</div>
          <div className="kpi-label">{t('active')}</div>
        </div>
        <div className="kpi-card" data-testid="staff-stat-inactive">
          <div className="kpi-value text-[#71717A]">{stats.inactive || 0}</div>
          <div className="kpi-label">{t('inactive')}</div>
        </div>
        <div className="kpi-card" data-testid="staff-stat-online">
          <div className="kpi-value text-[#4F46E5]">{stats.online || 0}</div>
          <div className="kpi-label">{t('online') || 'Online'}</div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-[#F4F4F5] p-1 rounded-xl">
          <TabsTrigger 
            value="list" 
            className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-6 py-2 rounded-lg text-sm font-medium"
            data-testid="tab-list"
          >
            {t('list')}
          </TabsTrigger>
          <TabsTrigger 
            value="performance" 
            className="data-[state=active]:bg-white data-[state=active]:text-[#18181B] px-6 py-2 rounded-lg text-sm font-medium"
            data-testid="tab-performance"
          >
            {t('performance')}
          </TabsTrigger>
        </TabsList>

        {/* Staff List Tab */}
        <TabsContent value="list">
          <div className="card overflow-x-auto">
            <table className="table-premium min-w-[900px]" data-testid="staff-table">
              <thead>
                <tr>
                  <th>{t('name')}</th>
                  <th>{t('email')}</th>
                  <th>{t('phone')}</th>
                  <th>{t('role')}</th>
                  <th>Team</th>
                  <th>{t('status')}</th>
                  <th>{t('lastLogin')}</th>
                  <th className="text-right">{t('actions')}</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={8} className="text-center py-12 text-[#71717A]">{t('loading')}</td></tr>
                ) : staff.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-12 text-[#71717A]">{t('noStaff')}</td></tr>
                ) : staff.map(user => (
                  <tr key={user.id} data-testid={`staff-row-${user.id}`}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 min-w-[40px] bg-[#18181B] rounded-full flex items-center justify-center text-sm font-semibold text-white">
                          {user.firstName?.[0]}{user.lastName?.[0]}
                        </div>
                        <span className="font-medium text-[#18181B]">{user.firstName} {user.lastName}</span>
                      </div>
                    </td>
                    <td className="text-[#3F3F46]">{user.email}</td>
                    <td className="text-[#71717A]">{user.phone || '—'}</td>
                    <td>
                      <span className="badge status-new">{roleLabels[user.role]}</span>
                    </td>
                    <td>
                      {user.teamId ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#E0E7FF] text-[#3730A3] text-xs font-medium" data-testid={`staff-team-${user.id}`}>
                          {user.teamId}
                        </span>
                      ) : (
                        <span className="text-xs text-[#A1A1AA] italic">no team</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${user.isActive ? 'status-won' : 'status-lost'}`}>
                        {user.isActive ? t('active') : t('inactive')}
                      </span>
                    </td>
                    <td className="text-sm text-[#71717A]">
                      {user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString(getLocale()) : '—'}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <button 
                          onClick={() => openEditModal(user)} 
                          className="p-2 hover:bg-[#F4F4F5] rounded-lg transition-colors" 
                          title={t('edit')}
                          data-testid={`edit-user-${user.id}`}
                        >
                          <Pencil size={16} className="text-[#71717A]" />
                        </button>
                        <button 
                          onClick={() => handleToggleActive(user)} 
                          className={`p-2 rounded-lg transition-colors ${user.isActive ? 'hover:bg-[#FEE2E2]' : 'hover:bg-[#D1FAE5]'}`}
                          title={user.isActive ? t('disable') : t('enable')}
                          data-testid={`toggle-user-${user.id}`}
                        >
                          {user.isActive ? (
                            <UserCircleMinus size={16} className="text-[#DC2626]" />
                          ) : (
                            <UserCirclePlus size={16} className="text-[#059669]" />
                          )}
                        </button>
                        <button 
                          onClick={() => handleResetPassword(user.id)} 
                          className="p-2 hover:bg-[#FEF3C7] rounded-lg transition-colors" 
                          title={t('changePassword')}
                          data-testid={`reset-pwd-${user.id}`}
                        >
                          <Key size={16} className="text-[#D97706]" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance">
          {/* Period Selector - Mobile responsive */}
          <div className="flex flex-col gap-4 mb-6">
            <h2 className="text-lg font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('managerPerformance')}
            </h2>
            <div className="period-tabs w-full sm:w-auto" data-testid="performance-period-selector">
              {['day', 'week', 'month'].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`period-tab flex-1 sm:flex-none ${period === p ? 'active' : ''}`}
                >
                  {periodLabels[p]}
                </button>
              ))}
            </div>
          </div>

          {/* Inactive Managers Alert */}
          {inactiveManagers.length > 0 && (
            <div className="bg-[#FEF3C7] border border-[#FCD34D] rounded-xl p-4 mb-6 flex items-start gap-3" data-testid="inactive-alert">
              <Warning size={20} className="text-[#D97706] mt-0.5" />
              <div>
                <p className="font-medium text-[#92400E]">{t('inactiveManagers')}</p>
                <p className="text-sm text-[#A16207]">
                  {inactiveManagers.map(m => m.userName || 'Unknown').join(', ')} — {t('noActivityHours')}
                </p>
              </div>
            </div>
          )}

          {/* Performance Table - with horizontal scroll */}
          <div className="card overflow-x-auto">
            <table className="table-premium min-w-[800px]" data-testid="performance-table">
              <thead>
                <tr>
                  <th>{t('name')}</th>
                  <th className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <ChartBar size={14} />
                      {t('actionsCount')}
                    </div>
                  </th>
                  <th className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Phone size={14} />
                      {t('calls')}
                    </div>
                  </th>
                  <th className="text-center">{t('leads')}</th>
                  <th className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <CheckCircle size={14} />
                      {t('conversion')}
                    </div>
                  </th>
                  <th className="text-center">{t('tasks')}</th>
                  <th className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Clock size={14} />
                      {t('lastAction')}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {performance.length === 0 ? (
                  <tr><td colSpan={7} className="text-center py-12 text-[#71717A]">{t('noDataForPeriod')}</td></tr>
                ) : performance.map(manager => (
                  <tr key={manager.userId} data-testid={`performance-row-${manager.userId}`}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 min-w-[40px] bg-[#18181B] rounded-full flex items-center justify-center text-sm font-semibold text-white">
                          {manager.userName?.split(' ').map(n => n[0]).join('') || '??'}
                        </div>
                        <div>
                          <p className="font-medium text-[#18181B]">{manager.userName || 'Unknown'}</p>
                          <p className="text-xs text-[#71717A]">{roleLabels[manager.userRole] || manager.userRole}</p>
                        </div>
                      </div>
                    </td>
                    <td className="text-center">
                      <span className="font-semibold text-[#18181B]">{manager.totalActions}</span>
                    </td>
                    <td className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <span className="font-semibold text-[#059669]">{manager.calls}</span>
                        {manager.callsMissed > 0 && (
                          <span className="text-xs text-[#DC2626]">(-{manager.callsMissed})</span>
                        )}
                      </div>
                    </td>
                    <td className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <span className="font-semibold text-[#18181B]">{manager.leadsHandled}</span>
                        <span className="text-xs text-[#059669]">+{manager.leadsConverted}</span>
                      </div>
                    </td>
                    <td className="text-center">
                      <span className={`badge ${manager.conversionRate >= 30 ? 'status-won' : manager.conversionRate >= 15 ? 'status-contacted' : 'status-lost'}`}>
                        {manager.conversionRate}%
                      </span>
                    </td>
                    <td className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <span className="font-semibold text-[#059669]">{manager.tasksCompleted}</span>
                        {manager.tasksOverdue > 0 && (
                          <span className="text-xs text-[#DC2626]">({manager.tasksOverdue} {t('overdueCount')})</span>
                        )}
                      </div>
                    </td>
                    <td className="text-center text-sm text-[#71717A]">
                      {manager.lastActivity ? new Date(manager.lastActivity).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>

      {/* Create/Edit Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md bg-white rounded-2xl border border-[#E4E4E7]" data-testid="staff-modal">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {editingUser ? t('editEmployee') : t('newEmployee')}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-5 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('firstName')}</label>
                <input 
                  type="text" 
                  value={formData.firstName} 
                  onChange={(e) => setFormData({...formData, firstName: e.target.value})} 
                  required 
                  className="input w-full" 
                  data-testid="staff-firstname-input" 
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('lastName')}</label>
                <input 
                  type="text" 
                  value={formData.lastName} 
                  onChange={(e) => setFormData({...formData, lastName: e.target.value})} 
                  required 
                  className="input w-full" 
                  data-testid="staff-lastname-input" 
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('email')}</label>
              <input 
                type="email" 
                value={formData.email} 
                onChange={(e) => setFormData({...formData, email: e.target.value})} 
                required 
                className="input w-full" 
                data-testid="staff-email-input" 
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('phone')}</label>
                <input 
                  type="tel" 
                  value={formData.phone} 
                  onChange={(e) => setFormData({...formData, phone: e.target.value})} 
                  className="input w-full" 
                  data-testid="staff-phone-input" 
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">{t('role')}</label>
                <Select value={formData.role} onValueChange={(v) => setFormData({...formData, role: v})}>
                  <SelectTrigger className="input" data-testid="staff-role-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map(r => (
                      <SelectItem key={r} value={r}>{roleLabels[r]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                Team <span className="font-normal normal-case text-[#A1A1AA]">(short code, e.g. sofia, korea — leave empty for none)</span>
              </label>
              <input
                type="text"
                value={formData.teamId}
                onChange={(e) => setFormData({...formData, teamId: e.target.value})}
                list="staff-team-suggestions"
                placeholder="e.g. sofia, korea, shipping"
                className="input w-full"
                data-testid="staff-team-input"
                autoComplete="off"
              />
              <datalist id="staff-team-suggestions">
                {knownTeams.map(team => (<option key={team} value={team} />))}
              </datalist>
              <p className="mt-1.5 text-[11px] text-[#71717A]">
                Used by the reassignment ACL: a <b>Team Lead</b> can reassign workload only within their own team.
              </p>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                {t('password')} {editingUser && <span className="font-normal normal-case">({t('passwordLeaveEmpty')})</span>}
              </label>
              <input 
                type="password" 
                value={formData.password} 
                onChange={(e) => setFormData({...formData, password: e.target.value})} 
                required={!editingUser}
                className="input w-full" 
                data-testid="staff-password-input" 
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary flex-1" data-testid="staff-cancel-btn">
                {t('cancel')}
              </button>
              <button type="submit" className="btn-primary flex-1" data-testid="staff-submit-btn">
                {editingUser ? t('save') : t('create')}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
};

export default Staff;
