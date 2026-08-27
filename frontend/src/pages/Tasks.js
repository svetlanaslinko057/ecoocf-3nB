/**
 * Tasks — global Tasks page.
 *
 * Доопр #9 (P1) — Сторінка задач  spec compliance:
 *
 *   Filters (left rail):
 *     • Today          (filter=today)
 *     • Tomorrow       (filter=tomorrow)
 *     • No deadline    (filter=no_deadline)
 *     • Overdue        (filter=overdue)
 *     • Completed      (status=completed)
 *     • Not completed  (status=pending|in_progress)
 *     • Leads w/o tasks    (separate panel via /api/tasks/reports/leads-without-tasks)
 *     • Customers w/o tasks (separate panel via /api/tasks/reports/customers-without-tasks)
 *     • By manager (assigneeId filter, admin/team_lead only)
 *
 *   Fields shown per task:
 *     • title, description
 *     • lead / customer link (clickable → opens 360-card)
 *     • assignee (manager)
 *     • created_at, dueDate, status, priority, comment
 *
 *   RBAC (enforced by backend already):
 *     • manager      → only own tasks
 *     • team_lead    → all tasks
 *     • admin/owner  → all tasks
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { API_URL } from '../App';
import { useLang, getLocale } from '../i18n';
import { toast } from 'sonner';
import WhiteDatePicker from '../components/ui/WhiteDatePicker';
import {
  Plus, Clock, Warning, ListChecks, User, ShieldCheck,
  CheckCircle, Calendar, CalendarBlank, CalendarPlus, CalendarSlash,
  CalendarDots, Funnel, ArrowSquareOut, ChatCircleDots,
} from '@phosphor-icons/react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { motion } from 'framer-motion';
import RefreshButton from '../components/ui/RefreshButton';

const TASK_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled'];
const TASK_PRIORITIES = ['low', 'medium', 'high', 'urgent'];

function authHeaders() {
  const token = (typeof window !== 'undefined' && window.localStorage)
    ? window.localStorage.getItem('token')
    : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function readMe() {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try { return JSON.parse(window.localStorage.getItem('user') || 'null'); } catch { return null; }
}

const ROLE_BADGE = {
  admin:       { label: 'Admin',       bg: '#FEF3C7', fg: '#92400E' },
  master_admin:{ label: 'Master',      bg: '#FEF3C7', fg: '#92400E' },
  owner:       { label: 'Owner',       bg: '#FEF3C7', fg: '#92400E' },
  team_lead:   { label: 'Team Lead',   bg: '#E0E7FF', fg: '#4338CA' },
  manager:     { label: 'Manager',     bg: '#DCFCE7', fg: '#166534' },
};

function tt(t, key, fallback) {
  const v = t(key);
  return (!v || v === key) ? fallback : v;
}

const QUICK_FILTERS = [
  { id: 'all',         icon: ListChecks,    color: '#18181B', labelKey: 'tasksFilterAll',         fallback: 'All tasks' },
  { id: 'today',       icon: Calendar,      color: '#2563EB', labelKey: 'tasksFilterToday',       fallback: 'Today' },
  { id: 'tomorrow',    icon: CalendarPlus,  color: '#7C3AED', labelKey: 'tasksFilterTomorrow',    fallback: 'Tomorrow' },
  { id: 'no_deadline', icon: CalendarBlank, color: '#71717A', labelKey: 'tasksFilterNoDeadline',  fallback: 'No deadline' },
  { id: 'overdue',     icon: Warning,       color: '#DC2626', labelKey: 'tasksFilterOverdue',     fallback: 'Overdue' },
  { id: 'completed',   icon: CheckCircle,   color: '#16A34A', labelKey: 'tasksFilterCompleted',   fallback: 'Completed' },
  { id: 'open',        icon: Clock,         color: '#D97706', labelKey: 'tasksFilterOpen',        fallback: 'Not completed' },
];

const ORPHAN_PANELS = [
  { id: 'leads',     icon: CalendarSlash, labelKey: 'tasksFilterLeadsWoTasks',     fallback: 'Leads w/o tasks',     endpoint: '/api/tasks/reports/leads-without-tasks',     linkPrefix: '/admin/leads' },
  { id: 'customers', icon: CalendarDots,  labelKey: 'tasksFilterCustomersWoTasks', fallback: 'Customers w/o tasks', endpoint: '/api/tasks/reports/customers-without-tasks', linkPrefix: '/admin/customers' },
];

const Tasks = () => {
  const { t } = useLang();
  const me = useMemo(() => readMe(), []);
  const myRole = (me?.role || '').toLowerCase();
  const canSeeAssigneeFilter = ['admin', 'master_admin', 'owner', 'team_lead'].includes(myRole);
  const canCreateTasks = canSeeAssigneeFilter;

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [quickFilter, setQuickFilter] = useState('all');
  const [assigneeFilter, setAssigneeFilter] = useState('');
  const [orphanMode, setOrphanMode] = useState(null); // 'leads' | 'customers' | null
  const [orphanItems, setOrphanItems] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [assigneeOptions, setAssigneeOptions] = useState([]);
  const [formData, setFormData] = useState({
    title: '', description: '', priority: 'medium', dueDate: '', assigneeId: '', comment: '',
  });

  // ─── Fetch tasks (respects quick + assignee filters) ─────────────────
  const fetchTasks = useCallback(async () => {
    if (orphanMode) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (quickFilter === 'today')        params.append('filter', 'today');
      else if (quickFilter === 'tomorrow') params.append('filter', 'tomorrow');
      else if (quickFilter === 'overdue')  params.append('filter', 'overdue');
      else if (quickFilter === 'no_deadline') params.append('filter', 'no_deadline');
      else if (quickFilter === 'completed')   params.append('status', 'completed');
      else if (quickFilter === 'open') {
        // backend doesn't have a NOT-completed filter; pass status=pending and merge
        // client-side: we'll just filter cancelled out below.
        params.append('status', 'pending');
      }
      if (assigneeFilter) params.append('assigneeId', assigneeFilter);
      params.append('limit', '500');

      const res = await axios.get(`${API_URL}/api/tasks?${params}`, { headers: authHeaders() });
      let items = res.data.data || res.data.items || [];

      if (quickFilter === 'open') {
        // Combine pending + in_progress (do a second call for in_progress).
        const p2 = new URLSearchParams(params);
        p2.set('status', 'in_progress');
        try {
          const r2 = await axios.get(`${API_URL}/api/tasks?${p2}`, { headers: authHeaders() });
          const more = r2.data.data || r2.data.items || [];
          items = items.concat(more);
        } catch (_) { /* swallow */ }
      }

      setTasks(items);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 401) toast.error(t('sessionExpired') || 'Session expired — please log in again.');
      else toast.error(err?.response?.data?.detail || t('error'));
    } finally { setLoading(false); }
  }, [quickFilter, assigneeFilter, orphanMode, t]);

  const fetchOrphans = useCallback(async () => {
    if (!orphanMode) return;
    const panel = ORPHAN_PANELS.find((p) => p.id === orphanMode);
    if (!panel) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (assigneeFilter) params.append('managerId', assigneeFilter);
      const res = await axios.get(`${API_URL}${panel.endpoint}?${params}`, { headers: authHeaders() });
      setOrphanItems(res.data?.items || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load report');
      setOrphanItems([]);
    } finally { setLoading(false); }
  }, [orphanMode, assigneeFilter]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);
  useEffect(() => { fetchOrphans(); }, [fetchOrphans]);

  // ─── Load eligible assignees (for create modal + filter dropdown) ────
  const loadAssignees = useCallback(async () => {
    if (!canSeeAssigneeFilter) return;
    try {
      const res = await axios.get(`${API_URL}/api/tasks/eligible-assignees`, { headers: authHeaders() });
      const items = res.data?.items || [];
      setAssigneeOptions(items);
      if (items.length && !formData.assigneeId) {
        setFormData((prev) => ({ ...prev, assigneeId: items[0].id }));
      }
    } catch (err) {
      // silent — filter dropdown will just be empty
    }
  }, [canSeeAssigneeFilter, formData.assigneeId]);

  useEffect(() => { loadAssignees(); }, [loadAssignees]);

  const openCreateModal = async () => {
    if (!canCreateTasks) { toast.error(tt(t, 'tasksRoleNotAllowed', 'Your role cannot create tasks.')); return; }
    setShowModal(true);
    await loadAssignees();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    if (!formData.title.trim()) { toast.error((t('taskTitle') || 'Title') + ' — required'); return; }
    if (!formData.assigneeId)   { toast.error(tt(t, 'pickAssignee', 'Please pick an assignee')); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/tasks`, formData, { headers: authHeaders() });
      toast.success(t('taskCreated') || 'Task created');
      setShowModal(false);
      setFormData({ title: '', description: '', priority: 'medium', dueDate: '', assigneeId: '', comment: '' });
      fetchTasks();
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('error') || 'Failed to create task');
    } finally { setSubmitting(false); }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await axios.patch(`${API_URL}/api/tasks/${id}`, { status }, { headers: authHeaders() });
      toast.success(t('statusUpdated') || 'Status updated');
      fetchTasks();
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('error'));
    }
  };

  const handleCommentSave = async (taskId, comment) => {
    try {
      await axios.patch(`${API_URL}/api/tasks/${taskId}`, { comment }, { headers: authHeaders() });
      toast.success(tt(t, 'tasksCommentSaved', 'Comment saved'));
      fetchTasks();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to save comment');
    }
  };

  const statusLabels = {
    pending: t('taskTodo') || 'Pending',
    todo: t('taskTodo') || 'Pending',
    in_progress: t('taskInProgress') || 'In progress',
    completed: t('taskCompleted') || 'Completed',
    cancelled: t('taskCancelled') || 'Cancelled',
  };
  const priorityLabels = {
    low: t('priorityLow') || 'Low',
    medium: t('priorityMedium') || 'Medium',
    high: t('priorityHigh') || 'High',
    urgent: t('priorityUrgent') || 'Urgent',
  };
  const priorityColors = {
    low:    { bg: '#F4F4F5', text: '#71717A' },
    medium: { bg: '#DBEAFE', text: '#2563EB' },
    high:   { bg: '#FEF3C7', text: '#D97706' },
    urgent: { bg: '#FEE2E2', text: '#DC2626' },
  };
  const isOverdue = (dueDate) => dueDate && new Date(dueDate) < new Date();

  // ─── Quick-filter pill ───────────────────────────────────────────────
  const Pill = ({ filter }) => {
    const Icon = filter.icon;
    const active = !orphanMode && quickFilter === filter.id;
    return (
      <button
        type="button"
        onClick={() => { setOrphanMode(null); setQuickFilter(filter.id); }}
        data-testid={`tasks-filter-${filter.id}`}
        className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border text-[12.5px] font-medium transition-colors ${
          active
            ? 'bg-[#18181B] border-[#18181B] text-white'
            : 'bg-white border-[#E4E4E7] text-zinc-700 hover:bg-zinc-50'
        }`}
      >
        <Icon size={14} weight="bold" style={{ color: active ? '#fff' : filter.color }} />
        {tt(t, filter.labelKey, filter.fallback)}
      </button>
    );
  };

  const OrphanPill = ({ panel }) => {
    const Icon = panel.icon;
    const active = orphanMode === panel.id;
    return (
      <button
        type="button"
        onClick={() => { setOrphanMode(panel.id); }}
        data-testid={`tasks-orphan-${panel.id}`}
        className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border text-[12.5px] font-medium transition-colors ${
          active
            ? 'bg-amber-100 border-amber-300 text-amber-900'
            : 'bg-white border-[#E4E4E7] text-zinc-700 hover:bg-zinc-50'
        }`}
      >
        <Icon size={14} weight="bold" />
        {tt(t, panel.labelKey, panel.fallback)}
      </button>
    );
  };

  return (
    <motion.div data-testid="tasks-page" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      {/* ─── Page header ─────────────────────────────────────────────── */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4 mb-6 lg:mb-8">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ListChecks size={20} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('tasksTitle') || 'Tasks'}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('taskManagement') || 'Task management'}
              {myRole && (
                <span className="ml-2 inline-flex items-center gap-1 align-middle">
                  <ShieldCheck size={12} weight="bold" />
                  <span className="text-[10px] uppercase tracking-wider text-[#A1A1AA]">{myRole}</span>
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <RefreshButton onClick={orphanMode ? fetchOrphans : fetchTasks} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="tasks-refresh-btn" />
          {canCreateTasks && (
            <button onClick={openCreateModal} className="btn-primary shrink-0 whitespace-nowrap" data-testid="create-task-btn">
              <Plus size={18} weight="bold" />
              <span className="hidden sm:inline ml-1">{t('newTask') || 'New task'}</span>
            </button>
          )}
        </div>
      </div>

      {/* ─── Filters row ─────────────────────────────────────────────── */}
      <div className="card p-4 sm:p-5 mb-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Funnel size={14} weight="bold" className="text-[#71717A]" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[#71717A]">
            {tt(t, 'tasksFilters', 'Filters')}
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {QUICK_FILTERS.map((f) => <Pill key={f.id} filter={f} />)}
        </div>

        <div className="flex flex-wrap gap-2">
          {ORPHAN_PANELS.map((p) => <OrphanPill key={p.id} panel={p} />)}
        </div>

        {canSeeAssigneeFilter && (
          <div className="flex items-center gap-2 pt-2 border-t border-[#F4F4F5]">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#71717A] shrink-0">
              {tt(t, 'tasksFilterByManager', 'By manager')}:
            </span>
            <Select value={assigneeFilter || 'all'} onValueChange={(v) => setAssigneeFilter(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-full sm:w-[280px] input" data-testid="tasks-assignee-filter">
                <SelectValue placeholder={tt(t, 'allManagers', 'All managers')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tt(t, 'allManagers', 'All managers')}</SelectItem>
                {assigneeOptions.map((opt) => (
                  <SelectItem key={opt.id} value={opt.id}>
                    {opt.displayName || opt.name || opt.email} · {ROLE_BADGE[opt.role]?.label || opt.role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* ─── Body: orphan panel OR tasks list ───────────────────────── */}
      {orphanMode ? (
        <div className="space-y-3 sm:space-y-4">
          {loading ? (
            <div className="text-center py-12 text-[#71717A]">{t('loading') || 'Loading…'}</div>
          ) : orphanItems.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              {tt(t, 'tasksOrphanEmpty', 'Everyone has at least one open task — nothing to act on.')}
            </div>
          ) : orphanItems.map((it) => {
            const panel = ORPHAN_PANELS.find((p) => p.id === orphanMode);
            const link = `${panel.linkPrefix}/${it.id}`;
            return (
              <div key={it.id} className="card p-4 sm:p-5 flex items-start justify-between gap-3" data-testid={`tasks-orphan-row-${it.id}`}>
                <div className="min-w-0 flex-1">
                  <Link to={link} className="font-semibold text-[#18181B] hover:underline">
                    {it.firstName ? `${it.firstName} ${it.lastName || ''}`.trim() : (it.name || it.title || it.id)}
                  </Link>
                  <div className="text-xs text-[#71717A] mt-1 flex flex-wrap gap-3">
                    {it.email && <span>{it.email}</span>}
                    {it.phone && <span>{it.phone}</span>}
                    {it.managerName && <span>· {it.managerName}</span>}
                  </div>
                </div>
                <Link to={link} className="text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1 text-sm font-medium">
                  {tt(t, 'tasksOpen', 'Open')}
                  <ArrowSquareOut size={14} weight="bold" />
                </Link>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-3 sm:space-y-4">
          {loading ? (
            <div className="text-center py-12 text-[#71717A]">{t('loading') || 'Loading…'}</div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">{t('noTasks') || 'No tasks yet'}</div>
          ) : tasks.map((task) => {
            const overdue = isOverdue(task.dueDate) && task.status !== 'completed';
            const pri = priorityColors[task.priority] || priorityColors.medium;
            const assigneeBadge = ROLE_BADGE[(task.assigneeRole || '').toLowerCase()] || null;
            const customerLink  = task.customerId ? `/admin/customers/${task.customerId}` : null;
            const leadLink      = task.leadId     ? `/admin/leads/${task.leadId}`         : null;
            return (
              <div
                key={task.id}
                className={`card p-4 sm:p-5 ${overdue ? 'border-l-4 border-l-[#DC2626]' : ''}`}
                data-testid={`task-card-${task.id}`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <h3 className="font-semibold text-[#18181B] break-words">{task.title}</h3>
                      <span className="badge" style={{ backgroundColor: pri.bg, color: pri.text }}>
                        {priorityLabels[task.priority]}
                      </span>
                      {assigneeBadge && (
                        <span className="badge" style={{ backgroundColor: assigneeBadge.bg, color: assigneeBadge.fg }}>
                          <User size={11} weight="bold" />
                          <span className="ml-1">{task.assigneeName || assigneeBadge.label}</span>
                        </span>
                      )}
                    </div>
                    {task.description && (
                      <p className="text-sm text-[#71717A] mb-3 break-words">{task.description}</p>
                    )}

                    {/* Customer / Lead link block */}
                    {(customerLink || leadLink) && (
                      <div className="flex flex-wrap gap-3 mb-3 text-[12px]">
                        {customerLink && (
                          <Link to={customerLink} className="inline-flex items-center gap-1 text-[#2563EB] hover:underline">
                            <ArrowSquareOut size={12} weight="bold" />
                            {tt(t, 'tasksOpenCustomer', 'Open customer')}
                          </Link>
                        )}
                        {leadLink && (
                          <Link to={leadLink} className="inline-flex items-center gap-1 text-[#2563EB] hover:underline">
                            <ArrowSquareOut size={12} weight="bold" />
                            {tt(t, 'tasksOpenLead', 'Open lead')}
                          </Link>
                        )}
                      </div>
                    )}

                    {/* Dates row */}
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      {task.dueDate && (
                        <div className={`flex items-center gap-1.5 ${overdue ? 'text-[#DC2626]' : 'text-[#71717A]'}`}>
                          {overdue ? <Warning size={14} weight="bold" /> : <Clock size={14} />}
                          <span>{tt(t, 'tasksDue', 'Due')}: {new Date(task.dueDate).toLocaleString(getLocale())}</span>
                        </div>
                      )}
                      {!task.dueDate && (
                        <div className="flex items-center gap-1.5 text-[#A1A1AA]">
                          <CalendarBlank size={14} />
                          <span>{tt(t, 'tasksNoDeadline', 'No deadline')}</span>
                        </div>
                      )}
                      {task.created_at && (
                        <div className="text-xs text-[#A1A1AA]">
                          {t('createdBy') || 'Created'}: {new Date(task.created_at).toLocaleDateString(getLocale())}
                          {task.createdByName ? ` · ${task.createdByName}` : ''}
                        </div>
                      )}
                    </div>

                    {/* Inline comment editor */}
                    <CommentRow
                      taskId={task.id}
                      initialComment={task.comment || task.result || ''}
                      onSave={handleCommentSave}
                      t={t}
                    />
                  </div>

                  {/* Status selector */}
                  <div className="sm:w-[180px] shrink-0">
                    <Select value={task.status} onValueChange={(v) => handleStatusChange(task.id, v)}>
                      <SelectTrigger className="w-full input" data-testid={`task-status-${task.id}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TASK_STATUSES.map((s) => (<SelectItem key={s} value={s}>{statusLabels[s]}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── Create-task modal ───────────────────────────────────────── */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent
          className="w-[calc(100%-24px)] sm:max-w-md bg-white rounded-2xl border border-[#E4E4E7] p-4 sm:p-6"
          data-testid="task-modal"
        >
          <DialogHeader>
            <DialogTitle
              className="text-lg sm:text-xl font-bold text-[#18181B]"
              style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
            >
              {t('newTask') || 'New task'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5 mt-3 sm:mt-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                {t('taskTitle') || 'Title'} *
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
                className="input w-full"
                data-testid="task-title-input"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                {t('assignee') || 'Assignee'} *
              </label>
              <Select
                value={formData.assigneeId || ''}
                onValueChange={(v) => setFormData({ ...formData, assigneeId: v })}
              >
                <SelectTrigger className="input w-full" data-testid="task-assignee-select">
                  <SelectValue placeholder={tt(t, 'pickAssignee', 'Pick an assignee')} />
                </SelectTrigger>
                <SelectContent>
                  {assigneeOptions.length === 0 && (
                    <SelectItem value="__none__" disabled>
                      {t('noEligibleAssignees') || 'No eligible assignees'}
                    </SelectItem>
                  )}
                  {assigneeOptions.map((opt) => (
                    <SelectItem key={opt.id} value={opt.id}>
                      {opt.displayName || opt.name || opt.email} · {ROLE_BADGE[opt.role]?.label || opt.role}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                  {t('priority') || 'Priority'}
                </label>
                <Select value={formData.priority} onValueChange={(v) => setFormData({ ...formData, priority: v })}>
                  <SelectTrigger className="input w-full" data-testid="task-priority-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TASK_PRIORITIES.map((p) => (<SelectItem key={p} value={p}>{priorityLabels[p]}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                  {t('deadline') || 'Deadline'}
                </label>
                <WhiteDatePicker
                  value={formData.dueDate}
                  onChange={(e) => setFormData({ ...formData, dueDate: e.target.value })}
                  data-testid="task-duedate-input"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                {t('description') || 'Description'}
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="input w-full resize-none"
                data-testid="task-description-input"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                {tt(t, 'tasksComment', 'Comment')}
              </label>
              <textarea
                value={formData.comment}
                onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                rows={2}
                placeholder={tt(t, 'tasksCommentPh', 'Anything the assignee should keep in mind…')}
                className="input w-full resize-none"
                data-testid="task-comment-input"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row gap-2 sm:gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="btn-secondary w-full sm:flex-1"
                disabled={submitting}
              >
                {t('cancel') || 'Cancel'}
              </button>
              <button
                type="submit"
                className="btn-primary w-full sm:flex-1"
                data-testid="task-submit-btn"
                disabled={submitting}
              >
                {submitting ? (t('saving') || 'Saving…') : (t('create') || 'Create')}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
};

/* ── Inline comment editor (saves on blur) ───────────────────────────── */
const CommentRow = ({ taskId, initialComment, onSave, t }) => {
  const [val, setVal] = useState(initialComment || '');
  const [dirty, setDirty] = useState(false);
  useEffect(() => { setVal(initialComment || ''); setDirty(false); }, [initialComment]);

  return (
    <div className="mt-3 flex items-start gap-2">
      <ChatCircleDots size={14} weight="bold" className="text-[#71717A] mt-2 shrink-0" />
      <div className="flex-1">
        <textarea
          value={val}
          onChange={(e) => { setVal(e.target.value); setDirty(true); }}
          placeholder={(t('addComment') || 'Add a comment…')}
          rows={1}
          className="w-full text-sm rounded-lg border border-[#E4E4E7] px-2 py-1.5 focus:outline-none focus:border-[#18181B] resize-none bg-white"
          data-testid={`task-comment-${taskId}`}
        />
        {dirty && (
          <div className="flex justify-end mt-1">
            <button
              type="button"
              onClick={() => { onSave(taskId, val); setDirty(false); }}
              className="text-xs font-semibold text-[#18181B] hover:underline"
            >
              {t('save') || 'Save'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Tasks;
